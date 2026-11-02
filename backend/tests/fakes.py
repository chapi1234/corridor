"""Deterministic in-memory providers for planning and API tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from corridor.domain.geometry import LatLon, Polyline
from corridor.domain.models import Place, RouteCandidate
from corridor.domain.weather import HourlySeries
from corridor.planning.config import PlanningConfig
from corridor.planning.errors import IncompleteForecastError, UpstreamServiceError
from corridor.planning.service import PlanningService

DENVER = Place("Denver, CO", LatLon(39.7392, -104.9903))
KANSAS_CITY = Place("Kansas City, MO", LatLon(39.0997, -94.5786))
NOW = datetime(2026, 11, 3, 10, tzinfo=UTC)
SPEED_MPS = 26.0  # ~58 mph

# Weather as a function of location and time: (gust mph, rain in/hr, snow in/hr).
WeatherFn = Callable[[LatLon, datetime], tuple[float, float, float]]


def calm(_: LatLon, __: datetime) -> tuple[float, float, float]:
    return 10.0, 0.0, 0.0


def straight_route(
    waypoints: Sequence[LatLon], source: str, steps_per_leg: int = 60
) -> RouteCandidate:
    points = [waypoints[0]]
    for a, b in pairwise(waypoints):
        for i in range(1, steps_per_leg + 1):
            t = i / steps_per_leg
            points.append(LatLon(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t))
    length = Polyline(points).total_m
    return RouteCandidate(
        points=tuple(points),
        length_m=length,
        duration_s=length / SPEED_MPS,
        anchors=(),
        highways=("I-70",),
        source=source,
    )


@dataclass
class FakeRouting:
    """Returns the straight line for direct requests; via requests bend through the waypoint."""

    direct_alternatives: int = 0
    calls: list[tuple[LatLon, ...]] = field(default_factory=list)
    display_name: str = "Fake routing"

    async def calculate_routes(
        self,
        waypoints: Sequence[LatLon],
        *,
        depart_at: datetime,
        gross_weight_kg: float,
        alternatives: int,
    ) -> list[RouteCandidate]:
        self.calls.append(tuple(waypoints))
        if len(waypoints) > 2:
            return [straight_route(waypoints, "via")]
        primary = straight_route(waypoints, "primary")
        # A provider "alternative" that duplicates the primary must be filtered out.
        return [primary] + [
            straight_route(waypoints, "alternative") for _ in range(self.direct_alternatives)
        ]


@dataclass
class FakeWeather:
    weather: WeatherFn = calm
    requested: int = 0
    calls: list[int] = field(default_factory=list)
    """Locations requested per call."""
    rate_limit_on_call: int | None = None
    """Zero-based call that answers only half its locations, then reports HTTP 429."""

    async def hourly_forecast(
        self, points: Sequence[LatLon], *, start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        self.requested += len(points)
        self.calls.append(len(points))
        if len(self.calls) - 1 == self.rate_limit_on_call:
            served = await self._series(points[: len(points) // 2], start, end)
            cause = UpstreamServiceError("open-meteo", "HTTP 429", status=429)
            raise IncompleteForecastError(cause, served)
        return await self._series(points, start, end)

    async def _series(
        self, points: Sequence[LatLon], start: datetime, end: datetime
    ) -> dict[LatLon, HourlySeries]:
        hours = int((end - start).total_seconds() // 3600) + 1
        result = {}
        for point in points:
            values = [self.weather(point, start + timedelta(hours=h)) for h in range(hours)]
            result[point] = HourlySeries(
                start=start,
                wind_mph=tuple(v[0] * 0.6 for v in values),
                gust_mph=tuple(v[0] for v in values),
                rain_in_hr=tuple(v[1] for v in values),
                snow_in_hr=tuple(v[2] for v in values),
                temperature_f=tuple(40.0 for _ in values),
                weather_code=tuple(0 for _ in values),
            )
        return result


def denver_tz(_: LatLon) -> ZoneInfo:
    return ZoneInfo("America/Denver")


def make_service(
    weather: WeatherFn = calm,
    *,
    routing: FakeRouting | None = None,
    config: PlanningConfig | None = None,
    weather_provider: FakeWeather | None = None,
) -> PlanningService:
    return PlanningService(
        routing or FakeRouting(),
        weather_provider or FakeWeather(weather),
        timezone_at=denver_tz,
        clock=lambda: NOW,
        config=config or PlanningConfig(heatmap_target_points=60),
    )
