"""Official weather alerts (NWS) and where they fall along a route.

Alerts are advisory: they are shown beside the rule-based risk, never folded into it, so
the ranking stays a deterministic function of the forecast (D9). Only hazards that affect
a truck on the road are kept; marine, beach and agricultural products are dropped.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Final


class AlertSeverity(StrEnum):
    """CAP severity, most severe first."""

    EXTREME = "extreme"
    SEVERE = "severe"
    MODERATE = "moderate"
    MINOR = "minor"
    UNKNOWN = "unknown"

    @property
    def rank(self) -> int:
        return list(AlertSeverity).index(self)


class AlertCategory(StrEnum):
    WINTER = "winter"
    WIND = "wind"
    VISIBILITY = "visibility"
    STORM = "storm"
    FLOOD = "flood"
    TROPICAL = "tropical"
    OTHER = "other"


# Checked in order; the first keyword found in the event name decides the category.
_CATEGORY_KEYWORDS: Final[tuple[tuple[str, AlertCategory], ...]] = (
    ("Hurricane", AlertCategory.TROPICAL),
    ("Tropical", AlertCategory.TROPICAL),
    ("Storm Surge", AlertCategory.TROPICAL),
    ("Blizzard", AlertCategory.WINTER),
    ("Ice Storm", AlertCategory.WINTER),
    ("Winter", AlertCategory.WINTER),
    ("Snow", AlertCategory.WINTER),
    ("Freezing", AlertCategory.WINTER),
    ("Wind Chill", AlertCategory.WINTER),
    ("Cold", AlertCategory.WINTER),
    ("Avalanche", AlertCategory.WINTER),
    ("Wind", AlertCategory.WIND),
    ("Dust", AlertCategory.WIND),
    ("Fog", AlertCategory.VISIBILITY),
    ("Smoke", AlertCategory.VISIBILITY),
    ("Tornado", AlertCategory.STORM),
    ("Thunderstorm", AlertCategory.STORM),
    ("Flood", AlertCategory.FLOOD),
    ("Special Weather Statement", AlertCategory.OTHER),
)
_OFF_ROAD: Final = (
    "Marine",
    "Small Craft",
    "Gale",
    "Rip Current",
    "Beach",
    "Surf",
    "Coastal",
    "Lakeshore",
    "Lake Wind",
    "Brisk Wind",
    "Hazardous Seas",
    "Freezing Spray",
    "Frost",
    "Freeze Watch",
    "Freeze Warning",
    "Hydrologic Outlook",
    "Fire Weather",
    "Red Flag",
)


def road_hazard_category(event: str) -> AlertCategory | None:
    """Category of an alert that matters on the road, or ``None`` to ignore it."""
    if any(term in event for term in _OFF_ROAD):
        return None
    return next((cat for keyword, cat in _CATEGORY_KEYWORDS if keyword in event), None)


@dataclass(frozen=True, slots=True)
class WeatherAlert:
    id: str
    event: str
    category: AlertCategory
    severity: AlertSeverity
    headline: str
    area: str
    starts: datetime | None
    """Hazard onset; ``None`` when already under way."""
    ends: datetime | None
    """Hazard end; ``None`` when open-ended."""

    def in_effect_between(self, start: datetime, end: datetime) -> bool:
        return (self.starts is None or self.starts <= end) and (
            self.ends is None or self.ends >= start
        )


@dataclass(frozen=True, slots=True)
class AlertSpan:
    """A stretch of route inside one alert's area."""

    alert: WeatherAlert
    start_m: float
    end_m: float


def alert_spans(
    samples: Sequence[tuple[float, Sequence[WeatherAlert]]], *, total_m: float
) -> list[AlertSpan]:
    """Contiguous stretches covered by each alert, from alerts found at sampled distances.

    ``samples`` are ``(distance_m, alerts at that point)`` in route order. Each sample stands
    for the route halfway to its neighbours; leaving and re-entering an area gives two spans.
    """
    if not samples:
        return []
    distances = [d for d, _ in samples]
    bounds = [0.0, *((a + b) / 2 for a, b in pairwise(distances)), total_m]

    spans: list[AlertSpan] = []
    open_spans: dict[str, AlertSpan] = {}
    for i, (_, alerts) in enumerate(samples):
        present = {a.id: a for a in alerts}
        for alert_id in list(open_spans):
            if alert_id not in present:
                spans.append(open_spans.pop(alert_id))
        for alert_id, alert in present.items():
            current = open_spans.get(alert_id)
            open_spans[alert_id] = AlertSpan(
                alert, current.start_m if current else bounds[i], bounds[i + 1]
            )
    spans.extend(open_spans.values())
    return sorted(spans, key=lambda s: (s.start_m, s.alert.severity.rank))
