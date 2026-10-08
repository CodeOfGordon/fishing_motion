import pytest

from fishing.input.motion import MotionState
from fishing.input.shaping import InputShaper, dead_zone
from fishing.settings import Settings


def st(t, reel=0.0, tilt=0.0, connected=True):
    return MotionState(t, reel, tilt, connected)


@pytest.mark.parametrize("x,dz,expected", [(0.05, 0.1, 0.0), (1.0, 0.1, 1.0), (-1.0, 0.1, -1.0),
                                           (0.55, 0.1, 0.5), (0.3, 0.0, 0.3)])
def test_dead_zone_rescales(x, dz, expected):
    assert dead_zone(x, dz) == pytest.approx(expected)


def test_reel_is_never_smoothed():
    sh = InputShaper(Settings(reel_deadzone=0.0), stale_ms=150)
    sh.shape(st(0, reel=0.0), 0)
    assert sh.shape(st(16, reel=0.9), 16).reel_rate == pytest.approx(0.9)
    assert sh.shape(st(32, reel=0.0), 32).reel_rate == 0.0


def test_tilt_is_smoothed_with_the_set_time_constant():
    sh = InputShaper(Settings(tilt_deadzone=0.0, tilt_smoothing_ms=250), stale_ms=150)
    sh.shape(st(0, tilt=0.0), 0)
    out = sh.shape(st(250, tilt=1.0), 250)
    assert out.tilt == pytest.approx(1 - 2.718281828 ** -1, abs=0.01)


def test_tilt_smoothing_off_passes_through():
    sh = InputShaper(Settings(tilt_deadzone=0.0, tilt_smoothing_ms=0), stale_ms=150)
    sh.shape(st(0, tilt=0.0), 0)
    assert sh.shape(st(16, tilt=0.7), 16).tilt == pytest.approx(0.7)


def test_offset_invert_and_sensitivity():
    s = Settings(tilt_deadzone=0.0, tilt_smoothing_ms=0, tilt_offset=0.2, tilt_invert=True, tilt_sensitivity=2.0)
    sh = InputShaper(s, stale_ms=150)
    assert sh.shape(st(0, tilt=0.4), 0).tilt == pytest.approx(-0.4)
    assert sh.shape(st(1, tilt=1.0), 1).tilt == -1.0  # clamped


def test_reel_sensitivity_and_clamp():
    sh = InputShaper(Settings(reel_deadzone=0.0, reel_sensitivity=2.0), stale_ms=150)
    assert sh.shape(st(0, reel=0.3), 0).reel_rate == pytest.approx(0.6)
    assert sh.shape(st(1, reel=0.8), 1).reel_rate == 1.0


def test_staleness():
    sh = InputShaper(Settings(), stale_ms=150)
    assert not sh.is_stale(st(1000), 1100)
    assert sh.is_stale(st(1000), 1200)
    assert sh.is_stale(st(1000, connected=False), 1000)
