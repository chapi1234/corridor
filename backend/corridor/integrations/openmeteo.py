"""Open-Meteo hourly forecast client (https://open-meteo.com/en/docs).

Locations are fetched in batches (one request carries many coordinates) and run
concurrently. Units are requested in US customary, but the response's ``hourly_units``
block is always honoured and converted, so a provider-side default change cannot
silently corrupt risk classification.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from itertools import batched, pairwise
from typing import Any, Final

import httpx

from corridor.domain.geometry import LatLon
from corridor.domain.weather import UNKNOWN_WEATHER_CODE, HourlySeries
from corridor.integrations.http import get_json
from corridor.planning.errors import UpstreamServiceError

SERVICE: Final = "open-meteo"
HOURLY_VARIABLES: Final = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
    "temperature_2m",
    "weather_code",
)

_TO_MPH: Final[Mapping[str, float]] = {
    "mp/h": 1.0,
    "mph": 1.0,
    "km/h": 0.621371,
    "m/s": 2.236936,
    "kn": 1.150779,
}
_TO_INCHES: Final[Mapping[str, float]] = {"inch": 1.0, "in": 1.0, "mm": 1 / 25.4, "cm": 1 / 2.54}
_TO_FAHRENHEIT: Final[Mapping[str, Callable[[float], float]]] = {
    "°F": lambda f: f,
    "°C": lambda c: c * 9 / 5 + 32,
}


class OpenMeteoClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str,
        api_key: str = "",
        batch_size: int = 40,
        max_concurrency: int = 6,
        backoff_s: float = 0.4,
    ) -> None:
        self._http = http
        self._base_url = base_url
        self._api_key = api_key
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._backoff_s = backoff_s

    async def hourly_forecast(
        self, points: Sequence[LatLon], *, start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        unique = list(dict.fromkeys(points))
        batches = await asyncio.gather(
            *(self._fetch_batch(batch, start, end) for batch in batched(unique, self._batch_size))
        )
        return {point: series for batch in batches for point, series in batch.items()}

    async def _fetch_batch(
        self, points: Sequence[LatLon], start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        params: dict[str, str | int | float] = {
            "latitude": ",".join(f"{p.lat:.4f}" for p in points),
            "longitude": ",".join(f"{p.lon:.4f}" for p in points),
            "hourly": ",".join(HOURLY_VARIABLES),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "temperature_unit": "fahrenheit",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "start_hour": _format_hour(start),
            "end_hour": _format_hour(end),
        }
        if self._api_key:
            params["apikey"] = self._api_key

        async with self._semaphore:
            data = await get_json(
                self._http,
                self._base_url,
                service=SERVICE,
                params=params,
                backoff_s=self._backoff_s,
            )
        payloads = data if isinstance(data, list) else [data]
        if len(payloads) != len(points):
            raise UpstreamServiceError(SERVICE, "location count mismatch in response")
        return {
            point: parse_series(payload) for point, payload in zip(points, payloads, strict=True)
        }


def parse_series(payload: Mapping[str, Any]) -> HourlySeries:
    try:
        hourly: Mapping[str, list[Any]] = payload["hourly"]
        units: Mapping[str, str] = payload["hourly_units"]
        times: list[int] = hourly["time"]
        to_mph = _TO_MPH[units["wind_speed_10m"]]
        gust_to_mph = _TO_MPH[units["wind_gusts_10m"]]
        rain_to_in = _TO_INCHES[units["rain"]]
        showers_to_in = _TO_INCHES[units["showers"]]
        snow_to_in = _TO_INCHES[units["snowfall"]]
        to_f = _TO_FAHRENHEIT[units["temperature_2m"]]
    except KeyError as exc:
        raise UpstreamServiceError(SERVICE, f"unexpected payload or unit: {exc}") from exc
    if not times:
        raise UpstreamServiceError(SERVICE, "empty hourly series")
    _require_contiguous_hours(times)

    def scaled(name: str, factor: float) -> tuple[float, ...]:
        return tuple(math.nan if v is None else v * factor for v in hourly[name])

    rain = tuple(
        _sum_known(r, s, rain_to_in, showers_to_in)
        for r, s in zip(hourly["rain"], hourly["showers"], strict=True)
    )
    return HourlySeries(
        start=datetime.fromtimestamp(times[0], UTC),
        wind_mph=scaled("wind_speed_10m", to_mph),
        gust_mph=scaled("wind_gusts_10m", gust_to_mph),
        rain_in_hr=rain,
        snow_in_hr=scaled("snowfall", snow_to_in),
        temperature_f=tuple(math.nan if v is None else to_f(v) for v in hourly["temperature_2m"]),
        weather_code=tuple(
            UNKNOWN_WEATHER_CODE if v is None else int(v) for v in hourly["weather_code"]
        ),
    )


def _sum_known(rain: float | None, showers: float | None, rain_k: float, showers_k: float) -> float:
    """Rain plus convective showers (D5); a missing component counts as zero unless both are."""
    if rain is None and showers is None:
        return math.nan
    return (rain or 0.0) * rain_k + (showers or 0.0) * showers_k


def _require_contiguous_hours(times: list[int]) -> None:
    step = int(timedelta(hours=1).total_seconds())
    if any(b - a != step for a, b in pairwise(times)):
        raise UpstreamServiceError(SERVICE, "hourly series is not contiguous")


def _format_hour(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:00")
