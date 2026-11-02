"""Composition root: wires concrete providers into the planning service.

Views resolve providers through these factories so tests can substitute fakes.
TomTom (truck-aware) is used when ``TOMTOM_API_KEY`` is set; otherwise the keyless
OSRM + Photon fallbacks keep the app fully functional for development and demos.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from django.conf import settings
from django.core.cache import cache

from corridor.integrations.cache import (
    CachedAlertsProvider,
    CachedGeocoder,
    CachedWeatherProvider,
)
from corridor.integrations.http import DEFAULT_TIMEOUT
from corridor.integrations.nws import NwsAlertsClient
from corridor.integrations.openmeteo import OpenMeteoClient
from corridor.integrations.osrm import OsrmClient
from corridor.integrations.photon import PhotonClient
from corridor.integrations.timezones import timezone_at
from corridor.integrations.tomtom import TomTomClient
from corridor.planning.ports import Geocoder, RoutingProvider
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
        routing = _routing_provider(http)
        weather = CachedWeatherProvider(
            OpenMeteoClient(
                http,
                base_url=settings.OPEN_METEO_BASE_URL,
                api_key=settings.OPEN_METEO_API_KEY,
            ),
            cache,
        )
        alerts = CachedAlertsProvider(NwsAlertsClient(http, base_url=settings.NWS_BASE_URL), cache)
        yield PlanningService(routing, weather, alerts=alerts, timezone_at=timezone_at)


@asynccontextmanager
async def geocoder() -> AsyncIterator[Geocoder]:
    async with _http_client() as http:
        inner: Geocoder = (
            TomTomClient(http, api_key=settings.TOMTOM_API_KEY, base_url=settings.TOMTOM_BASE_URL)
            if settings.TOMTOM_API_KEY
            else PhotonClient(http, base_url=settings.PHOTON_BASE_URL)
        )
        yield CachedGeocoder(inner, cache)


def _routing_provider(http: httpx.AsyncClient) -> RoutingProvider:
    if settings.TOMTOM_API_KEY:
        return TomTomClient(
            http, api_key=settings.TOMTOM_API_KEY, base_url=settings.TOMTOM_BASE_URL
        )
    return OsrmClient(http, base_url=settings.OSRM_BASE_URL)
