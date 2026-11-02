"""Distance → elapsed-time profiles along a route (D17)."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeAnchor:
    """A known point on a route: ``elapsed_s`` seconds after departure at ``distance_m``."""

    distance_m: float
    elapsed_s: float


class TimeProfile:
    """Piecewise-linear mapping from distance along a route to elapsed driving time.

    Built from the routing provider's per-instruction travel times so ETAs reflect
    road speeds and traffic rather than an average speed. Anchors are normalised:
    clamped to the route, sorted, bracketed by the start and end of the trip, and made
    monotonic so that time never runs backwards.
    """

    __slots__ = ("_distances", "_elapsed")

    def __init__(self, anchors: Iterable[TimeAnchor], total_m: float, total_s: float) -> None:
        if total_m <= 0 or total_s <= 0:
            raise ValueError("Route length and duration must be positive")

        inner = sorted(
            (
                TimeAnchor(a.distance_m, a.elapsed_s)
                for a in anchors
                if 0.0 < a.distance_m < total_m and a.elapsed_s >= 0.0
            ),
            key=lambda a: a.distance_m,
        )
        distances, elapsed = [0.0], [0.0]
        for anchor in inner:
            if anchor.distance_m == distances[-1]:
                continue
            distances.append(anchor.distance_m)
            elapsed.append(max(elapsed[-1], anchor.elapsed_s))
        distances.append(total_m)
        elapsed.append(max(elapsed[-1], total_s))

        self._distances: tuple[float, ...] = tuple(distances)
        self._elapsed: tuple[float, ...] = tuple(elapsed)

    @classmethod
    def constant_speed(cls, total_m: float, total_s: float) -> TimeProfile:
        return cls((), total_m, total_s)

    @property
    def total_s(self) -> float:
        return self._elapsed[-1]

    def elapsed_at(self, distance_m: float) -> float:
        d = min(max(distance_m, 0.0), self._distances[-1])
        i = bisect_right(self._distances, d) - 1
        if i >= len(self._distances) - 1:
            return self._elapsed[-1]
        d0, d1 = self._distances[i], self._distances[i + 1]
        t0, t1 = self._elapsed[i], self._elapsed[i + 1]
        return t0 + (t1 - t0) * (d - d0) / (d1 - d0)

    def distance_at(self, elapsed_s: float) -> float:
        """Inverse of :meth:`elapsed_at`: the first distance reached after ``elapsed_s``."""
        t = min(max(elapsed_s, 0.0), self._elapsed[-1])
        i = bisect_left(self._elapsed, t)
        if i == 0:
            return self._distances[0]
        t0, t1 = self._elapsed[i - 1], self._elapsed[i]
        d0, d1 = self._distances[i - 1], self._distances[i]
        return d0 + (d1 - d0) * (t - t0) / (t1 - t0)
