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
    heatmap_target_points: int = 280
    heatmap_min_spacing_m: float = 10_000
    heatmap_max_spacing_m: float = 45_000
    heatmap_hours: int = 49
    """Frames for forecast hours 0..48 relative to the departure hour (D15)."""

    weather_grid_deg: float = 0.05
    """Weather locations are snapped to this grid to dedupe requests and share cache."""
    checkpoint_window_hours: int = 6
    """Hours of forecast either side of each checkpoint ETA returned for the detail chart."""

    departure_grace: timedelta = timedelta(minutes=5)
    max_departure_ahead: timedelta = timedelta(days=10)
    forecast_horizon: timedelta = timedelta(days=15)
    """Open-Meteo serves roughly 16 days ahead; stay a day inside it."""


DEFAULT_CONFIG = PlanningConfig()
