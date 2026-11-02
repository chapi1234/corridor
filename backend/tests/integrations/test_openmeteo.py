import copy
import math
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from corridor.domain.geometry import LatLon
from corridor.integrations.openmeteo import OpenMeteoClient, parse_series
from corridor.planning.errors import IncompleteForecastError, UpstreamServiceError
from tests.conftest import load_fixture

BASE = "https://open-meteo.test/v1/forecast"
DENVER = LatLon(39.74, -104.99)
CHICAGO = LatLon(41.88, -87.63)
START = datetime(2026, 11, 2, 12, tzinfo=UTC)
END = START + timedelta(hours=2)


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield OpenMeteoClient(http, base_url=BASE, batch_size=1, backoff_s=0)


def test_parses_recorded_response() -> None:
    denver, chicago = load_fixture("open_meteo_two_points.json")

    series = parse_series(chicago)

    assert series.start == START
    assert len(series) == 3
    assert series.gust_mph[0] == pytest.approx(18.0)
    assert series.rain_in_hr[1] == pytest.approx(0.004)
    assert series.weather_code[1] == 51
    assert parse_series(denver).temperature_f[0] == pytest.approx(52.3)


def test_converts_metric_units() -> None:
    payload = copy.deepcopy(load_fixture("open_meteo_two_points.json")[0])
    payload["hourly_units"] |= {
        "wind_gusts_10m": "km/h",
        "snowfall": "cm",
        "rain": "mm",
        "showers": "mm",
        "temperature_2m": "°C",
    }
    payload["hourly"] |= {
        "wind_gusts_10m": [100.0, 0, 0],
        "snowfall": [2.54, 0, 0],
        "rain": [25.4, 0, 0],
        "showers": [None, 0, 0],
        "temperature_2m": [0.0, 0, 0],
    }

    series = parse_series(payload)

    assert series.gust_mph[0] == pytest.approx(62.137, rel=1e-4)
    assert series.snow_in_hr[0] == pytest.approx(1.0)
    assert series.rain_in_hr[0] == pytest.approx(1.0)
    assert series.temperature_f[0] == pytest.approx(32.0)


def test_missing_values_become_nan() -> None:
    payload = copy.deepcopy(load_fixture("open_meteo_two_points.json")[0])
    payload["hourly"]["wind_gusts_10m"][1] = None
    payload["hourly"]["rain"][2] = None
    payload["hourly"]["showers"][2] = None

    series = parse_series(payload)

    assert math.isnan(series.gust_mph[1])
    assert math.isnan(series.rain_in_hr[2])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["hourly_units"].update(wind_gusts_10m="furlongs"),
        lambda p: p.pop("hourly"),
        lambda p: p["hourly"].update(time=[1, 2, 3]),
    ],
    ids=["unknown-unit", "missing-block", "gappy-times"],
)
def test_rejects_malformed_payloads(mutate) -> None:
    payload = copy.deepcopy(load_fixture("open_meteo_two_points.json")[0])
    mutate(payload)
    with pytest.raises(UpstreamServiceError):
        parse_series(payload)


@respx.mock
async def test_batches_and_keys_by_requested_point(client: OpenMeteoClient) -> None:
    denver, chicago = load_fixture("open_meteo_two_points.json")
    route = respx.get(BASE).mock(
        side_effect=lambda request: httpx.Response(
            200, json=denver if request.url.params["latitude"] == "39.7400" else chicago
        )
    )

    result = await client.hourly_forecast([DENVER, CHICAGO, DENVER], start=START, end=END)

    assert route.call_count == 2
    assert set(result) == {DENVER, CHICAGO}
    params = route.calls.last.request.url.params
    assert params["start_hour"] == "2026-11-02T12:00"
    assert params["end_hour"] == "2026-11-02T14:00"
    assert params["precipitation_unit"] == "inch"


@respx.mock
async def test_count_mismatch_is_an_error() -> None:
    respx.get(BASE).mock(
        return_value=httpx.Response(200, json=load_fixture("open_meteo_two_points.json"))
    )
    async with httpx.AsyncClient() as http:
        client = OpenMeteoClient(http, base_url=BASE, batch_size=5, backoff_s=0)
        with pytest.raises(UpstreamServiceError, match="mismatch"):
            await client.hourly_forecast([DENVER], start=START, end=END)


@respx.mock
async def test_rate_limit_is_not_retried_and_keeps_successful_batches(
    client: OpenMeteoClient,
) -> None:
    denver, _ = load_fixture("open_meteo_two_points.json")
    limited = httpx.Response(
        429, json={"error": True, "reason": "Minutely API request limit exceeded."}
    )
    route = respx.get(BASE).mock(
        side_effect=lambda request: (
            httpx.Response(200, json=denver)
            if request.url.params["latitude"] == "39.7400"
            else limited
        )
    )

    with pytest.raises(IncompleteForecastError) as caught:
        await client.hourly_forecast([DENVER, CHICAGO], start=START, end=END)

    assert route.call_count == 2  # one call per batch: the 429 was not retried
    assert caught.value.rate_limited
    assert set(caught.value.partial) == {DENVER}


@respx.mock
async def test_concurrency_rejection_is_retried(client: OpenMeteoClient) -> None:
    denver, _ = load_fixture("open_meteo_two_points.json")
    busy = httpx.Response(429, json={"reason": "Too many concurrent requests", "error": True})
    route = respx.get(BASE).mock(side_effect=[busy, busy, httpx.Response(200, json=denver)])

    result = await client.hourly_forecast([DENVER], start=START, end=END)

    assert route.call_count == 3
    assert DENVER in result


@respx.mock
async def test_persistent_concurrency_rejection_gives_up(client: OpenMeteoClient) -> None:
    busy = httpx.Response(429, json={"reason": "Too many concurrent requests", "error": True})
    route = respx.get(BASE).mock(return_value=busy)
    with pytest.raises(IncompleteForecastError):
        await client.hourly_forecast([DENVER], start=START, end=END)
    assert route.call_count == 5


@respx.mock
async def test_retry_after_header_is_reported(client: OpenMeteoClient) -> None:
    respx.get(BASE).mock(return_value=httpx.Response(429, headers={"Retry-After": "42"}))
    with pytest.raises(IncompleteForecastError) as caught:
        await client.hourly_forecast([DENVER], start=START, end=END)
    assert caught.value.retry_after_s == 42
    assert caught.value.partial == {}


def test_parses_optional_direction_and_visibility() -> None:
    payload = copy.deepcopy(load_fixture("open_meteo_two_points.json")[0])
    payload["hourly_units"] |= {"wind_direction_10m": "°", "visibility": "ft"}
    payload["hourly"] |= {"wind_direction_10m": [270, None, 90], "visibility": [5280, 2640, None]}

    series = parse_series(payload)

    assert series.wind_direction_deg[0] == 270
    assert math.isnan(series.wind_direction_deg[1])
    assert series.visibility_mi[:2] == pytest.approx((1.0, 0.5))


def test_unknown_visibility_unit_drops_visibility_only() -> None:
    payload = copy.deepcopy(load_fixture("open_meteo_two_points.json")[0])
    payload["hourly_units"]["visibility"] = "furlong"
    payload["hourly"]["visibility"] = [1, 2, 3]

    assert parse_series(payload).visibility_mi == ()
