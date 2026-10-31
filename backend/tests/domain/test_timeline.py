import pytest

from corridor.domain.timeline import TimeAnchor, TimeProfile


def test_interpolates_between_anchors() -> None:
    profile = TimeProfile([TimeAnchor(1000, 50)], total_m=2000, total_s=150)

    assert profile.elapsed_at(0) == 0
    assert profile.elapsed_at(500) == pytest.approx(25)
    assert profile.elapsed_at(1500) == pytest.approx(100)
    assert profile.elapsed_at(2000) == 150


def test_constant_speed() -> None:
    profile = TimeProfile.constant_speed(1000, 100)
    assert profile.elapsed_at(250) == pytest.approx(25)


def test_normalises_unsorted_out_of_range_and_backwards_anchors() -> None:
    anchors = [TimeAnchor(800, 40), TimeAnchor(400, 60), TimeAnchor(-5, 3), TimeAnchor(5000, 9)]
    profile = TimeProfile(anchors, total_m=1000, total_s=100)

    # 800 m reports 40 s, earlier than 400 m's 60 s: time is held at 60 s instead.
    assert profile.elapsed_at(400) == pytest.approx(60)
    assert profile.elapsed_at(800) == pytest.approx(60)
    assert profile.elapsed_at(1000) == 100


def test_clamps_lookups() -> None:
    profile = TimeProfile.constant_speed(1000, 100)
    assert profile.elapsed_at(-1) == 0
    assert profile.elapsed_at(10_000) == 100


def test_rejects_degenerate_route() -> None:
    with pytest.raises(ValueError, match="positive"):
        TimeProfile.constant_speed(0, 10)
