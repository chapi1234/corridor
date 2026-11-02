from datetime import UTC, datetime

import pytest

from corridor.domain.alerts import (
    AlertCategory,
    AlertSeverity,
    WeatherAlert,
    alert_spans,
    road_hazard_category,
)


def alert(alert_id: str, severity: AlertSeverity = AlertSeverity.SEVERE) -> WeatherAlert:
    return WeatherAlert(
        id=alert_id,
        event="Winter Storm Warning",
        category=AlertCategory.WINTER,
        severity=severity,
        headline="",
        area="",
        starts=datetime(2026, 11, 3, 12, tzinfo=UTC),
        ends=datetime(2026, 11, 3, 18, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("event", "category"),
    [
        ("Winter Storm Warning", AlertCategory.WINTER),
        ("Blizzard Warning", AlertCategory.WINTER),
        ("High Wind Warning", AlertCategory.WIND),
        ("Dense Fog Advisory", AlertCategory.VISIBILITY),
        ("Flash Flood Warning", AlertCategory.FLOOD),
        ("Tornado Warning", AlertCategory.STORM),
        ("Tropical Storm Warning", AlertCategory.TROPICAL),
        ("Wind Chill Warning", AlertCategory.WINTER),
        ("Special Weather Statement", AlertCategory.OTHER),
        ("Coastal Flood Advisory", None),
        ("Small Craft Advisory", None),
        ("Lake Wind Advisory", None),
        ("Freeze Warning", None),
        ("Rip Current Statement", None),
        ("Extreme Heat Warning", None),
    ],
)
def test_keeps_only_road_hazards(event: str, category: AlertCategory | None) -> None:
    assert road_hazard_category(event) == category


def test_spans_cover_halfway_to_neighbouring_samples() -> None:
    storm = alert("storm")
    samples = [(0.0, ()), (20.0, (storm,)), (40.0, (storm,)), (60.0, ())]

    [span] = alert_spans(samples, total_m=60.0)

    assert (span.start_m, span.end_m) == (10.0, 50.0)


def test_leaving_and_reentering_an_area_gives_two_spans() -> None:
    storm = alert("storm")
    samples = [(0.0, (storm,)), (20.0, ()), (40.0, (storm,))]

    spans = alert_spans(samples, total_m=40.0)

    assert [(s.start_m, s.end_m) for s in spans] == [(0.0, 10.0), (30.0, 40.0)]


def test_overlapping_alerts_sort_by_start_then_severity() -> None:
    minor, extreme = alert("a", AlertSeverity.MINOR), alert("b", AlertSeverity.EXTREME)
    spans = alert_spans([(0.0, (minor, extreme)), (20.0, ())], total_m=20.0)
    assert [s.alert.id for s in spans] == ["b", "a"]


def test_in_effect_window() -> None:
    storm = alert("storm")
    assert storm.in_effect_between(
        datetime(2026, 11, 3, 17, tzinfo=UTC), datetime(2026, 11, 3, 19, tzinfo=UTC)
    )
    assert not storm.in_effect_between(
        datetime(2026, 11, 3, 19, tzinfo=UTC), datetime(2026, 11, 3, 20, tzinfo=UTC)
    )
