import math

import pytest

from corridor.domain.advisories import AdvisoryKind, advisories, crosswind_mph
from corridor.domain.geometry import LatLon, bearing_deg
from corridor.domain.weather import WeatherSample


def sample(**changes: float) -> WeatherSample:
    values = {
        "wind_mph": 10.0,
        "gust_mph": 15.0,
        "rain_in_hr": 0.0,
        "snow_in_hr": 0.0,
        "temperature_f": 50.0,
        "weather_code": 0,
        "wind_direction_deg": math.nan,
        "visibility_mi": math.nan,
    } | changes
    return WeatherSample(**values)  # type: ignore[arg-type]


def kinds(s: WeatherSample, heading: float = 90.0) -> list[AdvisoryKind]:
    return [a.kind for a in advisories(s, heading)]


@pytest.mark.parametrize(
    ("wind_from", "heading", "expected"),
    [(0, 90, 40.0), (90, 90, 0.0), (270, 90, 0.0), (45, 90, 40 * math.sqrt(0.5))],
)
def test_crosswind_component(wind_from: float, heading: float, expected: float) -> None:
    assert crosswind_mph(40, wind_from, heading) == pytest.approx(expected, abs=1e-9)


def test_broadside_gusts_warn_but_head_on_gusts_do_not() -> None:
    gusty = {"gust_mph": 34.0}
    assert kinds(sample(**gusty, wind_direction_deg=0)) == [AdvisoryKind.CROSSWIND]
    assert kinds(sample(**gusty, wind_direction_deg=90)) == []
    assert kinds(sample(**gusty)) == []  # direction unknown


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"weather_code": 66}, [AdvisoryKind.ICE]),
        ({"rain_in_hr": 0.05, "temperature_f": 33.0}, [AdvisoryKind.ICE]),
        ({"rain_in_hr": 0.05, "temperature_f": 38.0}, []),
        ({"visibility_mi": 0.1}, [AdvisoryKind.VISIBILITY]),
        ({"visibility_mi": 3.0}, []),
    ],
)
def test_ice_and_visibility(changes: dict[str, float], expected: list[AdvisoryKind]) -> None:
    assert kinds(sample(**changes)) == expected


def test_dense_fog_wording() -> None:
    [advisory] = advisories(sample(visibility_mi=0.12), 0)
    assert advisory.message == "Dense fog: visibility 0.12 mi."


def test_bearing() -> None:
    assert bearing_deg(LatLon(40, -100), LatLon(41, -100)) == pytest.approx(0, abs=1e-6)
    assert bearing_deg(LatLon(40, -100), LatLon(40, -99)) == pytest.approx(90, abs=0.5)
