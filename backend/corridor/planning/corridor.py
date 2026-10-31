"""Sampling grid for the weather heatmap along the trip corridor."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import shapely
from shapely import LineString

from corridor.domain.geometry import LatLon
from corridor.planning.config import PlanningConfig
from corridor.planning.projection import LocalProjection

_SIMPLIFY_M = 1_000.0
_HEX_ROW_FACTOR = math.sqrt(3) / 2


def corridor_grid(
    lines: Sequence[LineString], projection: LocalProjection, config: PlanningConfig
) -> list[LatLon]:
    """Hexagonal grid of points covering the union of buffers around ``lines``.

    Spacing adapts to the corridor's area so the point count stays near the target
    regardless of trip length, within the configured minimum and maximum spacing.
    """
    area = shapely.union_all(
        [line.buffer(config.corridor_half_width_m) for line in lines]
    ).simplify(_SIMPLIFY_M)
    spacing = math.sqrt(area.area / (config.heatmap_target_points * _HEX_ROW_FACTOR))
    spacing = min(max(spacing, config.heatmap_min_spacing_m), config.heatmap_max_spacing_m)

    min_x, min_y, max_x, max_y = area.bounds
    row_step = spacing * _HEX_ROW_FACTOR
    rows = np.arange(min_y, max_y + row_step, row_step)
    cols = np.arange(min_x, max_x + spacing, spacing)
    xs = (cols[None, :] + (np.arange(len(rows)) % 2)[:, None] * spacing / 2).ravel()
    ys = np.repeat(rows, len(cols))

    inside = shapely.contains_xy(area, xs, ys)
    return projection.to_latlon(xs[inside], ys[inside])


def snap(point: LatLon, step_deg: float) -> LatLon:
    """Snap to a regular lat/lon grid so nearby requests share one weather location."""
    return LatLon(
        round(round(point.lat / step_deg) * step_deg, 4),
        round(round(point.lon / step_deg) * step_deg, 4),
    )
