"""FMCSA hours-of-service rest planning (property-carrying drivers), D25.

Driving time from the router is turned into wall-clock trip time by inserting the rest a
driver must legally take:

* a 30-minute break once 8 hours of driving have accumulated since the last break;
* a 10-hour off-duty reset after 11 hours of driving in a shift.

The driver is assumed to start rested (10 h off duty) and to spend on-duty time only
driving. Under that assumption the 14-hour duty window never binds (11 h driving + 0.5 h
break = 11.5 h), and the 70-hour/8-day cycle is far beyond the forecast horizon, so both
are omitted. Rest is placed exactly where the limit is reached; a real driver stops at
the nearest truck stop before it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

HOUR_S = 3600.0


class RestKind(StrEnum):
    BREAK = "break"
    RESET = "reset"


@dataclass(frozen=True, slots=True)
class HosRules:
    max_driving_s: float = 11 * HOUR_S
    break_after_driving_s: float = 8 * HOUR_S
    break_s: float = 0.5 * HOUR_S
    reset_s: float = 10 * HOUR_S


FMCSA = HosRules()


@dataclass(frozen=True, slots=True)
class RestStop:
    kind: RestKind
    driving_s: float
    """Driving time accumulated when the rest begins."""
    start_s: float
    """Wall-clock seconds after departure when the rest begins."""
    duration_s: float

    @property
    def end_s(self) -> float:
        return self.start_s + self.duration_s


class DutySchedule:
    """Maps cumulative driving time to wall-clock time since departure."""

    __slots__ = ("_rests",)

    def __init__(self, rests: tuple[RestStop, ...] = ()) -> None:
        self._rests = rests

    @classmethod
    def plan(cls, total_driving_s: float, rules: HosRules = FMCSA) -> DutySchedule:
        """Rest stops for a trip of ``total_driving_s``; none are needed at the very end."""
        if total_driving_s < 0:
            raise ValueError("Driving time must be non-negative")
        rests: list[RestStop] = []
        rested_s = 0.0

        def add(kind: RestKind, at_driving_s: float, duration_s: float) -> None:
            nonlocal rested_s
            rests.append(RestStop(kind, at_driving_s, at_driving_s + rested_s, duration_s))
            rested_s += duration_s

        shift_start = 0.0
        while True:
            break_at = shift_start + rules.break_after_driving_s
            if rules.break_after_driving_s < rules.max_driving_s:
                if break_at >= total_driving_s:
                    break
                add(RestKind.BREAK, break_at, rules.break_s)
            reset_at = shift_start + rules.max_driving_s
            if reset_at >= total_driving_s:
                break
            add(RestKind.RESET, reset_at, rules.reset_s)
            shift_start = reset_at
        return cls(tuple(rests))

    @property
    def rests(self) -> tuple[RestStop, ...]:
        return self._rests

    def clock_s(self, driving_s: float) -> float:
        """Wall-clock time at which ``driving_s`` of driving is reached.

        A point reached exactly when a rest begins gets the time before the rest.
        """
        return driving_s + sum(r.duration_s for r in self._rests if r.driving_s < driving_s)
