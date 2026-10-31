import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from corridor.domain.weather import HourlySeries

START = datetime(2026, 11, 3, 12, tzinfo=UTC)


def series(**overrides: Any) -> HourlySeries:
    values: dict[str, Any] = {
        "wind_mph": (10.0, 20.0, 30.0),
        "gust_mph": (20.0, 40.0, 60.0),
        "rain_in_hr": (0.0, 0.2, 0.4),
        "snow_in_hr": (0.0, 0.0, 1.0),
        "temperature_f": (30.0, 32.0, 34.0),
        "weather_code": (0, 61, 71),
    }
    values.update(overrides)
    return HourlySeries(start=START, **values)


def test_on_the_hour_uses_that_hour() -> None:
    sample = series().at(START + timedelta(hours=1))
    assert sample is not None
    assert sample.gust_mph == 40
    assert sample.rain_in_hr == 0.2


def test_instantaneous_values_interpolate() -> None:
    sample = series().at(START + timedelta(minutes=15))
    assert sample is not None
    assert sample.gust_mph == pytest.approx(25)
    assert sample.wind_mph == pytest.approx(12.5)


def test_accumulated_values_use_hour_ending_after_moment() -> None:
    sample = series().at(START + timedelta(hours=1, minutes=20))
    assert sample is not None
    assert sample.rain_in_hr == 0.4
    assert sample.snow_in_hr == 1.0
    assert sample.weather_code == 71


def test_outside_series_is_unavailable() -> None:
    assert series().at(START - timedelta(minutes=1)) is None
    assert series().at(START + timedelta(hours=2, minutes=1)) is None


def test_missing_required_value_is_unavailable() -> None:
    broken = series(gust_mph=(20.0, math.nan, 60.0))
    assert broken.at(START + timedelta(minutes=30)) is None


def test_accepts_non_utc_moment() -> None:
    local = (START + timedelta(hours=1)).astimezone(ZoneInfo("America/Denver"))
    sample = series().at(local)
    assert sample is not None
    assert sample.gust_mph == 40


def test_validates_start_and_lengths() -> None:
    one = (1.0,)
    with pytest.raises(ValueError, match="UTC"):
        HourlySeries(START.replace(tzinfo=None), one, one, one, one, one, (0,))
    with pytest.raises(ValueError, match="hour"):
        HourlySeries(START.replace(minute=5), one, one, one, one, one, (0,))
    with pytest.raises(ValueError, match="same length"):
        HourlySeries(START, one, (1.0, 2.0), one, one, one, (0,))
