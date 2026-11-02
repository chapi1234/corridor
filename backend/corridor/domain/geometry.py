"""Spherical geometry and distance-indexed polylines."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

EARTH_RADIUS_M: Final = 6_371_008.8


@dataclass(frozen=True, slots=True)
class LatLon:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0) or not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"Coordinate out of range: {self.lat}, {self.lon}")


def haversine_m(a: LatLon, b: LatLon) -> float:
    """Great-circle distance in meters."""
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    d_phi = phi2 - phi1
    d_lambda = math.radians(b.lon - a.lon)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    """Initial great-circle bearing from ``a`` to ``b``, clockwise from north in [0, 360)."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


class Polyline:
    """An ordered path with precomputed cumulative distances.

    Lookups by distance are O(log n). Interpolation inside a segment is linear in
    lat/lon, which is accurate for the short segments routing APIs return.
    """

    __slots__ = ("cumulative_m", "points")

    def __init__(self, points: Sequence[LatLon]) -> None:
        if len(points) < 2:
            raise ValueError("A polyline needs at least two points")
        cumulative = [0.0]
        for prev, cur in pairwise(points):
            cumulative.append(cumulative[-1] + haversine_m(prev, cur))
        self.points: tuple[LatLon, ...] = tuple(points)
        self.cumulative_m: tuple[float, ...] = tuple(cumulative)

    @property
    def total_m(self) -> float:
        return self.cumulative_m[-1]

    def point_at(self, distance_m: float) -> LatLon:
        """Position at ``distance_m`` along the path, clamped to its ends."""
        d = min(max(distance_m, 0.0), self.total_m)
        i = bisect_right(self.cumulative_m, d) - 1
        if i >= len(self.points) - 1:
            return self.points[-1]
        start, end = self.cumulative_m[i], self.cumulative_m[i + 1]
        if end == start:
            return self.points[i]
        t = (d - start) / (end - start)
        a, b = self.points[i], self.points[i + 1]
        return LatLon(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t)
