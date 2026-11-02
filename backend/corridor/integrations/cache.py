"""Caching decorators for providers, backed by the Django cache (Redis in production).

Weather is cached per location so overlapping trips and repeated plans share series;
this is what keeps us comfortably inside Open-Meteo's per-location rate limits.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Final

from django.core.cache import BaseCache

from corridor.domain.alerts import WeatherAlert
from corridor.domain.geometry import LatLon
from corridor.domain.models import Place
from corridor.domain.weather import HourlySeries
from corridor.planning.errors import IncompleteForecastError
from corridor.planning.ports import AlertsProvider, Geocoder, WeatherProvider

WEATHER_TTL_S: Final = 30 * 60
GEOCODE_TTL_S: Final = 24 * 60 * 60
REVERSE_TTL_S: Final = 7 * 24 * 60 * 60
ALERTS_TTL_S: Final = 5 * 60
"""NWS updates alerts continuously; a short TTL only absorbs repeated plans."""
_KEY_VERSION: Final = "v1"


class CachedWeatherProvider:
    def __init__(self, inner: WeatherProvider, cache: BaseCache, *, ttl_s: int = WEATHER_TTL_S):
        self._inner = inner
        self._cache = cache
        self._ttl_s = ttl_s

    async def hourly_forecast(
        self, points: Sequence[LatLon], *, start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        keys = {point: _weather_key(point, start, end) for point in dict.fromkeys(points)}
        cached: dict[str, HourlySeries] = await self._cache.aget_many(keys.values())
        result = {point: cached[key] for point, key in keys.items() if key in cached}

        missing = [point for point in keys if point not in result]
        if missing:
            try:
                fetched = await self._inner.hourly_forecast(missing, start=start, end=end)
            except IncompleteForecastError as exc:
                await self._store(keys, exc.partial)
                raise
            await self._store(keys, fetched)
            result |= fetched
        return result

    async def _store(
        self, keys: Mapping[LatLon, str], series: Mapping[LatLon, HourlySeries]
    ) -> None:
        if series:
            await self._cache.aset_many({keys[p]: s for p, s in series.items()}, self._ttl_s)


class CachedAlertsProvider:
    def __init__(self, inner: AlertsProvider, cache: BaseCache, *, ttl_s: int = ALERTS_TTL_S):
        self._inner = inner
        self._cache = cache
        self._ttl_s = ttl_s

    async def active_alerts(
        self, points: Sequence[LatLon]
    ) -> dict[LatLon, tuple[WeatherAlert, ...]]:
        keys = {p: f"alerts:{_KEY_VERSION}:{p.lat:.4f},{p.lon:.4f}" for p in dict.fromkeys(points)}
        cached: dict[str, tuple[WeatherAlert, ...]] = await self._cache.aget_many(keys.values())
        result = {point: cached[key] for point, key in keys.items() if key in cached}
        missing = [point for point in keys if point not in result]
        if missing:
            fetched = await self._inner.active_alerts(missing)
            if fetched:
                await self._cache.aset_many(
                    {keys[p]: alerts for p, alerts in fetched.items()}, self._ttl_s
                )
            result |= fetched
        return result


class CachedGeocoder:
    def __init__(self, inner: Geocoder, cache: BaseCache) -> None:
        self._inner = inner
        self._cache = cache

    async def search(
        self, query: str, *, near: LatLon | None = None, limit: int = 6
    ) -> list[Place]:
        near_key = f"{near.lat:.1f},{near.lon:.1f}" if near else "-"
        key = f"geo:{_KEY_VERSION}:{query.strip().lower()}:{near_key}:{limit}"
        cached: list[Place] | None = await self._cache.aget(key)
        if cached is not None:
            return cached
        places = await self._inner.search(query, near=near, limit=limit)
        await self._cache.aset(key, places, GEOCODE_TTL_S)
        return places

    async def reverse(self, point: LatLon) -> Place | None:
        key = f"rev:{_KEY_VERSION}:{point.lat:.2f},{point.lon:.2f}"
        cached: Place | None = await self._cache.aget(key)
        if cached is not None:
            return cached
        place = await self._inner.reverse(point)
        if place is not None:
            await self._cache.aset(key, place, REVERSE_TTL_S)
        return place


def _weather_key(point: LatLon, start: datetime, end: datetime) -> str:
    fmt = "%Y%m%d%H"
    return (
        f"wx:{_KEY_VERSION}:{point.lat:.4f},{point.lon:.4f}:"
        f"{start.astimezone(UTC).strftime(fmt)}:{end.astimezone(UTC).strftime(fmt)}"
    )
