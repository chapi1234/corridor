"""Shared HTTP helpers: JSON GETs with bounded retries and uniform error mapping."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from typing import Any, Final

import httpx

from corridor.planning.errors import UpstreamServiceError

# 429 is deliberately absent: providers rate-limit per minute, so a retry within the
# request only burns more quota. The caller gets the provider's Retry-After instead.
RETRYABLE_STATUS: Final = frozenset({500, 502, 503, 504})
DEFAULT_TIMEOUT: Final = httpx.Timeout(10.0, connect=3.0)
_MAX_ERROR_BODY: Final = 300


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    service: str,
    params: Mapping[str, str | int | float] | None = None,
    retries: int = 2,
    backoff_s: float = 0.4,
) -> Any:
    """GET ``url`` and decode JSON, retrying transient failures with jittered backoff."""
    error: UpstreamServiceError | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.get(url, params=params)
        except httpx.TransportError as exc:
            error = UpstreamServiceError(service, f"network error ({type(exc).__name__})")
        else:
            if response.is_success:
                try:
                    return response.json()
                except ValueError as exc:
                    raise UpstreamServiceError(service, "invalid JSON response") from exc
            error = UpstreamServiceError(
                service,
                _describe(response),
                status=response.status_code,
                retry_after_s=_retry_after(response),
            )
            if response.status_code not in RETRYABLE_STATUS:
                raise error
        if attempt < retries:
            await asyncio.sleep(backoff_s * (2**attempt) * (1 + random.random() / 2))
    assert error is not None
    raise error


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("retry-after", "")
    return int(value) if value.isdigit() else None


def _describe(response: httpx.Response) -> str:
    body = response.text[:_MAX_ERROR_BODY].strip()
    return f"HTTP {response.status_code}" + (f": {body}" if body else "")
