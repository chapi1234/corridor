"""Tunable planning parameters, kept in one place and documented."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class PlanningConfig:
    route_count: int = 3
    """The brief asks for three route options (D20)."""

    tractor_trailer_tare_lb: float = 35_000
    """Empty tractor + 53 ft trailer; gross routing weight = tare + load (D23)."""

    max_detour_ratio: float = 1.6
    """Generated via-routes slower than this multiple of the fastest route are discarded."""
    via_offset_ratio: float = 0.12
    """Via-point offset from the midpoint, as a share of the straight-line trip distance."""
    via_offset_cap_m: float = 150_000
    similarity_tolerance_m: float = 300
    similarity_share: float = 0.9
    """Two routes are duplicates if this share of each lies within the tolerance of the other."""

    corridor_half_width_m: float = 30_000
    heatmap_target_points: int = 220
    heatmap_min_points: int = 60
    heatmap_min_spacing_m: float = 10_000
    heatmap_max_spacing_m: float = 90_000
    heatmap_hours: int = 49
    """Frames for forecast hours 0..48 relative to the departure hour (D15)."""

    weather_grid_deg: float = 0.05
    """Weather locations are snapped to this grid to dedupe requests and share cache."""
    checkpoint_grid_steps_deg: tuple[float, ...] = (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)
    """Coarser snapping grids tried in turn until checkpoints fit the location budget."""
    checkpoint_location_budget: int = 240
    weather_location_budget: int = 360
    """Forecast locations per plan. Open-Meteo's free tier counts every location in a
    request as one call and allows ~600 a minute, so a plan must stay well under that."""
    alerts_sample_spacing_m: float = 20_000
    """NWS forecast zones are roughly county-sized; sampling every 20 km catches each one."""
    alerts_grid_steps_deg: tuple[float, ...] = (0.2, 0.3, 0.4, 0.5)
    alerts_location_budget: int = 160
    """NWS answers one location per request, so long trips sample more coarsely."""
    checkpoint_window_hours: int = 6
    """Hours of forecast either side of each checkpoint ETA returned for the detail chart."""

    departure_offsets_h: tuple[int, ...] = (-12, -9, -6, -3, 0, 3, 6, 9, 12, 15, 18, 21, 24)
    """Departures the advisor re-scores, relative to the requested one (past ones skipped)."""

    departure_grace: timedelta = timedelta(minutes=5)
    max_departure_ahead: timedelta = timedelta(days=10)
    forecast_horizon: timedelta = timedelta(days=15)
    """Open-Meteo serves roughly 16 days ahead; stay a day inside it."""


DEFAULT_CONFIG = PlanningConfig()
