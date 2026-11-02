from datetime import UTC, datetime, timedelta

from corridor.domain.departure import DepartureOption, suggest
from corridor.domain.ranking import Criterion, RiskSegment, rank, summarize
from corridor.domain.risk import Level
from corridor.domain.units import METERS_PER_MILE as MILE

LEAVE = datetime(2026, 11, 3, 13, tzinfo=UTC)


def option(
    offset_h: int, *, severe: float = 0, high: float = 0, unknown: float = 0
) -> DepartureOption:
    segments = [
        RiskSegment(severe * MILE, Level.SEVERE),
        RiskSegment(high * MILE, Level.HIGH),
        RiskSegment(unknown * MILE, None),
        RiskSegment((300 - severe - high - unknown) * MILE, Level.LOW),
    ]
    risk = summarize("A", segments, 300 * MILE, 5 * 3600)
    return DepartureOption(offset_h, LEAVE + timedelta(hours=offset_h), rank([risk]), (risk,))


def test_suggests_the_safest_departure() -> None:
    advice = suggest([option(0, severe=80), option(3, severe=40), option(6, high=30)])
    assert advice is not None
    assert advice.option.offset_h == 6
    assert (advice.criterion, advice.gain_mi) == (Criterion.SEVERE_MILES, 80)


def test_ties_go_to_the_nearest_departure() -> None:
    advice = suggest([option(-3), option(0, severe=50), option(3), option(9)])
    assert advice is not None
    assert advice.option.offset_h == -3


def test_small_gains_are_not_worth_moving_for() -> None:
    assert suggest([option(0, severe=12), option(3, severe=5)]) is None


def test_unforecast_miles_do_not_count_as_safer() -> None:
    assert suggest([option(0, severe=60), option(24, severe=0, unknown=120)]) is None


def test_no_suggestion_when_already_best() -> None:
    assert suggest([option(0), option(3, high=40)]) is None
