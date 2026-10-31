import math
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from corridor.domain.risk import Factor, Level, LoadRule, classify_values
from tests.conftest import SHARED_RISK_CASES

gusts = st.floats(min_value=0, max_value=120, allow_nan=False)
rates = st.floats(min_value=0, max_value=8, allow_nan=False)
loads = st.floats(min_value=0, max_value=120_000, allow_nan=False)


@pytest.mark.parametrize("case", SHARED_RISK_CASES, ids=[c["name"] for c in SHARED_RISK_CASES])
def test_shared_parity_cases(case: dict[str, Any]) -> None:
    result = classify_values(case["gust"], case["rain"], case["snow"], case["load"])

    assert result.level == Level(case["level"])
    assert result.driver == Factor(case["driver"])
    expected_rule = LoadRule(case["load_rule"]) if case["load_rule"] else None
    assert result.load_rule == expected_rule


@given(gust=gusts, rain=rates, snow=rates, load=loads)
def test_index_floor_equals_level(gust: float, rain: float, snow: float, load: float) -> None:
    result = classify_values(gust, rain, snow, load)
    assert math.floor(result.index) == result.level
    assert 0 <= result.index < 5


@given(a=gusts, b=gusts, load=loads)
def test_level_is_monotonic_in_wind(a: float, b: float, load: float) -> None:
    low, high = sorted((a, b))
    assert classify_values(low, 0, 0, load).level <= classify_values(high, 0, 0, load).level


@given(gust=gusts, a=loads, b=loads)
def test_level_is_monotonic_in_load(gust: float, a: float, b: float) -> None:
    light, heavy = sorted((a, b))
    assert classify_values(gust, 0, 0, light).level <= classify_values(gust, 0, 0, heavy).level


@given(a=rates, b=rates)
def test_level_is_monotonic_in_rain_and_snow(a: float, b: float) -> None:
    low, high = sorted((a, b))
    assert classify_values(0, low, 0, 0).level <= classify_values(0, high, 0, 0).level
    assert classify_values(0, 0, low, 0).level <= classify_values(0, 0, high, 0).level


@given(gust=gusts, rain=rates, snow=rates, load=loads)
def test_level_is_worst_factor(gust: float, rain: float, snow: float, load: float) -> None:
    result = classify_values(gust, rain, snow, load)
    assert result.level == max(f.level for f in result.factors.values())
    assert result.factors[result.driver].level == result.level
