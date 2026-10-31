"""Errors raised by planning and by the providers it depends on."""

from __future__ import annotations


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

    def __init__(self, service: str, message: str, *, status: int | None = None) -> None:
        super().__init__(f"{service}: {message}")
        self.service = service
        self.message = message
        self.status = status
