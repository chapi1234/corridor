from datetime import UTC, datetime

import httpx
import pytest
import respx

from corridor.domain.geometry import LatLon
from corridor.integrations.tomtom import TomTomClient, main_highways, parse_search_result
from corridor.planning.errors import RouteNotFoundError, UpstreamServiceError
from tests.conftest import load_fixture

BASE = "https://api.tomtom.test"
DENVER = LatLon(39.7392, -104.9903)
AURORA = LatLon(39.742, -104.7563)
DEPART = datetime(2026, 11, 3, 13, tzinfo=UTC)


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield TomTomClient(http, api_key="k", base_url=BASE, backoff_s=0)


@respx.mock
async def test_calculate_routes_parses_points_anchors_and_highways(client: TomTomClient) -> None:
    route = respx.get(url__startswith=f"{BASE}/routing/1/calculateRoute/").mock(
        return_value=httpx.Response(200, json=load_fixture("tomtom_route.json"))
    )

    routes = await client.calculate_routes(
        [DENVER, AURORA], depart_at=DEPART, gross_weight_kg=34_019.4, alternatives=2
    )

    params = route.calls.last.request.url.params
    assert params["travelMode"] == "truck"
    assert params["vehicleWeight"] == "34019"
    assert params["departAt"] == "2026-11-03T13:00:00Z"
    assert params["maxAlternatives"] == "2"

    primary, alternative = routes
    assert primary.source == "primary"
    assert alternative.source == "alternative"
    assert len(primary.points) == 4  # consecutive duplicate removed
    assert primary.length_m == 20_000
    assert primary.anchors[2].distance_m == 5000
    assert primary.anchors[2].elapsed_s == 450
    assert primary.highways == ("US-6", "I-70", "CO-470")
    assert alternative.anchors == ()


@respx.mock
async def test_via_routes_are_labelled(client: TomTomClient) -> None:
    respx.get(url__startswith=f"{BASE}/routing/").mock(
        return_value=httpx.Response(200, json=load_fixture("tomtom_route.json"))
    )
    routes = await client.calculate_routes(
        [DENVER, LatLon(40, -104.9), AURORA], depart_at=DEPART, gross_weight_kg=1, alternatives=0
    )
    assert {r.source for r in routes} == {"via"}


@respx.mock
async def test_no_route_found_maps_to_domain_error(client: TomTomClient) -> None:
    body = {"error": {"description": "Unable to find a route", "code": "NO_ROUTE_FOUND"}}
    respx.get(url__startswith=f"{BASE}/routing/").mock(return_value=httpx.Response(400, json=body))

    with pytest.raises(RouteNotFoundError):
        await client.calculate_routes(
            [DENVER, AURORA], depart_at=DEPART, gross_weight_kg=1, alternatives=0
        )


@respx.mock
async def test_retries_transient_errors_then_raises(client: TomTomClient) -> None:
    route = respx.get(url__startswith=f"{BASE}/routing/").mock(
        return_value=httpx.Response(503, text="busy")
    )
    with pytest.raises(UpstreamServiceError) as excinfo:
        await client.calculate_routes(
            [DENVER, AURORA], depart_at=DEPART, gross_weight_kg=1, alternatives=0
        )
    assert route.call_count == 3
    assert excinfo.value.status == 503


@respx.mock
async def test_search_and_reverse(client: TomTomClient) -> None:
    respx.get(url__startswith=f"{BASE}/search/2/search/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "g1",
                        "type": "Geography",
                        "address": {
                            "municipality": "Denver",
                            "countrySubdivision": "CO",
                            "country": "United States",
                            "freeformAddress": "Denver, CO",
                        },
                        "position": {"lat": 39.74, "lon": -104.99},
                    }
                ]
            },
        )
    )
    respx.get(url__startswith=f"{BASE}/search/2/reverseGeocode/").mock(
        return_value=httpx.Response(
            200,
            json={
                "addresses": [{"address": {"municipality": "Laramie", "countrySubdivision": "WY"}}]
            },
        )
    )

    [place] = await client.search("den ver", near=DENVER)
    assert place.label == "Denver, CO"
    assert place.sublabel == "United States"

    reverse = await client.reverse(LatLon(41.31, -105.59))
    assert reverse is not None
    assert reverse.label == "Laramie, WY"


def test_poi_search_result_uses_poi_name() -> None:
    place = parse_search_result(
        {
            "type": "POI",
            "poi": {"name": "Pilot Travel Center"},
            "address": {"freeformAddress": "100 Main St, Ogallala, NE"},
            "position": {"lat": 41.1, "lon": -101.7},
        }
    )
    assert place.label == "Pilot Travel Center"
    assert place.sublabel == "100 Main St, Ogallala, NE"


def test_main_highways_ranks_by_distance_and_keeps_driving_order() -> None:
    instructions = [
        {"routeOffsetInMeters": 0, "roadNumbers": ["CO-2"]},
        {"routeOffsetInMeters": 1_000, "roadNumbers": ["I-76"]},
        {"routeOffsetInMeters": 300_000, "roadNumbers": ["US-34"]},
        {"routeOffsetInMeters": 350_000, "roadNumbers": ["I-80"]},
    ]
    assert main_highways(instructions, 900_000) == ("I-76", "US-34", "I-80")


def test_requires_api_key() -> None:
    with pytest.raises(UpstreamServiceError, match="TOMTOM_API_KEY"):
        TomTomClient(httpx.AsyncClient(), api_key="")
