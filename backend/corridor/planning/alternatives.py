"""Guaranteeing distinct route options (D20).

Routing providers may return fewer alternatives than requested, or alternatives that
differ only by a short stretch. We deduplicate by geometric overlap and, when needed,
generate extra candidates by routing through waypoints offset to either side of the
straight line between origin and destination.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np
import shapely
from shapely import LineString

from corridor.domain.geometry import LatLon
from corridor.domain.models import RouteCandidate
from corridor.planning.config import PlanningConfig
from corridor.planning.projection import LocalProjection

_SAMPLE_STEP_M = 1_000.0
VIA_OFFSET_MULTIPLIERS = (1, -1, 2, -2)


def share_near(line: LineString, other: LineString, tolerance_m: float) -> float:
    """Share of ``line`` (sampled every kilometre) lying within ``tolerance_m`` of ``other``."""
    count = max(2, math.ceil(line.length / _SAMPLE_STEP_M) + 1)
    samples = shapely.line_interpolate_point(line, np.linspace(0, line.length, count))
    return float(np.mean(shapely.distance(samples, other) <= tolerance_m))


def is_duplicate(a: LineString, b: LineString, config: PlanningConfig) -> bool:
    tolerance, share = config.similarity_tolerance_m, config.similarity_share
    return share_near(a, b, tolerance) >= share and share_near(b, a, tolerance) >= share


class DistinctRoutes:
    """Accumulates candidates, keeping only those that differ from the ones already kept."""

    def __init__(self, projection: LocalProjection, config: PlanningConfig) -> None:
        self._projection = projection
        self._config = config
        self._kept: list[tuple[RouteCandidate, LineString]] = []

    @property
    def routes(self) -> list[RouteCandidate]:
        return [candidate for candidate, _ in self._kept]

    def __len__(self) -> int:
        return len(self._kept)

    def offer(self, candidate: RouteCandidate) -> bool:
        if self._kept and candidate.duration_s > self._config.max_detour_ratio * min(
            c.duration_s for c, _ in self._kept
        ):
            return False
        line = self._projection.line(candidate.points)
        if any(is_duplicate(line, kept, self._config) for _, kept in self._kept):
            return False
        self._kept.append((candidate, line))
        return True

    def offer_all(self, candidates: Iterable[RouteCandidate]) -> None:
        for candidate in candidates:
            self.offer(candidate)


def via_points(
    origin: LatLon,
    destination: LatLon,
    projection: LocalProjection,
    config: PlanningConfig,
    multipliers: Sequence[int] = VIA_OFFSET_MULTIPLIERS,
) -> list[LatLon]:
    """Waypoints perpendicular to the origin→destination line, through its midpoint."""
    (x0, y0), (x1, y1) = projection.to_xy(origin), projection.to_xy(destination)
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        return []
    offset = min(config.via_offset_ratio * length, config.via_offset_cap_m)
    nx, ny = -dy / length, dx / length
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    xs = np.array([mx + nx * offset * k for k in multipliers])
    ys = np.array([my + ny * offset * k for k in multipliers])
    return projection.to_latlon(xs, ys)
