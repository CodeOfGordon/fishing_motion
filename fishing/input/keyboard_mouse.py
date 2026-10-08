"""Play without hardware: a MotionSource driven by the keyboard and mouse.

    Space (hold, release)   cast; hold time sets strength
    mouse circles           reel (analog), around the window centre
    W / S (hold)            reel fast / slow
    A D or left/right       tilt
    left click, J or up     hook-set
"""
from __future__ import annotations

import math
from collections import deque
from typing import Callable

import pygame

from fishing.config import KeyboardConfig
from fishing.input.motion import CAST, HOOK_SET, MotionEvent, MotionState, now_ms

LEFT_KEYS = (pygame.K_a, pygame.K_LEFT)
RIGHT_KEYS = (pygame.K_d, pygame.K_RIGHT)
HOOK_KEYS = (pygame.K_j, pygame.K_UP)
CAST_KEY = pygame.K_SPACE
FAST_REEL_KEY = pygame.K_w
SLOW_REEL_KEY = pygame.K_s

# Longest poll gap used for the tilt ramp, so a hitch can't snap tilt to full.
_MAX_RAMP_DT_S = 0.1


def _pygame_is_down(key: int) -> bool:
    return bool(pygame.key.get_pressed()[key])


class KeyboardMouseSource:
    def __init__(
        self,
        cfg: KeyboardConfig,
        centre: tuple[float, float],
        is_down: Callable[[int], bool] = _pygame_is_down,
        clock: Callable[[], float] = now_ms,
    ) -> None:
        self.cfg = cfg
        self.centre = centre
        self.is_down = is_down
        self.clock = clock
        self.on_send: Callable[[str], None] | None = None  # e.g. play a buzzer beep
        self.sent: list[str] = []
        self._events: list[MotionEvent] = []
        self._charge_start: float | None = None
        self._angles: deque[tuple[float, float]] = deque()  # (t_ms, angle)
        self._tilt = 0.0
        self._last_poll = clock()
        self._seq = 0

    # -- fed by the app's event loop -------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        t = self.clock()
        if e.type == pygame.KEYDOWN:
            if e.key == CAST_KEY and self._charge_start is None:
                self._charge_start = t
            elif e.key in HOOK_KEYS:
                self._events.append(MotionEvent(HOOK_SET, t, 1.0))
        elif e.type == pygame.KEYUP and e.key == CAST_KEY and self._charge_start is not None:
            self._events.append(MotionEvent(CAST, t, self.charge))
            self._charge_start = None
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._events.append(MotionEvent(HOOK_SET, t, 1.0))
        elif e.type == pygame.MOUSEMOTION:
            dx = e.pos[0] - self.centre[0]
            dy = e.pos[1] - self.centre[1]
            if math.hypot(dx, dy) >= self.cfg.mouse_min_radius:
                self._angles.append((t, math.atan2(dy, dx)))

    @property
    def charge(self) -> float:
        """Cast strength if Space were released now (0 when not charging)."""
        if self._charge_start is None:
            return 0.0
        held_s = (self.clock() - self._charge_start) / 1000.0
        return min(1.0, held_s / self.cfg.cast_charge_s)

    @property
    def charging(self) -> bool:
        return self._charge_start is not None

    # -- MotionSource ------------------------------------------------------
    def poll(self) -> MotionState:
        t = self.clock()
        dt_s = min(max(t - self._last_poll, 0.0) / 1000.0, _MAX_RAMP_DT_S)
        self._last_poll = t
        self._seq += 1
        return MotionState(t, self._reel_rate(t), self._step_tilt(dt_s), True, self._seq)

    def drain_events(self) -> list[MotionEvent]:
        events, self._events = self._events, []
        return events

    def send(self, msg: str) -> None:
        self.sent.append(msg)
        if self.on_send is not None:
            self.on_send(msg)

    def reset(self) -> None:
        """Forget pending gestures and any half-charged cast."""
        self._events.clear()
        self._angles.clear()
        self._charge_start = None

    def close(self) -> None:
        self.reset()

    # -- helpers -----------------------------------------------------------
    def _step_tilt(self, dt_s: float) -> float:
        target = float(any(self.is_down(k) for k in RIGHT_KEYS)) - float(
            any(self.is_down(k) for k in LEFT_KEYS)
        )
        step = self.cfg.tilt_ramp_per_s * dt_s
        if self._tilt < target:
            self._tilt = min(target, self._tilt + step)
        else:
            self._tilt = max(target, self._tilt - step)
        return self._tilt

    def _reel_rate(self, t: float) -> float:
        keys = 0.0
        if self.is_down(FAST_REEL_KEY):
            keys = self.cfg.fast_reel
        elif self.is_down(SLOW_REEL_KEY):
            keys = self.cfg.slow_reel
        return max(keys, self._mouse_reel(t))

    def _mouse_reel(self, t: float) -> float:
        window = self.cfg.mouse_window_ms
        while self._angles and t - self._angles[0][0] > window:
            self._angles.popleft()
        if len(self._angles) < 2:
            return 0.0
        turned = 0.0
        for (_, a0), (_, a1) in zip(self._angles, list(self._angles)[1:]):
            d = a1 - a0
            turned += (d + math.pi) % (2 * math.pi) - math.pi  # unwrap to (-pi, pi]
        turns_per_s = abs(turned) / (2 * math.pi) / (window / 1000.0)
        return min(1.0, turns_per_s / self.cfg.mouse_full_turns_per_s)
