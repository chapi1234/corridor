"""Metric projection for buffering and comparing routes."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from pyproj import CRS, Transformer
from shapely import LineString

from corridor.domain.geometry import LatLon

_MIN_PARALLEL_SPREAD_DEG = 1.0


class LocalProjection:
    """Albers equal-area projection fitted to the area of interest, in metres.

    Fitting the standard parallels to the data keeps distance distortion negligible at
    trip scale anywhere in North America, unlike a single national projection.
    """

    def __init__(self, points: Sequence[LatLon]) -> None:
        if not points:
            raise ValueError("Projection needs at least one point")
        lats = [p.lat for p in points]
        lons = [p.lon for p in points]
        south, north = min(lats), max(lats)
        if north - south < _MIN_PARALLEL_SPREAD_DEG:
            mid = (north + south) / 2
            south, north = mid - _MIN_PARALLEL_SPREAD_DEG / 2, mid + _MIN_PARALLEL_SPREAD_DEG / 2
        spread = north - south
        crs = CRS.from_proj4(
            f"+proj=aea +lat_1={south + spread / 6} +lat_2={north - spread / 6} "
            f"+lat_0={(south + north) / 2} +lon_0={(min(lons) + max(lons)) / 2} "
            "+datum=WGS84 +units=m +no_defs"
        )
        self._forward = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self._inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    def line(self, points: Sequence[LatLon]) -> LineString:
        xs, ys = self._forward.transform([p.lon for p in points], [p.lat for p in points])
        return LineString(np.column_stack((xs, ys)))

    def to_xy(self, point: LatLon) -> tuple[float, float]:
        x, y = self._forward.transform(point.lon, point.lat)
        return float(x), float(y)

    def to_latlon(self, xs: NDArray[np.float64], ys: NDArray[np.float64]) -> list[LatLon]:
        lons, lats = self._inverse.transform(xs, ys)
        return [LatLon(float(lat), float(lon)) for lon, lat in zip(lons, lats, strict=True)]
