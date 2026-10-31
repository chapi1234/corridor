"""Value objects exchanged between providers and the planning service."""

from __future__ import annotations

from dataclasses import dataclass

from corridor.domain.geometry import LatLon
from corridor.domain.timeline import TimeAnchor


@dataclass(frozen=True, slots=True)
class Place:
    label: str
    point: LatLon
    sublabel: str = ""
    id: str = ""


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """A route as returned by a routing provider, before any weather analysis."""

    points: tuple[LatLon, ...]
    length_m: float
    duration_s: float
    anchors: tuple[TimeAnchor, ...]
    """Known (distance, elapsed time) pairs used to interpolate ETAs (D17)."""
    highways: tuple[str, ...]
    source: str
    """``primary``, ``alternative`` or ``via`` (generated through an offset waypoint)."""
