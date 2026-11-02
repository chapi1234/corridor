from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from corridor.domain.geometry import LatLon
from corridor.domain.ranking import Criterion, Tag
from corridor.domain.risk import Level, LoadRule
from corridor.planning.config import PlanningConfig
from corridor.planning.errors import IncompleteForecastError, InvalidPlanRequestError
from corridor.planning.frames import MISSING
from corridor.planning.models import PlanRequest, WarningCode
from tests.fakes import (
    DENVER,
    KANSAS_CITY,
    SPEED_MPS,
    FakeRouting,
    FakeWeather,
    make_service,
)

REQUEST = PlanRequest(
    origin=DENVER,
    destination=KANSAS_CITY,
    departure_local=datetime(2026, 11, 3, 6, 0),  # 13:00 UTC (MST)
    load_lb=20_000,
    interval_mi=25,
)


def storm_on_direct_line(point: LatLon, _: datetime) -> tuple[float, float, float]:
    """Severe gusts in a band crossed only by the straight Denver-Kansas City line."""
    if 39.0 <= point.lat <= 39.8 and -100.5 <= point.lon <= -98.5:
        return 48.0, 0.0, 0.0
    return 12.0, 0.0, 0.0


async def test_produces_three_distinct_labelled_routes() -> None:
    routing = FakeRouting(direct_alternatives=1)
    plan = await make_service(routing=routing).build(REQUEST)

    assert [r.id for r in plan.routes] == ["A", "B", "C"]
    assert [r.candidate.source for r in plan.routes].count("primary") == 1
    durations = [r.candidate.duration_s for r in plan.routes]
    assert durations == sorted(durations)
    assert plan.warnings == ()


async def test_departure_is_converted_from_origin_local_time() -> None:
    plan = await make_service().build(REQUEST)
    assert plan.departure == datetime(2026, 11, 3, 13, tzinfo=UTC)
    assert plan.heatmap.base_time == plan.departure


async def test_checkpoints_follow_interval_and_eta() -> None:
    plan = await make_service().build(REQUEST)
    route = plan.routes[0]
    checkpoints = route.checkpoints

    assert checkpoints[0].eta == plan.departure
    assert checkpoints[-1].eta == pytest.approx(route.arrival, abs=timedelta(seconds=1))
    assert checkpoints[1].position.distance_m == pytest.approx(25 * 1609.344)
    assert sum(c.position.owned_m for c in checkpoints) == pytest.approx(
        checkpoints[-1].position.distance_m
    )
    assert all(c.classification is not None for c in checkpoints)
    assert checkpoints[3].hourly is not None
    assert len(checkpoints[3].hourly.gust_mph) == 13


async def test_recommends_route_that_avoids_the_storm() -> None:
    plan = await make_service(storm_on_direct_line).build(REQUEST)
    direct = next(r for r in plan.routes if r.candidate.source == "primary")

    assert direct.risk.miles_by_level[Level.SEVERE] > 0
    assert plan.ranking.recommended != direct.id
    assert plan.ranking.deciding == Criterion.SEVERE_MILES
    recommended = next(r for r in plan.routes if r.id == plan.ranking.recommended)
    assert Tag.RECOMMENDED in recommended.tags
    assert Tag.FASTEST in direct.tags


async def test_heavy_load_turns_severe_wind_into_no_travel() -> None:
    plan = await make_service(storm_on_direct_line).build(replace(REQUEST, load_lb=35_000))
    direct = next(r for r in plan.routes if r.candidate.source == "primary")
    stormy = [c for c in direct.checkpoints if c.classification and c.classification.level >= 3]

    assert stormy
    assert all(c.classification.level == Level.NO_TRAVEL for c in stormy)
    assert all(c.classification.load_rule == LoadRule.WIND_45_54_OVER_30K_LB for c in stormy)
    assert plan.ranking.deciding == Criterion.NO_TRAVEL_MILES


async def test_weather_is_read_at_eta_not_departure() -> None:
    storm_hour = datetime(2026, 11, 3, 13, tzinfo=UTC) + timedelta(hours=8)

    def late_storm_everywhere(_: LatLon, moment: datetime) -> tuple[float, float, float]:
        return (60.0, 0.0, 0.0) if moment >= storm_hour else (5.0, 0.0, 0.0)

    plan = await make_service(late_storm_everywhere).build(REQUEST)
    route = plan.routes[0]

    early = [c for c in route.checkpoints if c.eta < storm_hour - timedelta(hours=1)]
    late = [c for c in route.checkpoints if c.eta > storm_hour]
    assert early
    assert late
    assert all(c.classification.level == Level.LOW for c in early)
    assert all(c.classification.level == Level.NO_TRAVEL for c in late)


async def test_heatmap_frames_cover_48_hours() -> None:
    plan = await make_service().build(REQUEST)
    frames = plan.heatmap

    assert len(frames.gust_mph_x10) == 49
    assert len(frames.points) > 20
    assert all(len(row) == len(frames.points) for row in frames.gust_mph_x10)
    assert frames.gust_mph_x10[0][0] == 100  # 10 mph x 10


async def test_unforecast_checkpoints_are_flagged_not_counted_safe() -> None:
    service = make_service()
    service._config = replace(service._config, forecast_horizon=timedelta(hours=10))
    plan = await service.build(REQUEST)

    assert any(w.code == WarningCode.FORECAST_UNAVAILABLE for w in plan.warnings)
    assert all(r.risk.unknown_miles > 0 for r in plan.routes)


async def test_warns_when_fewer_routes_exist() -> None:
    class SingleRouteRouting(FakeRouting):
        async def calculate_routes(self, waypoints, **kwargs):
            return await super().calculate_routes(waypoints[:1] + waypoints[-1:], **kwargs)

    plan = await make_service(routing=SingleRouteRouting()).build(REQUEST)

    assert len(plan.routes) == 1
    assert plan.warnings[0].code == WarningCode.FEWER_ROUTES


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"interval_mi": 15}, "interval_mi"),
        ({"destination": DENVER}, "destination"),
        ({"departure_local": datetime(2026, 11, 3, 1, 0)}, "departure"),
        ({"departure_local": datetime(2026, 11, 30, 6, 0)}, "departure"),
    ],
)
async def test_validation(changes: dict, field: str) -> None:
    with pytest.raises(InvalidPlanRequestError) as excinfo:
        await make_service().build(replace(REQUEST, **changes))
    assert excinfo.value.field == field


async def test_hours_of_service_rest_delays_later_checkpoints() -> None:
    # Denver → Kansas City is ~9.6 h of driving: one 30-minute break at 8 h.
    plain = (await make_service().build(REQUEST)).routes[0]
    rested = (await make_service().build(replace(REQUEST, hos=True))).routes[0]

    assert plain.rests == ()
    assert [r.kind.value for r in rested.rests] == ["break"]
    rest = rested.rests[0]
    assert rest.trip_s == pytest.approx(8 * 3600)
    assert rest.distance_m == pytest.approx(8 * 3600 * SPEED_MPS, rel=1e-3)
    assert rested.trip_s == pytest.approx(plain.trip_s + 1800)
    assert rested.arrival - plain.arrival == timedelta(minutes=30)
    assert rested.risk.duration_s == pytest.approx(rested.trip_s)

    for before, after in zip(plain.checkpoints, rested.checkpoints, strict=True):
        delay = (after.eta - before.eta).total_seconds()
        expected = 1800 if after.position.elapsed_s > 8 * 3600 else 0
        assert delay == pytest.approx(expected, abs=1)
        assert after.trip_s == pytest.approx(after.position.elapsed_s + expected, abs=1)


async def test_long_trips_share_checkpoint_forecasts_to_fit_the_budget() -> None:
    provider = FakeWeather()
    config = PlanningConfig(heatmap_target_points=60, checkpoint_location_budget=80)
    plan = await make_service(config=config, weather_provider=provider).build(
        replace(REQUEST, interval_mi=10)
    )

    assert provider.calls[0] <= 80  # checkpoint locations, fetched first
    assert all(c.classification is not None for r in plan.routes for c in r.checkpoints)
    assert WarningCode.SHARED_FORECASTS in {w.code for w in plan.warnings}


async def test_short_trips_keep_the_finest_forecast_grid() -> None:
    plan = await make_service().build(REQUEST)
    assert WarningCode.SHARED_FORECASTS not in {w.code for w in plan.warnings}


async def test_heatmap_degrades_when_the_provider_rate_limits() -> None:
    provider = FakeWeather(rate_limit_on_call=1)
    plan = await make_service(weather_provider=provider).build(REQUEST)

    assert all(c.classification is not None for r in plan.routes for c in r.checkpoints)
    assert WarningCode.HEATMAP_INCOMPLETE in {w.code for w in plan.warnings}
    first_frame = plan.heatmap.gust_mph_x10[0]
    assert MISSING in first_frame
    assert any(value != MISSING for value in first_frame)  # the half that arrived is kept


async def test_checkpoint_rate_limit_fails_the_plan() -> None:
    provider = FakeWeather(rate_limit_on_call=0)
    with pytest.raises(IncompleteForecastError) as caught:
        await make_service(weather_provider=provider).build(REQUEST)
    assert caught.value.rate_limited
