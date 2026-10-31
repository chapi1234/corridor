"""Interfaces the planning service depends on. Implementations live in ``integrations``."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from corridor.domain.geometry import LatLon
from corridor.domain.models import Place, RouteCandidate
from corridor.domain.weather import HourlySeries


class RoutingProvider(Protocol):
    @property
    def display_name(self) -> str:
        """Shown to users as the source of route data."""
        ...

    async def calculate_routes(
        self,
        waypoints: Sequence[LatLon],
        *,
        depart_at: datetime,
        gross_weight_kg: float,
        alternatives: int,
    ) -> list[RouteCandidate]:
        """Truck routes through ``waypoints`` in order; the first result is the provider's best.

        Raises ``RouteNotFoundError`` when no route exists and ``UpstreamServiceError`` on failure.
        """
        ...


class WeatherProvider(Protocol):
    async def hourly_forecast(
        self, points: Sequence[LatLon], *, start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        """Hourly series covering ``start``..``end`` (inclusive, UTC hours) keyed by input point."""
        ...


class Geocoder(Protocol):
    async def search(
        self, query: str, *, near: LatLon | None = None, limit: int = 6
    ) -> list[Place]: ...

    async def reverse(self, point: LatLon) -> Place | None: ...
