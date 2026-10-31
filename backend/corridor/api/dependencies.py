"""Composition root: wires concrete providers into the planning service.

Views resolve providers through these factories so tests can substitute fakes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from django.conf import settings
from django.core.cache import cache

from corridor.integrations.cache import CachedGeocoder, CachedWeatherProvider
from corridor.integrations.http import DEFAULT_TIMEOUT
from corridor.integrations.openmeteo import OpenMeteoClient
from corridor.integrations.timezones import timezone_at
from corridor.integrations.tomtom import TomTomClient
from corridor.planning.ports import Geocoder
from corridor.planning.service import PlanningService

USER_AGENT = "corridor/1.0 (+https://github.com/)"


@asynccontextmanager
async def _http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}
    ) as client:
        yield client


@asynccontextmanager
async def planning_service() -> AsyncIterator[PlanningService]:
    async with _http_client() as http:
        routing = TomTomClient(
            http, api_key=settings.TOMTOM_API_KEY, base_url=settings.TOMTOM_BASE_URL
        )
        weather = CachedWeatherProvider(
            OpenMeteoClient(
                http,
                base_url=settings.OPEN_METEO_BASE_URL,
                api_key=settings.OPEN_METEO_API_KEY,
            ),
            cache,
        )
        yield PlanningService(routing, weather, timezone_at=timezone_at)


@asynccontextmanager
async def geocoder() -> AsyncIterator[Geocoder]:
    async with _http_client() as http:
        client = TomTomClient(
            http, api_key=settings.TOMTOM_API_KEY, base_url=settings.TOMTOM_BASE_URL
        )
        yield CachedGeocoder(client, cache)
