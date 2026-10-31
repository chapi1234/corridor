import pytest

from corridor.domain.geometry import LatLon, Polyline, haversine_m
from corridor.domain.units import meters_to_miles

DENVER = LatLon(39.7392, -104.9903)
CHICAGO = LatLon(41.8781, -87.6298)


def test_haversine_known_distance() -> None:
    assert meters_to_miles(haversine_m(DENVER, CHICAGO)) == pytest.approx(920, rel=0.01)


def test_haversine_zero() -> None:
    assert haversine_m(DENVER, DENVER) == 0


def test_rejects_invalid_coordinates() -> None:
    with pytest.raises(ValueError, match="out of range"):
        LatLon(91, 0)


def test_polyline_cumulative_and_interpolation() -> None:
    line = Polyline([LatLon(0, 0), LatLon(0, 1), LatLon(0, 2)])
    half = line.total_m / 2

    assert line.cumulative_m[1] == pytest.approx(half)
    assert line.point_at(half / 2).lon == pytest.approx(0.5)
    assert line.point_at(-10) == LatLon(0, 0)
    assert line.point_at(line.total_m * 2) == LatLon(0, 2)


def test_polyline_handles_duplicate_points() -> None:
    line = Polyline([LatLon(0, 0), LatLon(0, 0), LatLon(0, 1)])
    assert line.point_at(0) == LatLon(0, 0)
    assert line.point_at(line.total_m).lon == pytest.approx(1)


def test_polyline_requires_two_points() -> None:
    with pytest.raises(ValueError, match="two points"):
        Polyline([DENVER])
