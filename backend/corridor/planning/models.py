"""Inputs and outputs of the planning service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from corridor.domain.geometry import LatLon
from corridor.domain.models import Place, RouteCandidate
from corridor.domain.ranking import Ranking, RouteRisk, Tag
from corridor.domain.risk import Classification
from corridor.domain.sampling import CheckpointPosition
from corridor.domain.weather import WeatherSample

SAMPLING_INTERVALS_MI = (10, 25, 50)


@dataclass(frozen=True, slots=True)
class PlanRequest:
    origin: Place
    destination: Place
    departure_local: datetime
    """Naive wall-clock time at the origin (D14)."""
    load_lb: float
    interval_mi: int


@dataclass(frozen=True, slots=True)
class HourlyWindow:
    """Forecast around a checkpoint ETA for the detail chart; ``None`` marks missing hours."""

    start: datetime
    gust_mph: tuple[float | None, ...]
    rain_in_hr: tuple[float | None, ...]
    snow_in_hr: tuple[float | None, ...]


@dataclass(frozen=True, slots=True)
class Checkpoint:
    position: CheckpointPosition
    eta: datetime
    tz: ZoneInfo
    """Local time zone at the checkpoint, for displaying its ETA."""
    line_fraction: float
    weather_point: LatLon
    weather: WeatherSample | None
    classification: Classification | None
    """``None`` when the ETA is outside the forecast (D19)."""
    hourly: HourlyWindow | None


@dataclass(frozen=True, slots=True)
class PlannedRoute:
    id: str
    candidate: RouteCandidate
    checkpoints: tuple[Checkpoint, ...]
    risk: RouteRisk
    arrival: datetime
    tags: tuple[Tag, ...]


@dataclass(frozen=True, slots=True)
class HeatmapFrames:
    """Raw weather on the corridor grid for each forecast hour, quantised to integers.

    Arrays are indexed ``[hour][point]``. ``-1`` marks a missing value. The client derives
    risk from these with the current load, so a load change needs no new request.
    """

    base_time: datetime
    points: tuple[LatLon, ...]
    spacing_m: float
    """Grid spacing; lets the client size heatmap kernels to blend neighbouring points."""
    gust_mph_x10: tuple[tuple[int, ...], ...]
    rain_in_hr_x1000: tuple[tuple[int, ...], ...]
    snow_in_hr_x100: tuple[tuple[int, ...], ...]


class WarningCode(StrEnum):
    FEWER_ROUTES = "fewer_routes"
    FORECAST_UNAVAILABLE = "forecast_unavailable"


@dataclass(frozen=True, slots=True)
class PlanWarning:
    code: WarningCode
    message: str


@dataclass(frozen=True, slots=True)
class Plan:
    request: PlanRequest
    generated_at: datetime
    departure: datetime
    origin_tz: ZoneInfo
    destination_tz: ZoneInfo
    routes: tuple[PlannedRoute, ...]
    ranking: Ranking
    heatmap: HeatmapFrames
    routing_source: str = ""
    warnings: tuple[PlanWarning, ...] = ()
    timings_ms: dict[str, int] = field(default_factory=dict)
