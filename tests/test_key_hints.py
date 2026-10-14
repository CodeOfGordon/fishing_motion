"""Keyboard prompts: the right key for the right moment, and they draw headless."""
from types import SimpleNamespace

import pygame
import pytest

from fishing.render import key_hints as K
from fishing.render.hud import ViewInfo
from fishing.sim import round as R
from fishing.ui.widgets import Fonts


def rnd(state, **fight):
    f = SimpleNamespace(**{"running": False, "run_dir": 1, **fight}) if state == R.FIGHT else None
    return SimpleNamespace(state=state, fight=f, frozen=False)


def keys(r):
    return [(h.keys, h.live) for h in K.hints_for(r)]


def test_bite_prompts_every_hook_key():
    assert keys(rnd(R.BITE)) == [(("J", K.UP, K.CLICK), True)]


def test_nibble_says_wait():
    assert keys(rnd(R.NIBBLE)) == [(("W",), False)]


def test_resting_fish_means_reel():
    assert keys(rnd(R.FIGHT, running=False)) == [(("W",), True)]


@pytest.mark.parametrize("run_dir,against", [(1, "A"), (-1, "D")])
def test_running_fish_means_ease_off_and_steer_against(run_dir, against):
    assert keys(rnd(R.FIGHT, running=True, run_dir=run_dir)) == [
        (("W",), False), (("S",), True), ((against,), True)]


def test_nothing_in_other_states():
    assert K.hints_for(rnd(R.DRIFT)) == []


@pytest.fixture
def screen():
    pygame.init()
    yield pygame.display.set_mode((640, 360))
    pygame.quit()


def info(source="keyboard"):
    return ViewInfo(source_name=source, charging=None, practice=False, stale=False, connecting=False,
                    paused=False, host_now_ms=0.0)


def test_keyboard_row_draws_only_for_keyboard(screen):
    fonts = Fonts()
    blank = screen.copy()
    K.draw_key_hints(screen, fonts, rnd(R.BITE), info("other"))
    assert pygame.image.tobytes(screen, "RGB") == pygame.image.tobytes(blank, "RGB")
    K.draw_key_hints(screen, fonts, rnd(R.BITE), info())
    assert pygame.image.tobytes(screen, "RGB") != pygame.image.tobytes(blank, "RGB")


from fishing.render import motion_icons as M  # noqa: E402


def rod_keys(r):
    return [(h.keys, h.live) for h in K.hints_for(r, rod=True)]


def test_rod_prompts_the_gesture_for_each_moment():
    assert rod_keys(rnd(R.READY)) == [((M.FLICK,), True)]
    assert rod_keys(rnd(R.DRIFT)) == [((M.CIRCLE,), True), ((M.TILT,), True)]
    assert rod_keys(rnd(R.NIBBLE)) == [((M.CIRCLE,), False)]
    assert rod_keys(rnd(R.BITE)) == [((M.JERK,), True)]
    assert rod_keys(rnd(R.FIGHT, running=False)) == [((M.CIRCLE,), True)]


@pytest.mark.parametrize("run_dir,against", [(1, M.TILT_LEFT), (-1, M.TILT_RIGHT)])
def test_rod_running_fish_means_slow_circles_and_tilt_against(run_dir, against):
    assert rod_keys(rnd(R.FIGHT, running=True, run_dir=run_dir)) == [((M.CIRCLE_SLOW,), True), ((against,), True)]


@pytest.mark.parametrize("name", M.ICONS)
def test_every_icon_draws_at_every_phase(screen, name):
    for t in range(0, 2400, 100):
        screen.fill((0, 0, 0))
        M.draw_icon(screen, name, 20, 60, True, float(t))
        assert pygame.image.tobytes(screen, "RGB") != bytes(640 * 360 * 3)


def test_rod_row_draws_and_hides_when_disconnected(screen):
    fonts = Fonts()
    blank = screen.copy()
    K.draw_key_hints(screen, fonts, rnd(R.READY), info("rod"))
    assert pygame.image.tobytes(screen, "RGB") != pygame.image.tobytes(blank, "RGB")
    screen.blit(blank, (0, 0))
    gone = ViewInfo("rod", None, False, True, False, False, 0.0)  # stale
    K.draw_key_hints(screen, fonts, rnd(R.READY), gone)
    assert pygame.image.tobytes(screen, "RGB") == pygame.image.tobytes(blank, "RGB")
