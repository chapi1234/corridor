from datetime import UTC, datetime

import httpx
import pytest
import respx

from corridor.domain.geometry import LatLon
from corridor.integrations.osrm import OsrmClient, main_highways
from corridor.integrations.photon import PhotonClient
from corridor.integrations.polyline import decode, encode
from corridor.planning.errors import RouteNotFoundError

OSRM = "https://osrm.test"
PHOTON = "https://photon.test"
A, B = LatLon(39.74, -104.99), LatLon(39.10, -94.58)
DEPART = datetime(2026, 11, 3, 13, tzinfo=UTC)

OSRM_ROUTE = {
    "code": "Ok",
    "routes": [
        {
            "distance": 30.0,
            "duration": 3.0,
            "geometry": encode(
                [LatLon(39.74, -104.99), LatLon(39.74, -104.98), LatLon(39.74, -104.97)]
            ),
            "legs": [
                {
                    "steps": [
                        {"ref": "I 70", "distance": 20.0, "duration": 2.0},
                        {"ref": "US 40; I 70", "distance": 10.0, "duration": 1.0},
                        {"distance": 0.0, "duration": 0.0},
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
async def http():
    async with httpx.AsyncClient() as client:
        yield client


@respx.mock
async def test_osrm_parses_geometry_anchors_and_highways(http: httpx.AsyncClient) -> None:
    respx.get(url__startswith=f"{OSRM}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json=OSRM_ROUTE)
    )
    client = OsrmClient(http, base_url=OSRM, backoff_s=0)

    [route] = await client.calculate_routes(
        [A, B], depart_at=DEPART, gross_weight_kg=1, alternatives=2
    )

    assert route.source == "primary"
    assert route.points[0] == LatLon(39.74, -104.99)
    assert route.length_m == 30
    assert route.anchors[0].distance_m == 20
    assert route.anchors[1].elapsed_s == 3
    assert route.highways == ("I-70", "US-40")


@respx.mock
async def test_osrm_no_route(http: httpx.AsyncClient) -> None:
    respx.get(url__startswith=f"{OSRM}/").mock(
        return_value=httpx.Response(200, json={"code": "NoRoute", "routes": []})
    )
    with pytest.raises(RouteNotFoundError):
        await OsrmClient(http, base_url=OSRM, backoff_s=0).calculate_routes(
            [A, B], depart_at=DEPART, gross_weight_kg=1, alternatives=0
        )


def test_osrm_highways_split_multi_refs() -> None:
    steps = [{"ref": "I 25;US 87", "distance": 100.0}, {"ref": "I 80", "distance": 500.0}]
    assert main_highways(steps) == ("I-25", "US-87", "I-80")


def feature(name: str, countrycode: str, **props: str) -> dict:
    return {
        "geometry": {"coordinates": [-104.98, 39.74]},
        "properties": {"name": name, "countrycode": countrycode, "osm_type": "R", "osm_id": 1}
        | props,
    }


@respx.mock
async def test_photon_filters_to_north_america_and_formats_labels(http: httpx.AsyncClient) -> None:
    respx.get(f"{PHOTON}/api/").mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    feature(
                        "Denver", "US", osm_key="place", state="Colorado", country="United States"
                    ),
                    feature("Denver", "GB", osm_key="place", state="England"),
                    feature("Pilot", "US", osm_key="amenity", city="Denver", state="Colorado"),
                ]
            },
        )
    )
    places = await PhotonClient(http, base_url=PHOTON, backoff_s=0).search("denver")

    assert [p.label for p in places] == ["Denver, CO", "Pilot"]
    assert places[0].sublabel == "United States"
    assert places[1].sublabel == "Denver, CO"


@respx.mock
async def test_photon_reverse(http: httpx.AsyncClient) -> None:
    respx.get(f"{PHOTON}/reverse").mock(
        return_value=httpx.Response(
            200,
            json={"features": [feature("x", "US", city="Laramie", state="Wyoming")]},
        )
    )
    place = await PhotonClient(http, base_url=PHOTON, backoff_s=0).reverse(LatLon(41.3, -105.6))
    assert place is not None
    assert place.label == "Laramie, WY"


def test_polyline_round_trip_matches_reference() -> None:
    # Reference vector from Google's documentation (precision 5).
    reference = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    points = decode(reference, precision=5)
    assert points == [LatLon(38.5, -120.2), LatLon(40.7, -120.95), LatLon(43.252, -126.453)]
    assert encode(points, precision=5) == reference
