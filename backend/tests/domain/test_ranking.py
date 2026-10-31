import pytest
from hypothesis import given
from hypothesis import strategies as st

from corridor.domain.ranking import (
    Criterion,
    RiskSegment,
    RouteRisk,
    Tag,
    assign_tags,
    format_duration,
    rank,
    summarize,
)
from corridor.domain.risk import Level
from corridor.domain.units import METERS_PER_MILE as MILE


def route(
    route_id: str,
    *,
    no_travel: float = 0,
    severe: float = 0,
    high: float = 0,
    moderate: float = 0,
    low: float = 100,
    hours: float = 10,
) -> RouteRisk:
    miles_by_level = {
        Level.NO_TRAVEL: no_travel,
        Level.SEVERE: severe,
        Level.HIGH: high,
        Level.MODERATE: moderate,
        Level.LOW: low,
    }
    segments = [RiskSegment(m * MILE, lvl) for lvl, m in miles_by_level.items() if m]
    distance = sum(s.owned_m for s in segments)
    return summarize(route_id, segments, distance, hours * 3600)


def test_summary_miles_and_weighted_average() -> None:
    segments = [
        RiskSegment(30 * MILE, Level.LOW),
        RiskSegment(10 * MILE, Level.SEVERE),
        RiskSegment(5 * MILE, None),
    ]
    summary = summarize("A", segments, 45 * MILE, 3600)

    assert summary.miles_by_level[Level.SEVERE] == pytest.approx(10)
    assert summary.unknown_miles == pytest.approx(5)
    assert summary.average_risk == pytest.approx(0.75)


def test_summary_with_no_forecast_has_no_average() -> None:
    assert summarize("A", [RiskSegment(MILE, None)], MILE, 60).average_risk is None


@pytest.mark.parametrize(
    ("a", "b", "criterion", "reason"),
    [
        pytest.param(
            route("A", no_travel=5, hours=8),
            route("B", severe=50, hours=12),
            Criterion.NO_TRAVEL_MILES,
            "Avoids 5 No Travel miles that Route A crosses.",
            id="no-travel",
        ),
        pytest.param(
            route("A", severe=38, hours=8),
            route("B", high=90, hours=12),
            Criterion.SEVERE_MILES,
            "Avoids 38 Severe miles that Route A crosses.",
            id="severe",
        ),
        pytest.param(
            route("A", severe=10, high=5),
            route("B", severe=10, high=27),
            Criterion.HIGH_MILES,
            "Same Severe exposure as Route B, but 22 fewer High miles.",
            id="high",
        ),
        pytest.param(
            route("A", moderate=80, low=20),
            route("B", moderate=10, low=90),
            Criterion.AVERAGE_RISK,
            "Lower overall weather risk than Route A",
            id="average",
        ),
        pytest.param(
            route("A", hours=10),
            route("B", hours=10.7),
            Criterion.DURATION,
            "Equal weather risk to Route B, and 42 min faster.",
            id="duration",
        ),
    ],
)
def test_each_criterion_can_decide(
    a: RouteRisk, b: RouteRisk, criterion: Criterion, reason: str
) -> None:
    ranking = rank([a, b])
    assert ranking.deciding == criterion
    assert ranking.reason.startswith(reason)


def test_risk_beats_travel_time() -> None:
    fast_but_severe = route("A", severe=1, hours=8)
    slow_but_clear = route("B", hours=14)
    assert rank([fast_but_severe, slow_but_clear]).recommended == "B"


def test_quantisation_ignores_negligible_mile_differences() -> None:
    ranking = rank([route("A", severe=10.2, hours=11), route("B", severe=10.4, hours=10)])
    assert ranking.recommended == "B"
    assert ranking.deciding == Criterion.DURATION


def test_no_safe_route_flag() -> None:
    ranking = rank([route("A", no_travel=3), route("B", no_travel=1)])
    assert ranking.no_safe_route
    assert ranking.recommended == "B"


def test_full_tie_and_single_route() -> None:
    assert rank([route("A"), route("B")]).deciding is None
    single = rank([route("A")])
    assert single.recommended == "A"
    assert single.reason == "Only one route is available for this trip."


def test_rank_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        rank([])


@given(
    st.lists(
        st.tuples(st.integers(0, 50), st.integers(0, 50), st.integers(0, 50), st.floats(1, 30)),
        min_size=1,
        max_size=4,
    )
)
def test_ranking_is_independent_of_input_order(
    specs: list[tuple[int, int, int, float]],
) -> None:
    routes = [
        route(chr(65 + i), no_travel=nt, severe=s, high=h, hours=hrs)
        for i, (nt, s, h, hrs) in enumerate(specs)
    ]
    forward, backward = rank(routes), rank(list(reversed(routes)))
    best_key = min(forward.keys.values())
    assert forward.keys[forward.recommended] == best_key
    assert backward.keys[backward.recommended] == best_key


def test_tags() -> None:
    a = route("A", severe=5, hours=8, low=90)
    b = route("B", hours=10, low=120)
    tags = assign_tags([a, b], rank([a, b]))
    assert tags["A"] == [Tag.FASTEST, Tag.SHORTEST]
    assert tags["B"] == [Tag.RECOMMENDED, Tag.LOWEST_RISK]


@pytest.mark.parametrize(
    ("seconds", "text"), [(60, "1 min"), (2520, "42 min"), (3900, "1 h 05 min")]
)
def test_format_duration(seconds: float, text: str) -> None:
    assert format_duration(seconds) == text
