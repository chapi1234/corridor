"""TomTom Routing and Search clients.

Routing: https://developer.tomtom.com/routing-api/documentation/routing/calculate-route
Search:  https://developer.tomtom.com/search-api/documentation/search-service/fuzzy-search
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any, Final
from urllib.parse import quote

import httpx

from corridor.domain.geometry import LatLon
from corridor.domain.models import Place, RouteCandidate
from corridor.domain.timeline import TimeAnchor
from corridor.integrations.http import get_json
from corridor.planning.errors import RouteNotFoundError, UpstreamServiceError

SERVICE: Final = "tomtom"

# A typical US tractor + 53 ft trailer, used for restriction-aware truck routing.
VEHICLE_LENGTH_M: Final = 22.0
VEHICLE_WIDTH_M: Final = 2.6
VEHICLE_HEIGHT_M: Final = 4.1

MAX_HIGHWAYS: Final = 3


class TomTomClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        base_url: str = "https://api.tomtom.com",
        backoff_s: float = 0.4,
    ) -> None:
        if not api_key:
            raise UpstreamServiceError(SERVICE, "TOMTOM_API_KEY is not configured")
        self._http = http
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._backoff_s = backoff_s

    # ------------------------------------------------------------------ routing
    async def calculate_routes(
        self,
        waypoints: Sequence[LatLon],
        *,
        depart_at: datetime,
        gross_weight_kg: float,
        alternatives: int,
    ) -> list[RouteCandidate]:
        locations = ":".join(f"{p.lat:.6f},{p.lon:.6f}" for p in waypoints)
        params: dict[str, str | int | float] = {
            "key": self._api_key,
            "travelMode": "truck",
            "vehicleCommercial": "true",
            "vehicleWeight": round(gross_weight_kg),
            "vehicleLength": VEHICLE_LENGTH_M,
            "vehicleWidth": VEHICLE_WIDTH_M,
            "vehicleHeight": VEHICLE_HEIGHT_M,
            "routeType": "fastest",
            "traffic": "true",
            "departAt": depart_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "maxAlternatives": alternatives,
            "instructionsType": "coded",
            "routeRepresentation": "polyline",
        }
        try:
            data = await self._get(f"/routing/1/calculateRoute/{locations}/json", params)
        except UpstreamServiceError as exc:
            if exc.status == 400 and "NO_ROUTE_FOUND" in exc.message:
                raise RouteNotFoundError("No truck route found between these places.") from exc
            raise

        routes = data.get("routes") or []
        if not routes:
            raise RouteNotFoundError("No truck route found between these places.")
        has_via = len(waypoints) > 2
        return [
            parse_route(route, "via" if has_via else ("primary" if i == 0 else "alternative"))
            for i, route in enumerate(routes)
        ]

    # ------------------------------------------------------------------ search
    async def search(
        self, query: str, *, near: LatLon | None = None, limit: int = 6
    ) -> list[Place]:
        params: dict[str, str | int | float] = {
            "key": self._api_key,
            "typeahead": "true",
            "limit": limit,
            "countrySet": "US,CA",
            "idxSet": "Geo,PAD,Addr,POI",
        }
        if near is not None:
            params |= {"lat": near.lat, "lon": near.lon}
        data = await self._get(f"/search/2/search/{quote(query, safe='')}.json", params)
        return [parse_search_result(r) for r in data.get("results", [])]

    async def reverse(self, point: LatLon) -> Place | None:
        data = await self._get(
            f"/search/2/reverseGeocode/{point.lat:.6f},{point.lon:.6f}.json",
            {"key": self._api_key},
        )
        addresses = data.get("addresses") or []
        if not addresses:
            return None
        address = addresses[0].get("address", {})
        return Place(label=_locality_label(address), point=point)

    async def _get(self, path: str, params: Mapping[str, str | int | float]) -> Any:
        return await get_json(
            self._http,
            f"{self._base_url}{path}",
            service=SERVICE,
            params=params,
            backoff_s=self._backoff_s,
        )


# ---------------------------------------------------------------------- parsing
def parse_route(route: Mapping[str, Any], source: str) -> RouteCandidate:
    try:
        summary = route["summary"]
        points = _dedupe_consecutive(
            LatLon(p["latitude"], p["longitude"]) for leg in route["legs"] for p in leg["points"]
        )
        length_m = float(summary["lengthInMeters"])
        duration_s = float(summary["travelTimeInSeconds"])
    except (KeyError, TypeError) as exc:
        raise UpstreamServiceError(SERVICE, f"unexpected route payload: {exc}") from exc

    instructions = route.get("guidance", {}).get("instructions", [])
    anchors = tuple(
        TimeAnchor(float(i["routeOffsetInMeters"]), float(i["travelTimeInSeconds"]))
        for i in instructions
        if "routeOffsetInMeters" in i and "travelTimeInSeconds" in i
    )
    return RouteCandidate(
        points=points,
        length_m=length_m,
        duration_s=duration_s,
        anchors=anchors,
        highways=main_highways(instructions, length_m),
        source=source,
    )


def main_highways(instructions: Sequence[Mapping[str, Any]], length_m: float) -> tuple[str, ...]:
    """The road numbers covering the most distance, listed in driving order.

    An instruction's ``roadNumbers`` describe the road taken after it, so each road is
    credited with the distance up to the next instruction.
    """
    offsets = [float(i.get("routeOffsetInMeters", 0)) for i in instructions] + [length_m]
    distance_by_road: dict[str, float] = defaultdict(float)
    first_seen: dict[str, int] = {}
    for index, (instruction, (start, end)) in enumerate(
        zip(instructions, pairwise(offsets), strict=False)
    ):
        for road in instruction.get("roadNumbers", []):
            distance_by_road[road] += max(end - start, 0.0)
            first_seen.setdefault(road, index)
    top = sorted(distance_by_road, key=distance_by_road.__getitem__, reverse=True)[:MAX_HIGHWAYS]
    return tuple(sorted(top, key=first_seen.__getitem__))


def parse_search_result(result: Mapping[str, Any]) -> Place:
    address = result.get("address", {})
    position = result["position"]
    point = LatLon(position["lat"], position["lon"])
    freeform = address.get("freeformAddress", "")
    poi_name = result.get("poi", {}).get("name")

    if poi_name:
        label, sublabel = poi_name, freeform
    elif result.get("type") == "Geography":
        label, sublabel = _locality_label(address) or freeform, address.get("country", "")
    else:
        label, sublabel = freeform, address.get("country", "")
    return Place(label=label, sublabel=sublabel, point=point, id=str(result.get("id", "")))


def _locality_label(address: Mapping[str, Any]) -> str:
    city = address.get("municipality") or address.get("localName")
    region = address.get("countrySubdivision")
    if city and region:
        return f"{city}, {region}"
    return str(address.get("freeformAddress") or city or region or "")


def _dedupe_consecutive(points: Iterable[LatLon]) -> tuple[LatLon, ...]:
    result: list[LatLon] = []
    for point in points:
        if not result or result[-1] != point:
            result.append(point)
    return tuple(result)
