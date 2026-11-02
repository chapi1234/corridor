"""Open-Meteo hourly forecast client (https://open-meteo.com/en/docs).

Locations are fetched in batches (one request carries many coordinates) and run
concurrently. Units are requested in US customary, but the response's ``hourly_units``
block is always honoured and converted, so a provider-side default change cannot
silently corrupt risk classification.
"""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from itertools import batched, pairwise
from typing import Any, Final

import httpx

from corridor.domain.geometry import LatLon
from corridor.domain.weather import UNKNOWN_WEATHER_CODE, HourlySeries
from corridor.integrations.http import get_json
from corridor.planning.errors import IncompleteForecastError, UpstreamServiceError

SERVICE: Final = "open-meteo"
_CONCURRENCY_RETRIES: Final = 4
HOURLY_VARIABLES: Final = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
    "temperature_2m",
    "weather_code",
    "wind_direction_10m",
    "visibility",
)
"""Kept at 10 or fewer: Open-Meteo bills extra calls for requests with more variables."""

_TO_MPH: Final[Mapping[str, float]] = {
    "mp/h": 1.0,
    "mph": 1.0,
    "km/h": 0.621371,
    "m/s": 2.236936,
    "kn": 1.150779,
}
_TO_INCHES: Final[Mapping[str, float]] = {"inch": 1.0, "in": 1.0, "mm": 1 / 25.4, "cm": 1 / 2.54}
_TO_MILES: Final[Mapping[str, float]] = {"ft": 1 / 5280, "m": 1 / 1609.344, "km": 0.621371}
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
        max_concurrency: int = 3,
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
        outcomes = await asyncio.gather(
            *(self._fetch_batch(batch, start, end) for batch in batched(unique, self._batch_size)),
            return_exceptions=True,
        )
        result: dict[LatLon, HourlySeries] = {}
        failure: UpstreamServiceError | None = None
        for outcome in outcomes:
            if isinstance(outcome, UpstreamServiceError):
                failure = failure or outcome
            elif isinstance(outcome, BaseException):
                raise outcome
            else:
                result |= outcome
        if failure is not None:
            raise IncompleteForecastError(failure, result)
        return result

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
            data = await self._get(params)
        payloads = data if isinstance(data, list) else [data]
        if len(payloads) != len(points):
            raise UpstreamServiceError(SERVICE, "location count mismatch in response")
        return {
            point: parse_series(payload) for point, payload in zip(points, payloads, strict=True)
        }

    async def _get(self, params: Mapping[str, str | int | float]) -> Any:
        """GET, retrying only Open-Meteo's *concurrency* rejection.

        A 429 "Too many concurrent requests" clears as soon as another request finishes, so a
        short jittered wait is enough. The per-minute/hour/day quota 429s are never retried:
        waiting would only burn more quota (see ``integrations.http``).
        """
        for attempt in range(_CONCURRENCY_RETRIES + 1):
            try:
                return await get_json(
                    self._http,
                    self._base_url,
                    service=SERVICE,
                    params=params,
                    backoff_s=self._backoff_s,
                )
            except UpstreamServiceError as exc:
                if not (_is_concurrency_limit(exc) and attempt < _CONCURRENCY_RETRIES):
                    raise
            await asyncio.sleep(self._backoff_s * (2**attempt) * (1 + random.random()))
        raise AssertionError("unreachable")


def _is_concurrency_limit(exc: UpstreamServiceError) -> bool:
    return exc.status == 429 and "concurrent" in exc.message.lower()


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
        wind_direction_deg=scaled("wind_direction_10m", 1.0)
        if "wind_direction_10m" in hourly
        else (),
        visibility_mi=_optional_visibility(hourly, units),
    )


def _optional_visibility(
    hourly: Mapping[str, list[Any]], units: Mapping[str, str]
) -> tuple[float, ...]:
    """Visibility is advisory: an unknown unit drops it rather than failing the forecast."""
    factor = _TO_MILES.get(units.get("visibility", ""))
    if "visibility" not in hourly or factor is None:
        return ()
    return tuple(math.nan if v is None else v * factor for v in hourly["visibility"])


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
