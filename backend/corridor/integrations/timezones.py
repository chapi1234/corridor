"""Offline coordinate → IANA time zone lookup (D14)."""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

from corridor.domain.geometry import LatLon


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    return TimezoneFinder(in_memory=True)


def timezone_at(point: LatLon) -> ZoneInfo:
    name = _finder().timezone_at(lng=point.lon, lat=point.lat)
    return ZoneInfo(name or "UTC")
