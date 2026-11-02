"""RFC 9457 problem details for every error the API returns."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from corridor.planning.errors import (
    InvalidPlanRequestError,
    RouteNotFoundError,
    UpstreamServiceError,
)

logger = logging.getLogger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"
UPSTREAM_RETRY_AFTER_S = 60
"""Open-Meteo's free-tier limit is per minute and it sends no Retry-After header."""


def problem(status_code: int, kind: str, title: str, detail: str, **extra: Any) -> Response:
    body = {"type": f"/problems/{kind}", "title": title, "status": status_code, "detail": detail}
    return Response(body | extra, status=status_code, content_type=PROBLEM_CONTENT_TYPE)


def problem_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    match exc:
        case InvalidPlanRequestError():
            return problem(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "invalid-request",
                "Invalid plan request",
                exc.message,
                errors={exc.field: [exc.message]},
            )
        case RouteNotFoundError():
            return problem(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "no-route", "No route found", str(exc)
            )
        case UpstreamServiceError() if exc.rate_limited:
            logger.warning("Upstream rate limit: %s", exc)
            retry_after_s = exc.retry_after_s or UPSTREAM_RETRY_AFTER_S
            busy = problem(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "upstream-rate-limited",
                "Weather provider is busy",
                f"The {exc.service} service limits how many forecasts can be fetched per "
                f"minute. Try again in about {retry_after_s} seconds; forecasts already "
                "fetched are kept, so the retry is faster.",
                service=exc.service,
                retry_after_s=retry_after_s,
            )
            busy["Retry-After"] = str(retry_after_s)
            return busy
        case UpstreamServiceError():
            logger.warning("Upstream failure: %s", exc)
            return problem(
                status.HTTP_502_BAD_GATEWAY,
                "upstream-unavailable",
                "A data provider is unavailable",
                f"The {exc.service} service could not complete the request. Try again shortly.",
                service=exc.service,
            )
        case exceptions.ValidationError():
            return problem(
                status.HTTP_400_BAD_REQUEST,
                "validation",
                "Invalid input",
                "One or more fields are invalid.",
                errors=exc.detail,
            )
        case exceptions.Throttled():
            return problem(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "rate-limited",
                "Too many requests",
                str(exc.detail),
            )

    response = exception_handler(exc, context)
    if response is not None:
        detail = response.data.get("detail", "") if isinstance(response.data, dict) else ""
        return problem(response.status_code, "error", "Request failed", str(detail))
    logger.exception("Unhandled API error", exc_info=exc)
    return None
