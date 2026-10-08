import math

import pygame
import pytest

from fishing.input.keyboard_mouse import KeyboardMouseSource

CENTRE = (640, 360)


class Keys:
    def __init__(self):
        self.down = set()

    def __call__(self, key):
        return key in self.down


@pytest.fixture
def keys():
    return Keys()


@pytest.fixture
def src(tuning, keys, clock):
    return KeyboardMouseSource(tuning.keyboard, CENTRE, is_down=keys, clock=clock)


def ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


def test_space_hold_sets_cast_strength(src, clock, tuning):
    src.handle_event(ev(pygame.KEYDOWN, key=pygame.K_SPACE))
    clock.advance(tuning.keyboard.cast_charge_s * 1000 / 2)
    assert src.charging
    src.handle_event(ev(pygame.KEYUP, key=pygame.K_SPACE))
    (cast,) = src.drain_events()
    assert cast.kind == "cast"
    assert cast.strength == pytest.approx(0.5)
    assert cast.t_ms == clock.t
    assert not src.charging


def test_long_hold_caps_at_full_strength(src, clock):
    src.handle_event(ev(pygame.KEYDOWN, key=pygame.K_SPACE))
    clock.advance(10_000)
    src.handle_event(ev(pygame.KEYUP, key=pygame.K_SPACE))
    assert src.drain_events()[0].strength == 1.0


@pytest.mark.parametrize(
    "event",
    [
        ev(pygame.KEYDOWN, key=pygame.K_j),
        ev(pygame.KEYDOWN, key=pygame.K_UP),
        ev(pygame.MOUSEBUTTONDOWN, button=1, pos=CENTRE),
    ],
)
def test_hook_set_inputs(src, event):
    src.handle_event(event)
    (hook,) = src.drain_events()
    assert hook.kind == "hook_set"


def test_two_gestures_in_one_frame_are_both_kept(src, clock):
    src.handle_event(ev(pygame.KEYDOWN, key=pygame.K_j))
    clock.advance(5)
    src.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=CENTRE))
    assert [e.kind for e in src.drain_events()] == ["hook_set", "hook_set"]


def test_tilt_ramps_and_returns(src, keys, clock, tuning):
    keys.down.add(pygame.K_d)
    clock.advance(50)
    first = src.poll().tilt
    assert 0 < first < 1
    for _ in range(20):
        clock.advance(50)
        last = src.poll().tilt
    assert last == 1.0
    keys.down.clear()
    for _ in range(20):
        clock.advance(50)
        last = src.poll().tilt
    assert last == 0.0


def test_reel_keys(src, keys, tuning):
    keys.down.add(pygame.K_s)
    assert src.poll().reel_rate == tuning.keyboard.slow_reel
    keys.down.add(pygame.K_w)
    assert src.poll().reel_rate == tuning.keyboard.fast_reel


def test_mouse_circles_reel(src, clock, tuning):
    kb = tuning.keyboard
    turns_per_s = kb.mouse_full_turns_per_s / 2  # half speed -> reel ~0.5
    r = 150
    for i in range(12):
        a = 2 * math.pi * turns_per_s * (i * 10 / 1000.0)
        src.handle_event(
            ev(pygame.MOUSEMOTION, pos=(CENTRE[0] + r * math.cos(a), CENTRE[1] + r * math.sin(a)))
        )
        clock.advance(10)
    assert src.poll().reel_rate == pytest.approx(0.5, abs=0.15)


def test_mouse_reel_stops_when_mouse_stops(src, clock):
    for i in range(10):
        a = i * 0.3
        src.handle_event(ev(pygame.MOUSEMOTION, pos=(CENTRE[0] + 150 * math.cos(a), CENTRE[1] + 150 * math.sin(a))))
        clock.advance(10)
    clock.advance(500)
    assert src.poll().reel_rate == 0.0


def test_send_records_and_calls_hook(src):
    heard = []
    src.on_send = heard.append
    src.send("BITE")
    assert src.sent == ["BITE"] and heard == ["BITE"]
