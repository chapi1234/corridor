"""OSRM routing client: the keyless fallback used when no TomTom key is configured.

OSRM's public profile is for cars, so routes are not truck-aware (no weight or height
restrictions). Geometry is requested as ``polyline6`` and ETA anchors are taken from the
route steps: per-segment annotations and GeoJSON make responses ~6x larger and the public
server serves them slowly.
https://project-osrm.org/docs/v5.24.0/api/#route-service
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from itertools import accumulate
from typing import Any, Final

import httpx

from corridor.domain.geometry import LatLon
from corridor.domain.models import RouteCandidate
from corridor.domain.timeline import TimeAnchor
from corridor.integrations.http import get_json
from corridor.integrations.polyline import decode
from corridor.planning.errors import RouteNotFoundError, UpstreamServiceError

SERVICE: Final = "osrm"
_NO_ROUTE_CODES: Final = ("NoRoute", "NoSegment")
"""No path exists, or a point is too far from any road."""
MAX_HIGHWAYS: Final = 3


class OsrmClient:
    display_name: Final = "OSRM (car profile; set TOMTOM_API_KEY for truck routing)"

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str = "https://router.project-osrm.org",
        backoff_s: float = 0.4,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._backoff_s = backoff_s

    async def calculate_routes(
        self,
        waypoints: Sequence[LatLon],
        *,
        depart_at: datetime,
        gross_weight_kg: float,
        alternatives: int,
    ) -> list[RouteCandidate]:
        coordinates = ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in waypoints)
        params: dict[str, str | int | float] = {
            "alternatives": alternatives if alternatives > 0 else "false",
            "overview": "full",
            "geometries": "polyline6",
            "steps": "true",
        }
        try:
            data = await get_json(
                self._http,
                f"{self._base_url}/route/v1/driving/{coordinates}",
                service=SERVICE,
                params=params,
                backoff_s=self._backoff_s,
            )
        except UpstreamServiceError as exc:
            # OSRM answers unroutable requests with HTTP 400 and a code in the body.
            if exc.status == 400 and any(code in exc.message for code in _NO_ROUTE_CODES):
                raise RouteNotFoundError("No route found between these places.") from exc
            raise
        if data.get("code") == "NoRoute" or not data.get("routes"):
            raise RouteNotFoundError("No route found between these places.")
        if data.get("code") != "Ok":
            raise UpstreamServiceError(SERVICE, str(data.get("message") or data.get("code")))

        has_via = len(waypoints) > 2
        return [
            parse_route(route, "via" if has_via else ("primary" if i == 0 else "alternative"))
            for i, route in enumerate(data["routes"])
        ]


def parse_route(route: Mapping[str, Any], source: str) -> RouteCandidate:
    try:
        points = decode(route["geometry"], precision=6)
        steps = [step for leg in route["legs"] for step in leg["steps"]]
        distances = [float(step["distance"]) for step in steps]
        durations = [float(step["duration"]) for step in steps]
    except (KeyError, TypeError, IndexError) as exc:
        raise UpstreamServiceError(SERVICE, f"unexpected route payload: {exc}") from exc

    anchors = tuple(
        TimeAnchor(d, t) for d, t in zip(accumulate(distances), accumulate(durations), strict=True)
    )
    return RouteCandidate(
        points=tuple(points),
        length_m=float(route["distance"]),
        duration_s=float(route["duration"]),
        anchors=anchors,
        highways=main_highways(steps),
        source=source,
    )


def main_highways(steps: Any) -> tuple[str, ...]:
    distance_by_ref: dict[str, float] = defaultdict(float)
    first_seen: dict[str, int] = {}
    for index, step in enumerate(steps):
        for ref in str(step.get("ref") or "").split(";"):
            name = _normalise_ref(ref)
            if name:
                distance_by_ref[name] += float(step.get("distance", 0))
                first_seen.setdefault(name, index)
    top = sorted(distance_by_ref, key=distance_by_ref.__getitem__, reverse=True)[:MAX_HIGHWAYS]
    return tuple(sorted(top, key=first_seen.__getitem__))


def _normalise_ref(ref: str) -> str:
    """``"I 70"`` → ``"I-70"``, ``"US 287"`` → ``"US-287"``."""
    parts = ref.strip().split()
    return "-".join(parts) if parts else ""
