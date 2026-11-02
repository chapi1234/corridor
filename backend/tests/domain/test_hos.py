from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from corridor.domain.hos import FMCSA, DutySchedule, HosRules, RestKind

H = 3600.0


def kinds(schedule: DutySchedule) -> list[tuple[RestKind, float, float]]:
    return [(r.kind, r.driving_s / H, r.start_s / H) for r in schedule.rests]


@pytest.mark.parametrize(
    ("driving_h", "expected"),
    [
        (0, []),
        (7.5, []),
        (8, []),  # arriving exactly at the limit needs no break
        (8.01, [(RestKind.BREAK, 8, 8)]),
        (11, [(RestKind.BREAK, 8, 8)]),
        (11.5, [(RestKind.BREAK, 8, 8), (RestKind.RESET, 11, 11.5)]),
        (18, [(RestKind.BREAK, 8, 8), (RestKind.RESET, 11, 11.5)]),
        (
            19.5,
            [
                (RestKind.BREAK, 8, 8),
                (RestKind.RESET, 11, 11.5),
                (RestKind.BREAK, 19, 29.5),
            ],
        ),
        (
            30,  # third shift's break would fall exactly at arrival
            [
                (RestKind.BREAK, 8, 8),
                (RestKind.RESET, 11, 11.5),
                (RestKind.BREAK, 19, 29.5),
                (RestKind.RESET, 22, 33),
            ],
        ),
    ],
)
def test_rest_schedule(driving_h: float, expected: list[tuple[RestKind, float, float]]) -> None:
    assert kinds(DutySchedule.plan(driving_h * H)) == expected


def test_clock_time_adds_rest_taken_before_a_point() -> None:
    schedule = DutySchedule.plan(20 * H)

    assert schedule.clock_s(4 * H) == 4 * H
    assert schedule.clock_s(8 * H) == 8 * H  # reached as the break begins
    assert schedule.clock_s(9 * H) == 9.5 * H
    assert schedule.clock_s(12 * H) == 22.5 * H
    assert schedule.clock_s(20 * H) == 31 * H


def test_no_schedule_is_identity() -> None:
    assert DutySchedule().clock_s(30 * H) == 30 * H


def test_rules_without_a_separate_break() -> None:
    rules = HosRules(max_driving_s=10 * H, break_after_driving_s=10 * H)
    assert [r.kind for r in DutySchedule.plan(25 * H, rules).rests] == [
        RestKind.RESET,
        RestKind.RESET,
    ]


def test_rejects_negative_driving() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        DutySchedule.plan(-1)


@given(st.floats(min_value=0, max_value=120 * H))
def test_legal_shifts(total_s: float) -> None:
    schedule = DutySchedule.plan(total_s)
    # Never more than 8 h driving between rests, or 11 h between resets.
    marks = [0.0, *(r.driving_s for r in schedule.rests), total_s]
    assert all(b - a <= FMCSA.break_after_driving_s + 1e-6 for a, b in pairwise(marks))
    resets = [0.0, *(r.driving_s for r in schedule.rests if r.kind is RestKind.RESET), total_s]
    assert all(b - a <= FMCSA.max_driving_s + 1e-6 for a, b in pairwise(resets))
    # Clock time is monotonic and accounts for every rest.
    assert schedule.clock_s(total_s) == pytest.approx(
        total_s + sum(r.duration_s for r in schedule.rests)
    )
