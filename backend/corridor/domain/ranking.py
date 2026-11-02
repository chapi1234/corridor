"""Route risk summaries and the recommendation ranking (D10-D13).

Ranking is lexicographic over:

    0. fewest No Travel miles   (D10: added ahead of the brief's list)
    1. fewest Severe miles
    2. fewest High miles
    3. lowest distance-weighted average risk
    4. shortest travel time

Values are quantised before comparison (whole miles, 0.05 risk steps, whole seconds) so
negligible differences fall through to the next criterion and the order stays total.

The explanation compares the winner with the route a driver would naturally weigh it
against: the fastest route when the recommendation is not the fastest (the safety vs
time trade-off), otherwise the runner-up.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Final

from corridor.domain.risk import Level
from corridor.domain.units import meters_to_miles

AVERAGE_RISK_STEP: Final = 0.05
_UNKNOWN_AVERAGE_KEY: Final = sys.maxsize


class Criterion(IntEnum):
    NO_TRAVEL_MILES = 0
    SEVERE_MILES = 1
    HIGH_MILES = 2
    AVERAGE_RISK = 3
    DURATION = 4

    @property
    def slug(self) -> str:
        return self.name.lower()


class Tag(StrEnum):
    RECOMMENDED = "recommended"
    FASTEST = "fastest"
    SHORTEST = "shortest"
    LOWEST_RISK = "lowest_risk"


@dataclass(frozen=True, slots=True)
class RiskSegment:
    """A stretch of road owned by one checkpoint. ``level`` is ``None`` when unforecast."""

    owned_m: float
    level: Level | None


@dataclass(frozen=True, slots=True)
class RouteRisk:
    route_id: str
    distance_m: float
    duration_s: float
    miles_by_level: dict[Level, float]
    unknown_miles: float
    average_risk: float | None
    """Distance-weighted mean of level scores over forecast miles (D12)."""


RankKey = tuple[int, int, int, int, int]

CALM_TOLERANCE_MI = 0.5


@dataclass(frozen=True, slots=True)
class Ranking:
    order: tuple[str, ...]
    recommended: str
    competitor: str | None
    """The route the explanation compares against; ``None`` when only one route exists."""
    deciding: Criterion | None
    """First criterion separating the winner from the competitor; ``None`` on a full tie."""
    beats_on: dict[str, Criterion | None]
    """For every other route, the first criterion on which the recommendation wins."""
    keys: dict[str, RankKey]
    reason: str
    no_safe_route: bool


def summarize(
    route_id: str, segments: Iterable[RiskSegment], distance_m: float, duration_s: float
) -> RouteRisk:
    meters_by_level = dict.fromkeys(Level, 0.0)
    unknown_m = 0.0
    for segment in segments:
        if segment.level is None:
            unknown_m += segment.owned_m
        else:
            meters_by_level[segment.level] += segment.owned_m

    known_m = sum(meters_by_level.values())
    average = (
        sum(level * meters for level, meters in meters_by_level.items()) / known_m
        if known_m > 0
        else None
    )
    return RouteRisk(
        route_id=route_id,
        distance_m=distance_m,
        duration_s=duration_s,
        miles_by_level={level: meters_to_miles(m) for level, m in meters_by_level.items()},
        unknown_miles=meters_to_miles(unknown_m),
        average_risk=average,
    )


def rank_key(route: RouteRisk) -> RankKey:
    miles = route.miles_by_level
    average_key = (
        _UNKNOWN_AVERAGE_KEY
        if route.average_risk is None
        else round(route.average_risk / AVERAGE_RISK_STEP)
    )
    return (
        round(miles[Level.NO_TRAVEL]),
        round(miles[Level.SEVERE]),
        round(miles[Level.HIGH]),
        average_key,
        round(route.duration_s),
    )


def rank(routes: Sequence[RouteRisk]) -> Ranking:
    if not routes:
        raise ValueError("Cannot rank an empty set of routes")

    keys = {route.route_id: rank_key(route) for route in routes}
    ordered = sorted(routes, key=lambda r: keys[r.route_id])
    best = ordered[0]
    others = ordered[1:]

    def first_difference(other: RouteRisk) -> Criterion | None:
        best_key, other_key = keys[best.route_id], keys[other.route_id]
        return next((c for c in Criterion if best_key[c] != other_key[c]), None)

    beats_on = {other.route_id: first_difference(other) for other in others}
    competitor = _competitor(best, others)
    deciding = beats_on[competitor.route_id] if competitor else None

    return Ranking(
        order=tuple(r.route_id for r in ordered),
        recommended=best.route_id,
        competitor=competitor.route_id if competitor else None,
        deciding=deciding,
        beats_on=beats_on,
        keys=keys,
        reason=explain(best, competitor, deciding),
        no_safe_route=all(keys[r.route_id][Criterion.NO_TRAVEL_MILES] > 0 for r in routes),
    )


def _competitor(best: RouteRisk, others: Sequence[RouteRisk]) -> RouteRisk | None:
    if not others:
        return None
    fastest = min(others, key=lambda r: r.duration_s)
    return fastest if fastest.duration_s < best.duration_s else others[0]


def explain(best: RouteRisk, competitor: RouteRisk | None, deciding: Criterion | None) -> str:
    """One-sentence, deterministic justification of the recommendation."""
    if competitor is None:
        return "Only one route is available for this trip."
    other = f"Route {competitor.route_id}"
    if deciding is None:
        return f"Routes are equivalent on every criterion; Route {best.route_id} is listed first."

    best_key, other_key = rank_key(best), rank_key(competitor)
    diff = other_key[deciding] - best_key[deciding]

    match deciding:
        case Criterion.NO_TRAVEL_MILES | Criterion.SEVERE_MILES:
            label = "No Travel" if deciding is Criterion.NO_TRAVEL_MILES else "Severe"
            if best_key[deciding] == 0:
                return f"Avoids {diff} {label} miles that {other} crosses."
            return f"{diff} fewer {label} miles than {other}."
        case Criterion.HIGH_MILES:
            return f"Same Severe exposure as {other}, but {diff} fewer High miles."
        case Criterion.AVERAGE_RISK:
            assert best.average_risk is not None
            other_avg = (
                "unknown" if competitor.average_risk is None else f"{competitor.average_risk:.2f}"
            )
            return (
                f"Lower overall weather risk than {other} "
                f"(average {best.average_risk:.2f} vs {other_avg})."
            )
        case Criterion.DURATION:
            if _all_low(best) and _all_low(competitor):
                return f"All low risk, like {other}, and {format_duration(diff)} faster."
            return f"Equal weather risk to {other}, and {format_duration(diff)} faster."


def _all_low(route: RouteRisk) -> bool:
    """Every forecast mile is Low and none is unknown (sub-mile slivers ignored)."""
    elevated = sum(m for level, m in route.miles_by_level.items() if level > Level.LOW)
    return elevated < CALM_TOLERANCE_MI and route.unknown_miles < CALM_TOLERANCE_MI


def assign_tags(routes: Sequence[RouteRisk], ranking: Ranking) -> dict[str, list[Tag]]:
    tags: dict[str, list[Tag]] = {r.route_id: [] for r in routes}
    tags[ranking.recommended].append(Tag.RECOMMENDED)
    tags[min(routes, key=lambda r: r.duration_s).route_id].append(Tag.FASTEST)
    tags[min(routes, key=lambda r: r.distance_m).route_id].append(Tag.SHORTEST)
    rated = [r for r in routes if r.average_risk is not None]
    if rated:
        tags[min(rated, key=lambda r: r.average_risk or 0.0).route_id].append(Tag.LOWEST_RISK)
    return tags


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return "under 1 min"
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if hours == 0:
        return f"{minutes} min"
    return f"{hours} h {minutes:02d} min"
