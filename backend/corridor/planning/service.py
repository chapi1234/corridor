"""Plan orchestration: routes → checkpoints → ETA-time weather → risk → recommendation."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from corridor.domain.geometry import LatLon, Polyline
from corridor.domain.models import RouteCandidate
from corridor.domain.ranking import RiskSegment, assign_tags, rank, summarize
from corridor.domain.risk import classify
from corridor.domain.sampling import CheckpointPosition, place_checkpoints
from corridor.domain.timeline import TimeAnchor, TimeProfile
from corridor.domain.units import lb_to_kg, miles_to_meters
from corridor.domain.weather import HourlySeries
from corridor.planning.alternatives import DistinctRoutes, via_points
from corridor.planning.config import DEFAULT_CONFIG, PlanningConfig
from corridor.planning.corridor import corridor_grid, snap
from corridor.planning.errors import (
    InvalidPlanRequestError,
    RouteNotFoundError,
    UpstreamServiceError,
)
from corridor.planning.frames import build_frames
from corridor.planning.models import (
    SAMPLING_INTERVALS_MI,
    Checkpoint,
    HourlyWindow,
    Plan,
    PlannedRoute,
    PlanRequest,
    PlanWarning,
    WarningCode,
)
from corridor.planning.ports import RoutingProvider, WeatherProvider
from corridor.planning.projection import LocalProjection

ROUTE_LABELS = "ABCDEFGH"

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def ceil_hour(moment: datetime) -> datetime:
    floored = floor_hour(moment)
    return floored if floored == moment else floored + timedelta(hours=1)


class PlanningService:
    def __init__(
        self,
        routing: RoutingProvider,
        weather: WeatherProvider,
        *,
        timezone_at: Callable[[LatLon], ZoneInfo],
        clock: Callable[[], datetime] = _utc_now,
        config: PlanningConfig = DEFAULT_CONFIG,
    ) -> None:
        self._routing = routing
        self._weather = weather
        self._timezone_at = timezone_at
        self._clock = clock
        self._config = config

    async def build(self, request: PlanRequest) -> Plan:
        timings: dict[str, int] = {}
        now = self._clock()
        origin_tz = self._timezone_at(request.origin.point)
        destination_tz = self._timezone_at(request.destination.point)
        departure = self._validate(request, origin_tz, now)

        with _timed(timings, "routing"):
            candidates = await self._candidate_routes(request, departure)
        candidates.sort(key=lambda c: c.duration_s)

        with _timed(timings, "geometry"):
            positions = [self._checkpoints(c, request.interval_mi) for c in candidates]
            projection = LocalProjection([p for c in candidates for p in c.points])
            grid = corridor_grid(
                [projection.line(c.points) for c in candidates], projection, self._config
            )

        base_time = floor_hour(departure)
        last_eta = departure + timedelta(seconds=max(c.duration_s for c in candidates))
        window = timedelta(hours=self._config.checkpoint_window_hours)
        start = base_time - window
        end = min(
            max(
                base_time + timedelta(hours=self._config.heatmap_hours - 1),
                ceil_hour(last_eta) + window,
            ),
            floor_hour(now) + self._config.forecast_horizon,
        )

        step = self._config.weather_grid_deg
        with _timed(timings, "weather"):
            locations = {snap(p.point, step) for route in positions for p in route}
            locations |= {snap(p, step) for p in grid.points}
            forecasts = await self._weather.hourly_forecast(
                sorted(locations, key=_coords), start=start, end=end
            )

        with _timed(timings, "scoring"):
            routes = self._score_routes(
                candidates, positions, forecasts, departure, request.load_lb
            )
            ranking = rank([r.risk for r in routes])
            tags = assign_tags([r.risk for r in routes], ranking)
            routes = [replace(r, tags=tuple(tags[r.id])) for r in routes]
            heatmap = build_frames(
                grid.points,
                {p: forecasts[snap(p, step)] for p in grid.points if snap(p, step) in forecasts},
                base_time=base_time,
                hours=self._config.heatmap_hours,
                spacing_m=grid.spacing_m,
            )

        return Plan(
            request=request,
            generated_at=now,
            departure=departure,
            origin_tz=origin_tz,
            destination_tz=destination_tz,
            routes=tuple(routes),
            ranking=ranking,
            heatmap=heatmap,
            routing_source=self._routing.display_name,
            warnings=tuple(self._warnings(routes)),
            timings_ms=timings,
        )

    # ------------------------------------------------------------------ steps
    def _validate(self, request: PlanRequest, origin_tz: ZoneInfo, now: datetime) -> datetime:
        if request.interval_mi not in SAMPLING_INTERVALS_MI:
            raise InvalidPlanRequestError(
                "interval_mi", "Sampling interval must be 10, 25 or 50 miles."
            )
        if request.origin.point == request.destination.point:
            raise InvalidPlanRequestError("destination", "Origin and destination must differ.")
        departure = request.departure_local.replace(tzinfo=origin_tz).astimezone(UTC)
        if departure < now - self._config.departure_grace:
            raise InvalidPlanRequestError("departure", "Departure time is in the past.")
        if departure > now + self._config.max_departure_ahead:
            days = self._config.max_departure_ahead.days
            raise InvalidPlanRequestError("departure", f"Departure must be within {days} days.")
        return departure

    async def _candidate_routes(
        self, request: PlanRequest, departure: datetime
    ) -> list[RouteCandidate]:
        origin, destination = request.origin.point, request.destination.point
        gross_kg = lb_to_kg(self._config.tractor_trailer_tare_lb + request.load_lb)
        target = self._config.route_count

        async def fetch(waypoints: Sequence[LatLon], alternatives: int) -> list[RouteCandidate]:
            return await self._routing.calculate_routes(
                waypoints, depart_at=departure, gross_weight_kg=gross_kg, alternatives=alternatives
            )

        async def fetch_via(via: LatLon) -> list[RouteCandidate]:
            """Generated alternatives are best-effort: a failure leaves fewer options."""
            try:
                return (await fetch([origin, via, destination], 0))[:1]
            except (RouteNotFoundError, UpstreamServiceError) as exc:
                logger.info("Via route through %s skipped: %s", via, exc)
                return []

        # Via points depend only on the endpoints, so the first pair is requested alongside
        # the primary route: one round trip instead of two when the provider offers few
        # alternatives. The wider pair is only requested if still short of the target.
        projection = LocalProjection([origin, destination])
        vias = via_points(origin, destination, projection, self._config)
        near_vias, far_vias = vias[:2], vias[2:]
        primary, *via_results = await asyncio.gather(
            fetch([origin, destination], target - 1), *(fetch_via(v) for v in near_vias)
        )

        distinct = DistinctRoutes(projection, self._config)
        distinct.offer_all(primary)
        for result in via_results:
            distinct.offer_all(result)
        if len(distinct) < target and far_vias:
            for result in await asyncio.gather(*(fetch_via(v) for v in far_vias)):
                distinct.offer_all(result)
        return distinct.routes[:target]

    def _checkpoints(self, candidate: RouteCandidate, interval_mi: int) -> list[CheckpointPosition]:
        polyline = Polyline(candidate.points)
        # Provider anchors are in the provider's length units; rescale onto our polyline.
        scale = polyline.total_m / candidate.length_m if candidate.length_m else 1.0
        profile = TimeProfile(
            (TimeAnchor(a.distance_m * scale, a.elapsed_s) for a in candidate.anchors),
            total_m=polyline.total_m,
            total_s=candidate.duration_s,
        )
        return place_checkpoints(polyline, profile, miles_to_meters(interval_mi))

    def _score_routes(
        self,
        candidates: Sequence[RouteCandidate],
        positions: Sequence[Sequence[CheckpointPosition]],
        forecasts: dict[LatLon, HourlySeries],
        departure: datetime,
        load_lb: float,
    ) -> list[PlannedRoute]:
        step = self._config.weather_grid_deg
        routes = []
        for label, candidate, route_positions in zip(
            ROUTE_LABELS, candidates, positions, strict=False
        ):
            total_m = route_positions[-1].distance_m
            checkpoints = []
            for position in route_positions:
                eta = departure + timedelta(seconds=position.elapsed_s)
                weather_point = snap(position.point, step)
                series = forecasts.get(weather_point)
                sample = series.at(eta) if series else None
                checkpoints.append(
                    Checkpoint(
                        position=position,
                        eta=eta,
                        tz=self._timezone_at(position.point),
                        line_fraction=position.distance_m / total_m,
                        weather_point=weather_point,
                        weather=sample,
                        classification=classify(sample, load_lb) if sample else None,
                        hourly=self._hourly_window(series, eta) if series else None,
                    )
                )
            risk = summarize(
                label,
                (
                    RiskSegment(
                        c.position.owned_m, c.classification.level if c.classification else None
                    )
                    for c in checkpoints
                ),
                distance_m=candidate.length_m,
                duration_s=candidate.duration_s,
            )
            routes.append(
                PlannedRoute(
                    id=label,
                    candidate=candidate,
                    checkpoints=tuple(checkpoints),
                    risk=risk,
                    arrival=departure + timedelta(seconds=candidate.duration_s),
                    tags=(),
                )
            )
        return routes

    def _hourly_window(self, series: HourlySeries, eta: datetime) -> HourlyWindow:
        half = self._config.checkpoint_window_hours
        start = floor_hour(eta) - timedelta(hours=half)
        offset = round((start - series.start).total_seconds() / 3600)
        indices = range(offset, offset + 2 * half + 1)

        def pick(values: tuple[float, ...]) -> tuple[float | None, ...]:
            return tuple(
                values[i] if 0 <= i < len(values) and not math.isnan(values[i]) else None
                for i in indices
            )

        return HourlyWindow(
            start=start,
            gust_mph=pick(series.gust_mph),
            rain_in_hr=pick(series.rain_in_hr),
            snow_in_hr=pick(series.snow_in_hr),
        )

    def _warnings(self, routes: Sequence[PlannedRoute]) -> Iterator[PlanWarning]:
        if len(routes) < self._config.route_count:
            yield PlanWarning(
                WarningCode.FEWER_ROUTES,
                f"Only {len(routes)} distinct route(s) exist for this trip.",
            )
        unknown = sum(1 for r in routes for c in r.checkpoints if c.classification is None)
        if unknown:
            yield PlanWarning(
                WarningCode.FORECAST_UNAVAILABLE,
                f"Forecast unavailable for {unknown} checkpoint(s); "
                "their miles are not counted as safe.",
            )


def _coords(point: LatLon) -> tuple[float, float]:
    return point.lat, point.lon


@contextmanager
def _timed(timings: dict[str, int], stage: str) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        timings[stage] = round((time.perf_counter() - started) * 1000)
