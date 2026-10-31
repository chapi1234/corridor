from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from corridor.domain.geometry import LatLon, Polyline
from corridor.domain.sampling import owned_lengths, place_checkpoints, sample_distances
from corridor.domain.timeline import TimeProfile
from corridor.domain.units import miles_to_meters


def test_sample_distances_includes_destination() -> None:
    assert sample_distances(25, 10) == [0, 10, 20, 25]


def test_sample_distances_exact_multiple_has_no_sliver() -> None:
    assert sample_distances(30, 10) == [0, 10, 20, 30]


def test_short_route_has_origin_and_destination() -> None:
    assert sample_distances(4, 10) == [0, 4]


def test_owned_lengths_split_at_midpoints() -> None:
    assert owned_lengths([0, 10, 20, 25]) == [5, 10, 7.5, 2.5]


@given(
    total=st.floats(min_value=1, max_value=5_000_000),
    interval=st.sampled_from([miles_to_meters(10), miles_to_meters(25), miles_to_meters(50)]),
)
def test_owned_lengths_cover_route_exactly(total: float, interval: float) -> None:
    distances = sample_distances(total, interval)
    assert sum(owned_lengths(distances)) == pytest.approx(total)
    assert all(b > a for a, b in pairwise(distances))


def test_place_checkpoints_uses_time_profile() -> None:
    line = Polyline([LatLon(0, 0), LatLon(0, 1)])
    profile = TimeProfile.constant_speed(line.total_m, 3600)

    checkpoints = place_checkpoints(line, profile, interval_m=line.total_m / 4)

    assert [c.index for c in checkpoints] == [0, 1, 2, 3, 4]
    assert checkpoints[2].elapsed_s == pytest.approx(1800)
    assert checkpoints[2].point.lon == pytest.approx(0.5)
    assert checkpoints[-1].distance_m == line.total_m


@pytest.mark.parametrize(("total", "interval"), [(0, 10), (10, 0)])
def test_sample_distances_validates(total: float, interval: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        sample_distances(total, interval)
