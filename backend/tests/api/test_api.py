from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from corridor.api import dependencies
from corridor.api.serializers import PlanResponseSerializer
from corridor.domain.geometry import LatLon
from corridor.domain.models import Place
from corridor.planning.errors import RouteNotFoundError, UpstreamServiceError
from tests.fakes import make_service

PAYLOAD: dict[str, Any] = {
    "origin": {"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903},
    "destination": {"label": "Kansas City, MO", "lat": 39.0997, "lon": -94.5786},
    "departure_local": "2026-11-03T06:00",
    "load_lb": 42000,
    "interval_mi": 25,
}


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch):
    cache.clear()

    @asynccontextmanager
    async def fake_service() -> AsyncIterator[Any]:
        yield make_service()

    monkeypatch.setattr(dependencies, "planning_service", fake_service)
    yield
    cache.clear()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def post_plan(client: APIClient, **changes: Any):
    return client.post("/api/v1/plans", {**PAYLOAD, **changes}, format="json")


def test_plan_response_matches_published_schema(client: APIClient) -> None:
    response = post_plan(client)

    assert response.status_code == 200, response.content
    body = response.json()
    contract = PlanResponseSerializer(data=body)
    assert contract.is_valid(), contract.errors

    assert len(body["routes"]) == 3
    assert body["departure"]["local"] == "2026-11-03T06:00-07:00"
    assert body["departure"]["tz"] == "America/Denver"
    assert body["recommendation"]["route_id"] in {r["id"] for r in body["routes"]}
    assert body["heatmap"]["hours"] == 49
    checkpoint = body["routes"][0]["checkpoints"][1]
    assert checkpoint["mile"] == pytest.approx(25)
    assert checkpoint["risk"]["level"] == 0


def test_hours_of_service_adds_rest_stops(client: APIClient) -> None:
    plain = post_plan(client).json()["routes"][0]
    response = post_plan(client, hos=True)

    assert response.status_code == 200, response.content
    body = response.json()
    assert PlanResponseSerializer(data=body).is_valid()
    assert body["inputs"]["hos"] is True
    route = body["routes"][0]
    assert plain["rest_stops"] == []
    assert [r["kind"] for r in route["rest_stops"]] == ["break"]
    assert route["rest_stops"][0]["start_s"] == 8 * 3600
    assert route["driving_s"] == plain["driving_s"] == plain["duration_s"]
    assert route["duration_s"] == plain["duration_s"] + 1800
    last = route["checkpoints"][-1]
    assert last["elapsed_s"] == last["driving_s"] + 1800


def test_plan_is_cached_by_inputs(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    @asynccontextmanager
    async def counting_service() -> AsyncIterator[Any]:
        nonlocal calls
        calls += 1
        yield make_service()

    monkeypatch.setattr(dependencies, "planning_service", counting_service)
    post_plan(client)
    post_plan(client)
    post_plan(client, load_lb=10_000)

    assert calls == 2


def test_routes_include_an_alerts_list(client: APIClient) -> None:
    body = post_plan(client).json()
    assert all(route["alerts"] == [] for route in body["routes"])


def test_shared_plan_resolves_to_the_computed_snapshot(client: APIClient) -> None:
    plan = post_plan(client).json()
    cache.delete(f"plan:v1:{plan['plan_id']}")  # the 10-minute plan cache has expired

    response = client.get(f"/api/v1/plans/{plan['plan_id']}")

    assert response.status_code == 200
    assert response.json() == plan


def test_unknown_snapshot_is_a_404_problem(client: APIClient) -> None:
    response = client.get("/api/v1/plans/0123456789abcdef")

    assert response.status_code == 404
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["type"] == "/problems/snapshot-not-found"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"interval_mi": 15}, "interval_mi"),
        ({"load_lb": -1}, "load_lb"),
        ({"departure_local": "tomorrow"}, "departure_local"),
        ({"departure_local": "2026-11-03T06:00+02:00"}, "departure_local"),
        ({"origin": {"label": "x", "lat": 95, "lon": 0}}, "origin"),
    ],
)
def test_input_validation_returns_problem_details(
    client: APIClient, changes: dict[str, Any], field: str
) -> None:
    response = post_plan(client, **changes)

    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "/problems/validation"
    assert field in body["errors"]


def test_domain_validation_maps_to_422(client: APIClient) -> None:
    response = post_plan(client, departure_local="2026-11-02T06:00")

    assert response.status_code == 422
    assert response.json()["errors"] == {"departure": ["Departure time is in the past."]}


def test_upstream_rate_limit_maps_to_503_with_retry_after(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class RateLimitedService:
        async def build(self, _: Any) -> None:
            raise UpstreamServiceError("open-meteo", "HTTP 429", status=429)

    @asynccontextmanager
    async def limited() -> AsyncIterator[Any]:
        yield RateLimitedService()

    monkeypatch.setattr(dependencies, "planning_service", limited)
    response = post_plan(client)

    assert response.status_code == 503
    assert response["Retry-After"] == "60"
    body = response.json()
    assert body["type"] == "/problems/upstream-rate-limited"
    assert body["retry_after_s"] == 60


@pytest.mark.parametrize(
    ("reason", "title", "max_wait_s"),
    [
        ("Minutely API request limit exceeded.", "Weather provider is busy", 60),
        ("Hourly API request limit exceeded.", "Hourly weather limit reached", 3600),
        ("Daily API request limit exceeded.", "Daily weather limit reached", 86400),
    ],
)
def test_rate_limit_message_matches_the_quota(
    client: APIClient, monkeypatch: pytest.MonkeyPatch, reason: str, title: str, max_wait_s: int
) -> None:
    class RateLimitedService:
        async def build(self, _: Any) -> None:
            raise UpstreamServiceError("open-meteo", f"HTTP 429: {reason}", status=429)

    @asynccontextmanager
    async def limited() -> AsyncIterator[Any]:
        yield RateLimitedService()

    monkeypatch.setattr(dependencies, "planning_service", limited)
    response = post_plan(client)

    body = response.json()
    assert response.status_code == 503
    assert body["title"] == title
    assert 0 < body["retry_after_s"] <= max_wait_s
    assert response["Retry-After"] == str(body["retry_after_s"])


@pytest.mark.parametrize(
    ("error", "status", "kind"),
    [
        (RouteNotFoundError("No truck route found."), 422, "/problems/no-route"),
        (UpstreamServiceError("tomtom", "HTTP 503"), 502, "/problems/upstream-unavailable"),
    ],
)
def test_planning_failures_map_to_problems(
    client: APIClient, monkeypatch: pytest.MonkeyPatch, error: Exception, status: int, kind: str
) -> None:
    class FailingService:
        async def build(self, _: Any) -> None:
            raise error

    @asynccontextmanager
    async def failing() -> AsyncIterator[Any]:
        yield FailingService()

    monkeypatch.setattr(dependencies, "planning_service", failing)
    response = post_plan(client)

    assert response.status_code == status
    assert response.json()["type"] == kind


class FakeGeocoder:
    async def search(self, query: str, *, near: LatLon | None = None, limit: int = 6):
        return [Place("Denver, CO", LatLon(39.74, -104.99), "United States", "g1")]

    async def reverse(self, point: LatLon):
        return Place("Laramie, WY", point)


def test_geocode_and_reverse(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def fake() -> AsyncIterator[FakeGeocoder]:
        yield FakeGeocoder()

    monkeypatch.setattr(dependencies, "geocoder", fake)

    search = client.get("/api/v1/geocode", {"q": "denv"})
    assert search.status_code == 200
    assert search.json()["results"][0] == {
        "id": "g1",
        "label": "Denver, CO",
        "sublabel": "United States",
        "lat": 39.74,
        "lon": -104.99,
    }

    reverse = client.get("/api/v1/reverse", {"lat": 41.3, "lon": -105.6})
    assert reverse.json() == {"label": "Laramie, WY"}

    assert client.get("/api/v1/geocode", {"q": "d"}).status_code == 400


@pytest.mark.parametrize(
    ("lat", "lon", "tz"),
    [
        (39.74, -104.99, "America/Denver"),
        (40.71, -74.0, "America/New_York"),
        (47.56, -52.71, "America/St_Johns"),
    ],
)
def test_timezone_lookup(client: APIClient, lat: float, lon: float, tz: str) -> None:
    response = client.get("/api/v1/timezone", {"lat": lat, "lon": lon})
    assert response.status_code == 200
    assert response.json() == {"tz": tz}


def test_timezone_rejects_bad_coordinates(client: APIClient) -> None:
    assert client.get("/api/v1/timezone", {"lat": 95, "lon": 0}).status_code == 400


def test_health_and_schema(client: APIClient) -> None:
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/schema").status_code == 200
