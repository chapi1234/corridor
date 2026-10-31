"""Photon (OpenStreetMap) geocoder: the keyless fallback for search and reverse lookups.

https://photon.komoot.io — supports typeahead, unlike Nominatim's usage policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

import httpx

from corridor.domain.geometry import LatLon
from corridor.domain.models import Place
from corridor.integrations.http import get_json

SERVICE: Final = "photon"
SUPPORTED_COUNTRIES: Final = frozenset({"US", "CA"})
_OVERFETCH: Final = 3
"""Photon has no country filter; fetch extra results and filter to the US and Canada."""

US_STATE_CODES: Final[Mapping[str, str]] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}  # fmt: skip


class PhotonClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str = "https://photon.komoot.io",
        backoff_s: float = 0.4,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._backoff_s = backoff_s

    async def search(
        self, query: str, *, near: LatLon | None = None, limit: int = 6
    ) -> list[Place]:
        params: dict[str, str | int | float] = {"q": query, "limit": limit * _OVERFETCH}
        if near is not None:
            params |= {"lat": near.lat, "lon": near.lon}
        data = await self._get("/api/", params)
        places = [
            parse_feature(f)
            for f in data.get("features", [])
            if f.get("properties", {}).get("countrycode") in SUPPORTED_COUNTRIES
        ]
        return list(dict.fromkeys(places))[:limit]

    async def reverse(self, point: LatLon) -> Place | None:
        data = await self._get("/reverse", {"lat": point.lat, "lon": point.lon})
        features = data.get("features") or []
        if not features:
            return None
        return Place(label=_locality(features[0]["properties"]), point=point)

    async def _get(self, path: str, params: Mapping[str, str | int | float]) -> Any:
        return await get_json(
            self._http,
            f"{self._base_url}{path}",
            service=SERVICE,
            params=params,
            backoff_s=self._backoff_s,
        )


def parse_feature(feature: Mapping[str, Any]) -> Place:
    props = feature["properties"]
    lon, lat = feature["geometry"]["coordinates"]
    if _is_settlement(props):
        label, sublabel_parts = _locality(props), [props.get("county"), props.get("country")]
    else:
        label = str(props.get("name") or _locality(props))
        sublabel_parts = [_locality(props), props.get("country")]
    return Place(
        label=label,
        sublabel=", ".join(p for p in sublabel_parts if p),
        point=LatLon(lat, lon),
        id=f"osm:{props.get('osm_type', '')}{props.get('osm_id', '')}",
    )


def _is_settlement(props: Mapping[str, Any]) -> bool:
    return props.get("osm_key") == "place"


def _locality(props: Mapping[str, Any]) -> str:
    if _is_settlement(props):
        city = props.get("name")
    else:
        city = props.get("city") or props.get("town") or props.get("village") or props.get("county")
    state = props.get("state")
    region = US_STATE_CODES.get(state, state) if state else None
    return ", ".join(str(p) for p in (city, region) if p)
