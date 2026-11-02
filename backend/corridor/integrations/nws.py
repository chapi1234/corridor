"""National Weather Service active alerts (https://www.weather.gov/documentation/services-web-api).

Most alerts are issued for forecast zones and carry no polygon, so each location is asked
for the alerts covering it (``?point=``) and NWS resolves the zones. Points outside NWS
coverage (Canada, offshore) answer 400; they simply have no alerts.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Final

import httpx

from corridor.domain.alerts import AlertSeverity, WeatherAlert, road_hazard_category
from corridor.domain.geometry import LatLon
from corridor.integrations.http import get_json
from corridor.planning.errors import UpstreamServiceError

SERVICE: Final = "nws"
_OUTSIDE_COVERAGE: Final = frozenset({400, 404})


class NwsAlertsClient:
    def __init__(
        self, http: httpx.AsyncClient, *, base_url: str, max_concurrency: int = 16
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def active_alerts(
        self, points: Sequence[LatLon]
    ) -> dict[LatLon, tuple[WeatherAlert, ...]]:
        """Road-relevant alerts per point. Failed points are absent from the result;
        if every point fails, the first failure is raised."""
        unique = list(dict.fromkeys(points))
        outcomes = await asyncio.gather(*(self._point(p) for p in unique), return_exceptions=True)
        result: dict[LatLon, tuple[WeatherAlert, ...]] = {}
        failure: UpstreamServiceError | None = None
        for point, outcome in zip(unique, outcomes, strict=True):
            if isinstance(outcome, UpstreamServiceError):
                failure = failure or outcome
            elif isinstance(outcome, BaseException):
                raise outcome
            else:
                result[point] = outcome
        if failure is not None and not result:
            raise failure
        return result

    async def _point(self, point: LatLon) -> tuple[WeatherAlert, ...]:
        async with self._semaphore:
            try:
                data = await get_json(
                    self._http,
                    f"{self._base_url}/alerts/active",
                    service=SERVICE,
                    params={"point": f"{point.lat:.4f},{point.lon:.4f}", "status": "actual"},
                )
            except UpstreamServiceError as exc:
                if exc.status in _OUTSIDE_COVERAGE:
                    return ()
                raise
        features = data.get("features", []) if isinstance(data, dict) else []
        return tuple(
            alert
            for feature in features
            if (alert := parse_alert(feature.get("properties", {}))) is not None
        )


def parse_alert(props: Mapping[str, Any]) -> WeatherAlert | None:
    """A road-relevant alert from CAP properties, or ``None`` for anything to ignore."""
    event = str(props.get("event", ""))
    category = road_hazard_category(event)
    if category is None or props.get("messageType") == "Cancel":
        return None
    try:
        severity = AlertSeverity(str(props.get("severity", "")).lower())
    except ValueError:
        severity = AlertSeverity.UNKNOWN
    return WeatherAlert(
        id=str(props.get("id", "")),
        event=event,
        category=category,
        severity=severity,
        headline=str(props.get("headline") or event),
        area=str(props.get("areaDesc", "")),
        starts=_time(props.get("onset") or props.get("effective")),
        ends=_time(props.get("ends") or props.get("expires")),
    )


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
