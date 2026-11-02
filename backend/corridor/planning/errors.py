"""Errors raised by planning and by the providers it depends on."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from corridor.domain.geometry import LatLon
    from corridor.domain.weather import HourlySeries


class PlanningError(Exception):
    """Base class for failures the API reports to clients."""


class InvalidPlanRequestError(PlanningError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class RouteNotFoundError(PlanningError):
    """No drivable route exists between the requested places."""


class UpstreamServiceError(PlanningError):
    """A third-party service failed or returned something unusable."""

    def __init__(
        self,
        service: str,
        message: str,
        *,
        status: int | None = None,
        retry_after_s: int | None = None,
    ) -> None:
        super().__init__(f"{service}: {message}")
        self.service = service
        self.message = message
        self.status = status
        self.retry_after_s = retry_after_s

    @property
    def rate_limited(self) -> bool:
        return self.status == 429

    @property
    def quota_window(self) -> str | None:
        """Which quota a 429 refers to: "day", "hour" or "minute" (from the provider's
        reason text); ``None`` if not a quota rejection or the window is unstated."""
        if not self.rate_limited:
            return None
        text = self.message.lower()
        windows = (("daily", "day"), ("hourly", "hour"), ("minutely", "minute"))
        return next((window for word, window in windows if word in text), None)


class IncompleteForecastError(UpstreamServiceError):
    """Some forecast batches failed; ``partial`` holds the locations that succeeded.

    Lets the cache keep what was fetched, so a retry only requests the missing locations.
    """

    def __init__(self, cause: UpstreamServiceError, partial: Mapping[LatLon, HourlySeries]) -> None:
        super().__init__(
            cause.service, cause.message, status=cause.status, retry_after_s=cause.retry_after_s
        )
        self.partial = partial
