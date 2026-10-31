from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from corridor.domain.geometry import LatLon
from corridor.domain.models import Place
from corridor.domain.weather import HourlySeries
from corridor.integrations.cache import CachedGeocoder, CachedWeatherProvider
from corridor.integrations.timezones import timezone_at

START = datetime(2026, 11, 3, 12, tzinfo=UTC)
END = START + timedelta(hours=1)


def series() -> HourlySeries:
    v = (1.0, 2.0)
    return HourlySeries(START, v, v, v, v, v, (0, 0))


class CountingWeather:
    def __init__(self) -> None:
        self.requested: list[list[LatLon]] = []

    async def hourly_forecast(
        self, points: Sequence[LatLon], *, start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        self.requested.append(list(points))
        return {p: series() for p in points}


class CountingGeocoder:
    def __init__(self) -> None:
        self.calls = 0

    async def search(
        self, query: str, *, near: LatLon | None = None, limit: int = 6
    ) -> list[Place]:
        self.calls += 1
        return [Place("Denver, CO", LatLon(39.7, -105))]

    async def reverse(self, point: LatLon) -> Place | None:
        self.calls += 1
        return Place("Laramie, WY", point)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


async def test_weather_cache_only_fetches_missing_points() -> None:
    inner = CountingWeather()
    cached = CachedWeatherProvider(inner, cache)
    a, b = LatLon(39, -105), LatLon(40, -100)

    await cached.hourly_forecast([a], start=START, end=END)
    result = await cached.hourly_forecast([a, b], start=START, end=END)

    assert inner.requested == [[a], [b]]
    assert set(result) == {a, b}


async def test_geocoder_cache() -> None:
    inner = CountingGeocoder()
    cached = CachedGeocoder(inner, cache)

    await cached.search(" Denver ")
    await cached.search("denver")
    await cached.reverse(LatLon(41.311, -105.591))
    await cached.reverse(LatLon(41.312, -105.592))

    assert inner.calls == 2


@pytest.mark.parametrize(
    ("point", "zone"),
    [
        (LatLon(39.7392, -104.9903), "America/Denver"),
        (LatLon(41.8781, -87.6298), "America/Chicago"),
        (LatLon(0, -150), "Etc/GMT+10"),
    ],
)
def test_timezone_at(point: LatLon, zone: str) -> None:
    assert timezone_at(point).key == zone
