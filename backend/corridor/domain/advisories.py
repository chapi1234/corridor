"""Road advisories beyond the brief's risk table: crosswind, ice and visibility.

Like NWS alerts these are advisory only. The risk level stays the brief's wind/rain/snow
table (D9); advisories explain hazards the table cannot see, such as a 30 mph gust that is
harmless head-on but pushes a high-profile trailer when it hits broadside.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from corridor.domain.weather import WeatherSample

CROSSWIND_ADVISORY_MPH: Final = 30.0
"""Broadside gusts at which empty and light high-profile trailers start to be pushed."""
NEAR_FREEZING_F: Final = 34.0
"""Air a little above freezing still leaves bridges and overpasses icy."""
FREEZING_PRECIP_CODES: Final = frozenset({56, 57, 66, 67})
"""WMO weather codes for freezing drizzle and freezing rain."""
DENSE_FOG_MI: Final = 0.25
LOW_VISIBILITY_MI: Final = 1.0


class AdvisoryKind(StrEnum):
    CROSSWIND = "crosswind"
    ICE = "ice"
    VISIBILITY = "visibility"


@dataclass(frozen=True, slots=True)
class Advisory:
    kind: AdvisoryKind
    message: str


def crosswind_mph(gust_mph: float, wind_from_deg: float, heading_deg: float) -> float:
    """Gust component perpendicular to the direction of travel."""
    return abs(gust_mph * math.sin(math.radians(wind_from_deg - heading_deg)))


def advisories(sample: WeatherSample, heading_deg: float) -> tuple[Advisory, ...]:
    """Advisories for a truck heading ``heading_deg`` (clockwise from north) in ``sample``."""
    found: list[Advisory] = []

    if not math.isnan(sample.wind_direction_deg):
        cross = crosswind_mph(sample.gust_mph, sample.wind_direction_deg, heading_deg)
        if cross >= CROSSWIND_ADVISORY_MPH:
            found.append(
                Advisory(
                    AdvisoryKind.CROSSWIND,
                    f"{round(cross)} mph crosswind gusts; empty and light trailers are most "
                    "at risk of being pushed.",
                )
            )

    if sample.weather_code in FREEZING_PRECIP_CODES:
        found.append(
            Advisory(AdvisoryKind.ICE, "Freezing rain or drizzle; expect ice on the road.")
        )
    elif sample.rain_in_hr > 0 and sample.temperature_f <= NEAR_FREEZING_F:
        found.append(
            Advisory(
                AdvisoryKind.ICE,
                f"Rain at {round(sample.temperature_f)}°F; black ice is possible on bridges "
                "and overpasses.",
            )
        )

    visibility = sample.visibility_mi
    if not math.isnan(visibility) and visibility < LOW_VISIBILITY_MI:
        label = "Dense fog" if visibility < DENSE_FOG_MI else "Reduced visibility"
        found.append(Advisory(AdvisoryKind.VISIBILITY, f"{label}: visibility {visibility:.2f} mi."))

    return tuple(found)
