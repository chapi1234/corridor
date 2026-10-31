"""Unit constants and conversions. All thresholds in the brief are US customary."""

from typing import Final

METERS_PER_MILE: Final = 1609.344
KG_PER_LB: Final = 0.45359237
SECONDS_PER_HOUR: Final = 3600


def meters_to_miles(meters: float) -> float:
    return meters / METERS_PER_MILE


def miles_to_meters(miles: float) -> float:
    return miles * METERS_PER_MILE


def lb_to_kg(pounds: float) -> float:
    return pounds * KG_PER_LB
