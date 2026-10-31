"""Weather risk classification and load rules.

Thresholds (brief):

    Condition  Low        Moderate    High        Severe      No Travel
    Wind       <25 mph    25-34       35-44       45-54       >=55 mph
    Rain       <0.10 in/h 0.10-0.25   0.25-0.50   0.50-1.00   >1.00
    Snow       <0.5 in/h  0.5-1.0     1.0-2.0     2.0-3.0     >3.0

Load rules:  >=55 mph -> No Travel for any load
             45-54 mph and >30,000 lb -> No Travel
             35-44 mph and >40,000 lb -> Severe

Interpretation (see PLAN.md):
    D2  Shared band edges belong to the higher band, except the No Travel column,
        which is strict (">"), so rain 1.00 and snow 3.0 are Severe.
    D3  Wind bands are continuous with lower-inclusive edges at 25/35/45/55 mph.
    D4  Wind is assessed on gusts.
    D7  35-44 mph with 30,001-40,000 lb has no load rule and stays High.
    D8  Load thresholds are strict: exactly 30,000 / 40,000 lb is not escalated.
    D9  A checkpoint's level is the worst of its wind, rain and snow levels.
    D16 A continuous index (level + position within the band) drives the heatmap.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Final

from corridor.domain.weather import WeatherSample


class Level(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


class Factor(StrEnum):
    WIND = "wind"
    RAIN = "rain"
    SNOW = "snow"


class LoadRule(StrEnum):
    """A load rule that raised the wind level above what the weather table alone gives."""

    WIND_45_54_OVER_30K_LB = "wind_45_54_over_30k_lb"
    WIND_35_44_OVER_40K_LB = "wind_35_44_over_40k_lb"


@dataclass(frozen=True, slots=True)
class Band:
    """A threshold band. ``upper`` of the open-ended top band is a soft cap for the index."""

    level: Level
    lower: float
    upper: float


# Bands are listed from the top down; the first band whose lower edge is met wins.
WIND_BANDS_MPH: Final = (
    Band(Level.NO_TRAVEL, 55.0, 75.0),
    Band(Level.SEVERE, 45.0, 55.0),
    Band(Level.HIGH, 35.0, 45.0),
    Band(Level.MODERATE, 25.0, 35.0),
    Band(Level.LOW, 0.0, 25.0),
)
RAIN_BANDS_IN_HR: Final = (
    Band(Level.NO_TRAVEL, 1.00, 2.00),
    Band(Level.SEVERE, 0.50, 1.00),
    Band(Level.HIGH, 0.25, 0.50),
    Band(Level.MODERATE, 0.10, 0.25),
    Band(Level.LOW, 0.0, 0.10),
)
SNOW_BANDS_IN_HR: Final = (
    Band(Level.NO_TRAVEL, 3.0, 5.0),
    Band(Level.SEVERE, 2.0, 3.0),
    Band(Level.HIGH, 1.0, 2.0),
    Band(Level.MODERATE, 0.5, 1.0),
    Band(Level.LOW, 0.0, 0.5),
)

NO_TRAVEL_LOAD_THRESHOLD_LB: Final = 30_000
SEVERE_LOAD_THRESHOLD_LB: Final = 40_000

# Keeps ``floor(index) == level`` for values sitting on a band's upper edge.
_MAX_BAND_FRACTION: Final = 0.999


def wind_band(mph: float) -> Band:
    """Wind bands are lower-inclusive at every edge, including No Travel (>=55)."""
    for band in WIND_BANDS_MPH:
        if mph >= band.lower:
            return band
    return WIND_BANDS_MPH[-1]


def precipitation_band(rate: float, bands: tuple[Band, ...]) -> Band:
    """Precipitation bands are lower-inclusive except No Travel, which is strict (D2)."""
    no_travel, *lower_bands = bands
    if rate > no_travel.lower:
        return no_travel
    for band in lower_bands:
        if rate >= band.lower:
            return band
    return bands[-1]


def apply_load_rules(band: Band, load_lb: float) -> tuple[Level, LoadRule | None]:
    if band.level is Level.SEVERE and load_lb > NO_TRAVEL_LOAD_THRESHOLD_LB:
        return Level.NO_TRAVEL, LoadRule.WIND_45_54_OVER_30K_LB
    if band.level is Level.HIGH and load_lb > SEVERE_LOAD_THRESHOLD_LB:
        return Level.SEVERE, LoadRule.WIND_35_44_OVER_40K_LB
    return band.level, None


def _band_fraction(value: float, band: Band) -> float:
    fraction = (value - band.lower) / (band.upper - band.lower)
    return min(max(fraction, 0.0), _MAX_BAND_FRACTION)


@dataclass(frozen=True, slots=True)
class FactorAssessment:
    level: Level
    index: float


@dataclass(frozen=True, slots=True)
class Classification:
    level: Level
    index: float
    """Continuous risk in [0, 5): ``floor(index) == level``."""
    driver: Factor
    """The factor responsible for the level (highest index among the worst factors)."""
    factors: dict[Factor, FactorAssessment]
    load_rule: LoadRule | None
    """Set whenever the load escalated the wind level, even if another factor is worse."""


def assess_wind(gust_mph: float, load_lb: float) -> tuple[FactorAssessment, LoadRule | None]:
    band = wind_band(gust_mph)
    level, rule = apply_load_rules(band, load_lb)
    return FactorAssessment(level, level + _band_fraction(gust_mph, band)), rule


def assess_precipitation(rate: float, bands: tuple[Band, ...]) -> FactorAssessment:
    band = precipitation_band(rate, bands)
    return FactorAssessment(band.level, band.level + _band_fraction(rate, band))


def classify_values(
    gust_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float
) -> Classification:
    wind, load_rule = assess_wind(gust_mph, load_lb)
    factors = {
        Factor.WIND: wind,
        Factor.RAIN: assess_precipitation(rain_in_hr, RAIN_BANDS_IN_HR),
        Factor.SNOW: assess_precipitation(snow_in_hr, SNOW_BANDS_IN_HR),
    }
    driver = max(factors, key=lambda f: factors[f].index)
    worst = factors[driver]
    return Classification(
        level=worst.level,
        index=worst.index,
        driver=driver,
        factors=factors,
        load_rule=load_rule,
    )


def classify(sample: WeatherSample, load_lb: float) -> Classification:
    return classify_values(sample.gust_mph, sample.rain_in_hr, sample.snow_in_hr, load_lb)
