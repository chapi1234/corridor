"""Hourly forecast series and value-at-time semantics (D18)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from corridor.domain.units import SECONDS_PER_HOUR

UNKNOWN_WEATHER_CODE = -1


@dataclass(frozen=True, slots=True)
class WeatherSample:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float
    temperature_f: float
    weather_code: int
    wind_direction_deg: float = math.nan
    """Direction the wind blows from, clockwise from north; ``nan`` when not forecast."""
    visibility_mi: float = math.nan


@dataclass(frozen=True, slots=True)
class HourlySeries:
    """Hourly forecast for one location, in US units.

    Index ``i`` is the top of hour ``start + i h`` (UTC). Instantaneous variables (wind,
    gust, temperature) are valid at that instant; accumulated variables (rain, snow) are
    the total over the hour *ending* at that instant, which is also their rate per hour.
    Missing values are ``nan``.
    """

    start: datetime
    wind_mph: tuple[float, ...]
    gust_mph: tuple[float, ...]
    rain_in_hr: tuple[float, ...]
    snow_in_hr: tuple[float, ...]
    temperature_f: tuple[float, ...]
    weather_code: tuple[int, ...]
    wind_direction_deg: tuple[float, ...] = ()
    """Optional, like ``visibility_mi``: empty when the provider does not forecast it."""
    visibility_mi: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.start.utcoffset() != timedelta(0):
            raise ValueError("Series start must be timezone-aware UTC")
        if self.start != self.start.replace(minute=0, second=0, microsecond=0):
            raise ValueError("Series start must be on the hour")
        lengths = {
            len(self.wind_mph),
            len(self.gust_mph),
            len(self.rain_in_hr),
            len(self.snow_in_hr),
            len(self.temperature_f),
            len(self.weather_code),
        }
        lengths |= {len(v) for v in (self.wind_direction_deg, self.visibility_mi) if v}
        if len(lengths) != 1:
            raise ValueError("All hourly variables must have the same length")

    def __len__(self) -> int:
        return len(self.gust_mph)

    def time_at(self, index: int) -> datetime:
        return self.start + timedelta(hours=index)

    def at(self, moment: datetime) -> WeatherSample | None:
        """Conditions a vehicle experiences at ``moment``, or ``None`` if not forecast.

        Instantaneous variables are linearly interpolated between the surrounding hours.
        Accumulated variables use the hour that contains ``moment``, i.e. the value at the
        next top of hour (or at ``moment`` itself when it falls exactly on the hour).
        """
        offset_h = (moment.astimezone(UTC) - self.start).total_seconds() / SECONDS_PER_HOUR
        lo, hi = math.floor(offset_h), math.ceil(offset_h)
        if lo < 0 or hi >= len(self):
            return None
        frac = offset_h - lo

        def lerp(values: tuple[float, ...]) -> float:
            return values[lo] + (values[hi] - values[lo]) * frac

        sample = WeatherSample(
            wind_mph=lerp(self.wind_mph),
            gust_mph=lerp(self.gust_mph),
            rain_in_hr=self.rain_in_hr[hi],
            snow_in_hr=self.snow_in_hr[hi],
            temperature_f=lerp(self.temperature_f),
            weather_code=self.weather_code[hi],
            # Angles don't interpolate linearly; take the nearer hour.
            wind_direction_deg=(
                self.wind_direction_deg[round(offset_h)] if self.wind_direction_deg else math.nan
            ),
            visibility_mi=lerp(self.visibility_mi) if self.visibility_mi else math.nan,
        )
        required = (sample.gust_mph, sample.rain_in_hr, sample.snow_in_hr)
        if any(math.isnan(v) for v in required):
            return None
        return sample
