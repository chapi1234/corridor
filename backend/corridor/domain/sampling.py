"""Checkpoint placement along a route (D1, D11)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from corridor.domain.geometry import LatLon, Polyline
from corridor.domain.timeline import TimeProfile

_EPSILON_M = 1e-6


@dataclass(frozen=True, slots=True)
class CheckpointPosition:
    index: int
    distance_m: float
    owned_m: float
    """Length of road this checkpoint represents when summing miles per risk level."""
    point: LatLon
    elapsed_s: float


def sample_distances(total_m: float, interval_m: float) -> list[float]:
    """Distances of checkpoints: every ``interval_m`` from the origin, plus the destination."""
    if total_m <= 0:
        raise ValueError("Route length must be positive")
    if interval_m <= 0:
        raise ValueError("Sampling interval must be positive")

    count = math.floor(total_m / interval_m + _EPSILON_M)
    distances = [i * interval_m for i in range(count + 1)]
    if total_m - distances[-1] > _EPSILON_M:
        distances.append(total_m)
    else:
        distances[-1] = total_m
    return distances


def owned_lengths(distances: Sequence[float]) -> list[float]:
    """Assign each checkpoint the road between the midpoints to its neighbours.

    Every metre of the route is attributed to exactly one checkpoint, so the result
    sums to the route length. Endpoints own half of their single adjacent segment.
    """
    if len(distances) < 2:
        raise ValueError("Need at least two checkpoints")
    midpoints = [(a + b) / 2 for a, b in pairwise(distances)]
    bounds = [distances[0], *midpoints, distances[-1]]
    return [hi - lo for lo, hi in pairwise(bounds)]


def place_checkpoints(
    polyline: Polyline, profile: TimeProfile, interval_m: float
) -> list[CheckpointPosition]:
    distances = sample_distances(polyline.total_m, interval_m)
    owned = owned_lengths(distances)
    return [
        CheckpointPosition(
            index=i,
            distance_m=d,
            owned_m=owned[i],
            point=polyline.point_at(d),
            elapsed_s=profile.elapsed_at(d),
        )
        for i, d in enumerate(distances)
    ]
