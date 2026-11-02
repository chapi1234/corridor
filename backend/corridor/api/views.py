"""HTTP endpoints. Views only parse, delegate and render; logic lives in ``planning``."""

from __future__ import annotations

from typing import Any, Final

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from corridor.api import dependencies
from corridor.api.errors import problem
from corridor.api.presenters import plan_id, present_plan
from corridor.api.serializers import (
    GeocodeQuerySerializer,
    GeocodeResponseSerializer,
    PlanRequestSerializer,
    PlanResponseSerializer,
    PointQuerySerializer,
    ReverseResponseSerializer,
    TimezoneResponseSerializer,
)
from corridor.domain.geometry import LatLon
from corridor.domain.models import Place
from corridor.integrations.timezones import timezone_at
from corridor.planning.models import PlanRequest

PLAN_CACHE_TTL_S: Final = 10 * 60
"""Identical requests within this window reuse the computed plan."""
SNAPSHOT_TTL_S: Final = 7 * 24 * 60 * 60
"""Shared links keep showing the plan as it was computed for this long."""


def snapshot_key(plan_id: str) -> str:
    return f"snapshot:v1:{plan_id}"


class PlanView(APIView):
    throttle_scope = "plans"

    @extend_schema(
        request=PlanRequestSerializer,
        responses={200: PlanResponseSerializer},
        summary="Plan weather-aware truck routes",
        description=(
            "Returns up to three routes with checkpoints sampled at the chosen interval, "
            "the forecast at each checkpoint's ETA, risk levels, a recommendation and a "
            "0-48 h corridor heatmap."
        ),
    )
    def post(self, request: Request) -> Response:
        serializer = PlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_request = serializer.to_plan_request()

        key = f"plan:v1:{plan_id(plan_request)}"
        body = cache.get(key)
        if body is None:
            body = async_to_sync(_build_plan)(plan_request)
            cache.set(key, body, PLAN_CACHE_TTL_S)
            cache.set(snapshot_key(body["plan_id"]), body, SNAPSHOT_TTL_S)
        return Response(body)


class PlanSnapshotView(APIView):
    throttle_scope = "snapshots"

    @extend_schema(
        responses={200: PlanResponseSerializer},
        summary="A previously computed plan, as it was computed",
        description=(
            "Shared links resolve here. The forecast is the one fetched at `generated_at`; "
            "clients should offer to re-plan when it is stale. Snapshots expire after 7 days."
        ),
    )
    def get(self, request: Request, plan_id: str) -> Response:
        body = cache.get(snapshot_key(plan_id))
        if body is None:
            return problem(
                status.HTTP_404_NOT_FOUND,
                "snapshot-not-found",
                "Plan not found",
                "This shared plan has expired or never existed. Plan the trip again.",
            )
        return Response(body)


async def _build_plan(plan_request: PlanRequest) -> dict[str, Any]:
    async with dependencies.planning_service() as service:
        return present_plan(await service.build(plan_request))


class GeocodeView(APIView):
    throttle_scope = "geocode"

    @extend_schema(
        parameters=[GeocodeQuerySerializer],
        responses={200: GeocodeResponseSerializer},
        summary="Autocomplete places (US & Canada)",
    )
    def get(self, request: Request) -> Response:
        query = GeocodeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        near = (
            LatLon(data["near_lat"], data["near_lon"])
            if "near_lat" in data and "near_lon" in data
            else None
        )
        places = async_to_sync(_search)(data["q"], near)
        return Response({"results": [_place(p) for p in places]})


async def _search(query: str, near: LatLon | None) -> list[Place]:
    async with dependencies.geocoder() as geocoder:
        return await geocoder.search(query, near=near)


class ReverseGeocodeView(APIView):
    throttle_scope = "geocode"

    @extend_schema(
        parameters=[
            OpenApiParameter("lat", float, required=True),
            OpenApiParameter("lon", float, required=True),
        ],
        responses={200: ReverseResponseSerializer},
        summary="Nearest locality for a coordinate",
    )
    def get(self, request: Request) -> Response:
        query = PointQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        point = LatLon(query.validated_data["lat"], query.validated_data["lon"])
        place = async_to_sync(_reverse)(point)
        return Response({"label": place.label if place else None})


async def _reverse(point: LatLon) -> Place | None:
    async with dependencies.geocoder() as geocoder:
        return await geocoder.reverse(point)


class TimezoneView(APIView):
    """Departures are wall-clock time at the origin (D14); the form needs that zone to offer
    sensible defaults and say which clock it means."""

    throttle_scope = "geocode"

    @extend_schema(
        parameters=[
            OpenApiParameter("lat", float, required=True),
            OpenApiParameter("lon", float, required=True),
        ],
        responses={200: TimezoneResponseSerializer},
        summary="IANA time zone at a coordinate",
    )
    def get(self, request: Request) -> Response:
        query = PointQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        point = LatLon(query.validated_data["lat"], query.validated_data["lon"])
        return Response({"tz": timezone_at(point).key})


class HealthView(APIView):
    throttle_classes: list[Any] = []

    @extend_schema(exclude=True)
    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "version": settings.APP_VERSION})


def _place(place: Place) -> dict[str, Any]:
    return {
        "id": place.id,
        "label": place.label,
        "sublabel": place.sublabel,
        "lat": place.point.lat,
        "lon": place.point.lon,
    }
