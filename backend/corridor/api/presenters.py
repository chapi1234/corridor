"""Render planning results as JSON-ready dicts (schema: ``serializers.PlanResponseSerializer``)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

from shapely import LineString

from corridor.domain.models import Place
from corridor.domain.ranking import Criterion
from corridor.domain.risk import Classification, Level
from corridor.domain.units import meters_to_miles
from corridor.domain.weather import WeatherSample
from corridor.planning.frames import MISSING
from corridor.planning.models import (
    Checkpoint,
    HourlyWindow,
    Plan,
    PlannedRest,
    PlannedRoute,
    PlanRequest,
    RouteAlert,
)

GEOMETRY_TOLERANCE_DEG: Final = 0.0003  # ~30 m; keeps lines crisp at highway zoom levels
COORD_DECIMALS: Final = 5


def plan_id(request: PlanRequest) -> str:
    payload = json.dumps(
        {
            "o": [request.origin.point.lat, request.origin.point.lon],
            "d": [request.destination.point.lat, request.destination.point.lon],
            "t": request.departure_local.isoformat(timespec="minutes"),
            "w": request.load_lb,
            "i": request.interval_mi,
            "h": request.hos,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def present_plan(plan: Plan) -> dict[str, Any]:
    ranking = plan.ranking
    return {
        "plan_id": plan_id(plan.request),
        "generated_at": _iso_utc(plan.generated_at),
        "departure": _local_time(plan.departure, plan.origin_tz),
        "inputs": {
            "origin": _place(plan.request.origin),
            "destination": _place(plan.request.destination),
            "load_lb": plan.request.load_lb,
            "interval_mi": plan.request.interval_mi,
            "hos": plan.request.hos,
            "wind_metric": "gust",
        },
        "routes": [_route(route, plan.destination_tz) for route in plan.routes],
        "recommendation": {
            "route_id": ranking.recommended,
            "competitor_id": ranking.competitor,
            "deciding_criterion": ranking.deciding.slug if ranking.deciding is not None else None,
            "beats_on": {
                rid: c.slug if c is not None else None for rid, c in ranking.beats_on.items()
            },
            "order": list(ranking.order),
            "criteria": [c.slug for c in Criterion],
            "keys": {rid: list(key) for rid, key in ranking.keys.items()},
            "reason": ranking.reason,
            "no_safe_route": ranking.no_safe_route,
        },
        "heatmap": {
            "base_time": _iso_utc(plan.heatmap.base_time),
            "hours": len(plan.heatmap.gust_mph_x10),
            "points": [_lonlat(p.lon, p.lat) for p in plan.heatmap.points],
            "spacing_m": round(plan.heatmap.spacing_m),
            "gust_mph_x10": [list(row) for row in plan.heatmap.gust_mph_x10],
            "rain_in_hr_x1000": [list(row) for row in plan.heatmap.rain_in_hr_x1000],
            "snow_in_hr_x100": [list(row) for row in plan.heatmap.snow_in_hr_x100],
            "missing": MISSING,
        },
        "warnings": [{"code": w.code.value, "message": w.message} for w in plan.warnings],
        "meta": {
            "timings_ms": plan.timings_ms,
            "routing_source": plan.routing_source,
            "weather_source": "Open-Meteo forecast (best match)",
        },
    }


def _route(route: PlannedRoute, destination_tz: ZoneInfo) -> dict[str, Any]:
    risk = route.risk
    worst = max(
        (c for c in route.checkpoints if c.classification is not None),
        key=lambda c: c.classification.index if c.classification else 0.0,
        default=None,
    )
    simplified = LineString([(p.lon, p.lat) for p in route.candidate.points]).simplify(
        GEOMETRY_TOLERANCE_DEG, preserve_topology=False
    )
    return {
        "id": route.id,
        "source": route.candidate.source,
        "distance_mi": round(meters_to_miles(route.candidate.length_m), 2),
        "duration_s": round(route.trip_s),
        "driving_s": round(route.candidate.duration_s),
        "arrival": _local_time(route.arrival, destination_tz),
        "highways": list(route.candidate.highways),
        "geometry": [_lonlat(x, y) for x, y in simplified.coords],
        "tags": [tag.value for tag in route.tags],
        "summary": {
            "miles_by_level": [round(risk.miles_by_level[level], 2) for level in Level],
            "unknown_miles": round(risk.unknown_miles, 2),
            "average_risk": None if risk.average_risk is None else round(risk.average_risk, 3),
            "worst_checkpoint": worst.position.index if worst else None,
        },
        "rest_stops": [_rest(r) for r in route.rests],
        "alerts": [_alert(a) for a in route.alerts],
        "checkpoints": [_checkpoint(c) for c in route.checkpoints],
    }


def _rest(rest: PlannedRest) -> dict[str, Any]:
    return {
        "kind": rest.kind.value,
        "start": _local_time(rest.start, rest.tz),
        "start_s": round(rest.trip_s),
        "duration_s": round(rest.duration_s),
        "mile": round(meters_to_miles(rest.distance_m), 2),
        "lat": round(rest.point.lat, COORD_DECIMALS),
        "lon": round(rest.point.lon, COORD_DECIMALS),
    }


def _alert(placed: RouteAlert) -> dict[str, Any]:
    alert = placed.alert
    return {
        "id": alert.id,
        "event": alert.event,
        "category": alert.category.value,
        "severity": alert.severity.value,
        "headline": alert.headline,
        "area": alert.area,
        "starts": _local_time(alert.starts, placed.tz) if alert.starts else None,
        "ends": _local_time(alert.ends, placed.tz) if alert.ends else None,
        "start_mi": round(meters_to_miles(placed.start_m), 2),
        "end_mi": round(meters_to_miles(placed.end_m), 2),
        "enter": _local_time(placed.enter, placed.tz),
        "exit": _local_time(placed.exit, placed.tz),
        "in_effect": placed.in_effect,
    }


def _checkpoint(checkpoint: Checkpoint) -> dict[str, Any]:
    position = checkpoint.position
    return {
        "index": position.index,
        "mile": round(meters_to_miles(position.distance_m), 2),
        "owned_miles": round(meters_to_miles(position.owned_m), 3),
        "lat": round(position.point.lat, COORD_DECIMALS),
        "lon": round(position.point.lon, COORD_DECIMALS),
        "eta": _local_time(checkpoint.eta, checkpoint.tz),
        "elapsed_s": round(checkpoint.trip_s),
        "driving_s": round(position.elapsed_s),
        "line_fraction": round(checkpoint.line_fraction, 6),
        "weather": _weather(checkpoint.weather) if checkpoint.weather else None,
        "risk": _risk(checkpoint.classification) if checkpoint.classification else None,
        "hourly": _hourly(checkpoint.hourly) if checkpoint.hourly else None,
    }


def _weather(sample: WeatherSample) -> dict[str, Any]:
    return {
        "wind_mph": round(sample.wind_mph, 1),
        "gust_mph": round(sample.gust_mph, 1),
        "rain_in_hr": round(sample.rain_in_hr, 3),
        "snow_in_hr": round(sample.snow_in_hr, 2),
        "temperature_f": round(sample.temperature_f, 1),
        "weather_code": sample.weather_code,
    }


def _risk(classification: Classification) -> dict[str, Any]:
    return {
        "level": int(classification.level),
        "index": round(classification.index, 3),
        "driver": classification.driver.value,
        "factors": {f.value: int(a.level) for f, a in classification.factors.items()},
        "load_rule": classification.load_rule.value if classification.load_rule else None,
    }


def _hourly(window: HourlyWindow) -> dict[str, Any]:
    def rounded(values: tuple[float | None, ...], digits: int) -> list[float | None]:
        return [None if v is None else round(v, digits) for v in values]

    return {
        "start": _iso_utc(window.start),
        "gust_mph": rounded(window.gust_mph, 1),
        "rain_in_hr": rounded(window.rain_in_hr, 3),
        "snow_in_hr": rounded(window.snow_in_hr, 2),
    }


def _place(place: Place) -> dict[str, Any]:
    return {"label": place.label, "lat": place.point.lat, "lon": place.point.lon}


def _local_time(moment: datetime, tz: ZoneInfo) -> dict[str, str]:
    return {
        "utc": _iso_utc(moment),
        "local": moment.astimezone(tz).isoformat(timespec="minutes"),
        "tz": tz.key,
    }


def _iso_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _lonlat(lon: float, lat: float) -> list[float]:
    return [round(lon, COORD_DECIMALS), round(lat, COORD_DECIMALS)]
