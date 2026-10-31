"""Heatmap frame construction (D15, D16)."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Final

from corridor.domain.geometry import LatLon
from corridor.domain.weather import HourlySeries, WeatherSample
from corridor.planning.models import HeatmapFrames

MISSING: Final = -1
GUST_SCALE: Final = 10
RAIN_SCALE: Final = 1000
SNOW_SCALE: Final = 100


def build_frames(
    points: Sequence[LatLon],
    series_for: Mapping[LatLon, HourlySeries],
    *,
    base_time: datetime,
    hours: int,
) -> HeatmapFrames:
    """Sample every grid point at each whole forecast hour after ``base_time``.

    ``series_for`` maps each grid point to the series of its (snapped) weather location.
    """
    samples = [
        [_sample(series_for.get(point), base_time + timedelta(hours=h)) for point in points]
        for h in range(hours)
    ]

    def quantise(read: Callable[[WeatherSample], float], scale: int) -> tuple[tuple[int, ...], ...]:
        return tuple(
            tuple(
                MISSING if s is None or math.isnan(read(s)) else round(read(s) * scale) for s in row
            )
            for row in samples
        )

    return HeatmapFrames(
        base_time=base_time,
        points=tuple(points),
        gust_mph_x10=quantise(lambda s: s.gust_mph, GUST_SCALE),
        rain_in_hr_x1000=quantise(lambda s: s.rain_in_hr, RAIN_SCALE),
        snow_in_hr_x100=quantise(lambda s: s.snow_in_hr, SNOW_SCALE),
    )


def _sample(series: HourlySeries | None, moment: datetime) -> WeatherSample | None:
    return None if series is None else series.at(moment)
