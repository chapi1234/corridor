"""Request validation and response schemas.

Responses are rendered by ``presenters`` (plain dicts, fast for large heatmap arrays);
the response serializers here document them in OpenAPI and are used by contract tests
to guarantee the presenters never drift from the published schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rest_framework import serializers

from corridor.domain.geometry import LatLon
from corridor.domain.hos import RestKind
from corridor.domain.models import Place
from corridor.domain.ranking import Criterion, Tag
from corridor.domain.risk import Factor, LoadRule
from corridor.planning.models import SAMPLING_INTERVALS_MI, PlanRequest, WarningCode

MAX_LOAD_LB = 120_000


# --------------------------------------------------------------------------- requests
class PlaceSerializer(serializers.Serializer[Place]):
    label = serializers.CharField(max_length=200)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class PlanRequestSerializer(serializers.Serializer[PlanRequest]):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_local = serializers.CharField(
        help_text="Wall-clock departure at the origin, without offset: YYYY-MM-DDTHH:MM."
    )
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=SAMPLING_INTERVALS_MI)
    hos = serializers.BooleanField(
        default=False,
        help_text="Insert FMCSA hours-of-service rest: a 30-min break after 8 h of driving "
        "and a 10-h reset after 11 h.",
    )

    def validate_departure_local(self, value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise serializers.ValidationError("Use the format YYYY-MM-DDTHH:MM.") from exc
        if parsed.tzinfo is not None:
            raise serializers.ValidationError(
                "Send local wall-clock time without an offset; the origin's zone is applied."
            )
        return parsed

    def to_plan_request(self) -> PlanRequest:
        data: dict[str, Any] = self.validated_data
        return PlanRequest(
            origin=_place(data["origin"]),
            destination=_place(data["destination"]),
            departure_local=data["departure_local"],
            load_lb=data["load_lb"],
            interval_mi=int(data["interval_mi"]),
            hos=data["hos"],
        )


class GeocodeQuerySerializer(serializers.Serializer[None]):
    q = serializers.CharField(min_length=2, max_length=120)
    near_lat = serializers.FloatField(min_value=-90, max_value=90, required=False)
    near_lon = serializers.FloatField(min_value=-180, max_value=180, required=False)


class PointQuerySerializer(serializers.Serializer[None]):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


def _place(data: dict[str, Any]) -> Place:
    return Place(label=data["label"], point=LatLon(data["lat"], data["lon"]))


# -------------------------------------------------------------------------- responses
def _choices(enum: Any) -> list[str]:
    return [member.value for member in enum]


class PlaceResultSerializer(serializers.Serializer[None]):
    id = serializers.CharField(allow_blank=True)
    label = serializers.CharField()
    sublabel = serializers.CharField(allow_blank=True)
    lat = serializers.FloatField()
    lon = serializers.FloatField()


class GeocodeResponseSerializer(serializers.Serializer[None]):
    results = PlaceResultSerializer(many=True)


class ReverseResponseSerializer(serializers.Serializer[None]):
    label = serializers.CharField(allow_null=True)


class LocalTimeSerializer(serializers.Serializer[None]):
    utc = serializers.CharField(help_text="ISO 8601, UTC")
    local = serializers.CharField(help_text="ISO 8601 with the local offset")
    tz = serializers.CharField(help_text="IANA time zone")


class WeatherSerializer(serializers.Serializer[None]):
    wind_mph = serializers.FloatField()
    gust_mph = serializers.FloatField()
    rain_in_hr = serializers.FloatField()
    snow_in_hr = serializers.FloatField()
    temperature_f = serializers.FloatField()
    weather_code = serializers.IntegerField()


class FactorLevelsSerializer(serializers.Serializer[None]):
    wind = serializers.IntegerField(min_value=0, max_value=4)
    rain = serializers.IntegerField(min_value=0, max_value=4)
    snow = serializers.IntegerField(min_value=0, max_value=4)


class RiskSerializer(serializers.Serializer[None]):
    level = serializers.IntegerField(min_value=0, max_value=4)
    index = serializers.FloatField(min_value=0, max_value=5)
    driver = serializers.ChoiceField(choices=_choices(Factor))
    factors = FactorLevelsSerializer()
    load_rule = serializers.ChoiceField(choices=_choices(LoadRule), allow_null=True)


class HourlyWindowSerializer(serializers.Serializer[None]):
    start = serializers.CharField()
    gust_mph = serializers.ListField(child=serializers.FloatField(allow_null=True))
    rain_in_hr = serializers.ListField(child=serializers.FloatField(allow_null=True))
    snow_in_hr = serializers.ListField(child=serializers.FloatField(allow_null=True))


class CheckpointSerializer(serializers.Serializer[None]):
    index = serializers.IntegerField()
    mile = serializers.FloatField()
    owned_miles = serializers.FloatField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    eta = LocalTimeSerializer()
    elapsed_s = serializers.IntegerField(help_text="Seconds after departure, including rest.")
    driving_s = serializers.IntegerField(help_text="Driving time to reach the checkpoint.")
    line_fraction = serializers.FloatField(min_value=0, max_value=1)
    weather = WeatherSerializer(allow_null=True)
    risk = RiskSerializer(allow_null=True)
    hourly = HourlyWindowSerializer(allow_null=True)


class RouteSummarySerializer(serializers.Serializer[None]):
    miles_by_level = serializers.ListField(
        child=serializers.FloatField(),
        min_length=5,
        max_length=5,
        help_text="Miles at Low, Moderate, High, Severe, No Travel.",
    )
    unknown_miles = serializers.FloatField()
    average_risk = serializers.FloatField(allow_null=True)
    worst_checkpoint = serializers.IntegerField(allow_null=True)


class RestStopSerializer(serializers.Serializer[None]):
    kind = serializers.ChoiceField(choices=_choices(RestKind))
    start = LocalTimeSerializer()
    start_s = serializers.IntegerField(help_text="Seconds after departure when the rest begins.")
    duration_s = serializers.IntegerField()
    mile = serializers.FloatField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()


class RouteSerializer(serializers.Serializer[None]):
    id = serializers.CharField()
    source = serializers.ChoiceField(choices=["primary", "alternative", "via"])
    distance_mi = serializers.FloatField()
    duration_s = serializers.IntegerField(help_text="Door-to-door time, including any rest.")
    driving_s = serializers.IntegerField()
    arrival = LocalTimeSerializer()
    highways = serializers.ListField(child=serializers.CharField())
    geometry = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
        help_text="Simplified [lon, lat] pairs.",
    )
    tags = serializers.ListField(child=serializers.ChoiceField(choices=_choices(Tag)))
    summary = RouteSummarySerializer()
    rest_stops = RestStopSerializer(many=True)
    checkpoints = CheckpointSerializer(many=True)


class RecommendationSerializer(serializers.Serializer[None]):
    route_id = serializers.CharField()
    competitor_id = serializers.CharField(allow_null=True)
    deciding_criterion = serializers.ChoiceField(
        choices=[c.slug for c in Criterion], allow_null=True
    )
    beats_on = serializers.DictField(
        child=serializers.ChoiceField(choices=[c.slug for c in Criterion], allow_null=True)
    )
    order = serializers.ListField(child=serializers.CharField())
    criteria = serializers.ListField(child=serializers.CharField())
    keys = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()))
    reason = serializers.CharField()
    no_safe_route = serializers.BooleanField()


class HeatmapSerializer(serializers.Serializer[None]):
    base_time = serializers.CharField()
    hours = serializers.IntegerField()
    points = serializers.ListField(child=serializers.ListField(child=serializers.FloatField()))
    spacing_m = serializers.FloatField(help_text="Grid spacing in metres.")
    gust_mph_x10 = serializers.ListField(
        child=serializers.ListField(child=serializers.IntegerField())
    )
    rain_in_hr_x1000 = serializers.ListField(
        child=serializers.ListField(child=serializers.IntegerField())
    )
    snow_in_hr_x100 = serializers.ListField(
        child=serializers.ListField(child=serializers.IntegerField())
    )
    missing = serializers.IntegerField()


class WarningSerializer(serializers.Serializer[None]):
    code = serializers.ChoiceField(choices=_choices(WarningCode))
    message = serializers.CharField()


class InputsSerializer(serializers.Serializer[None]):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    load_lb = serializers.FloatField()
    interval_mi = serializers.IntegerField()
    hos = serializers.BooleanField()
    wind_metric = serializers.CharField()


class MetaSerializer(serializers.Serializer[None]):
    timings_ms = serializers.DictField(child=serializers.IntegerField())
    routing_source = serializers.CharField()
    weather_source = serializers.CharField()


class PlanResponseSerializer(serializers.Serializer[None]):
    plan_id = serializers.CharField()
    generated_at = serializers.CharField()
    departure = LocalTimeSerializer()
    inputs = InputsSerializer()
    routes = RouteSerializer(many=True)
    recommendation = RecommendationSerializer()
    heatmap = HeatmapSerializer()
    warnings = WarningSerializer(many=True)
    meta = MetaSerializer()
