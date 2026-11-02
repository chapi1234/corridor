"""Departure advisor: would leaving earlier or later expose the truck to less weather?

The same routes are re-scored with every checkpoint's ETA shifted by the departure offset
(HOS rests move with the truck, so trip timing is unchanged). Each offset is ranked exactly
like the plan itself, then compared with the chosen departure.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from corridor.domain.ranking import Criterion, Ranking, RouteRisk

MIN_GAIN_MI: Final = 10
"""Smallest drop in exposure on the deciding criterion worth suggesting a new time for."""
UNKNOWN_TOLERANCE_MI: Final = 10
"""Unforecast miles are not counted as risk (D19), so an option may not look safer merely
because more of it falls outside the forecast."""
EXPOSURE_CRITERIA: Final = (Criterion.NO_TRAVEL_MILES, Criterion.SEVERE_MILES, Criterion.HIGH_MILES)


@dataclass(frozen=True, slots=True)
class DepartureOption:
    offset_h: int
    departure: datetime
    ranking: Ranking
    risks: tuple[RouteRisk, ...]

    @property
    def best(self) -> RouteRisk:
        return next(r for r in self.risks if r.route_id == self.ranking.recommended)

    @property
    def exposure(self) -> tuple[int, ...]:
        key = self.ranking.keys[self.ranking.recommended]
        return tuple(key[c] for c in EXPOSURE_CRITERIA)


@dataclass(frozen=True, slots=True)
class DepartureSuggestion:
    option: DepartureOption
    criterion: Criterion
    gain_mi: int
    """Miles fewer on ``criterion`` than the chosen departure, on each one's best route."""


def suggest(options: Sequence[DepartureOption]) -> DepartureSuggestion | None:
    """The best clearly safer departure, nearest the chosen one on ties; ``None`` if none."""
    current = next((o for o in options if o.offset_h == 0), None)
    if current is None:
        return None

    def gain(option: DepartureOption) -> tuple[Criterion, int] | None:
        if option.best.unknown_miles > current.best.unknown_miles + UNKNOWN_TOLERANCE_MI:
            return None
        for criterion, mine, theirs in zip(
            EXPOSURE_CRITERIA, option.exposure, current.exposure, strict=True
        ):
            if mine != theirs:
                return (criterion, theirs - mine) if theirs - mine >= MIN_GAIN_MI else None
        return None

    candidates = [(o, g) for o in options if o.offset_h != 0 and (g := gain(o)) is not None]
    if not candidates:
        return None
    option, (criterion, gained) = min(
        candidates, key=lambda c: (c[0].exposure, abs(c[0].offset_h), c[0].offset_h)
    )
    return DepartureSuggestion(option, criterion, gained)
