"""Game-side input shaping, applied to every source: dead zones, sensitivity, tilt smoothing."""
from __future__ import annotations

import math
from dataclasses import replace

from fishing.input.motion import MotionState
from fishing.settings import Settings


def dead_zone(x: float, dz: float) -> float:
    """Zero inside the dead zone, rescaled so the output still reaches +-1."""
    if dz <= 0:
        return x
    if dz >= 1:
        return 0.0
    mag = max(0.0, (abs(x) - dz) / (1.0 - dz))
    return math.copysign(mag, x)


class InputShaper:
    """Shapes raw MotionStates. Reel is never smoothed (no visible reel lag)."""

    def __init__(self, settings: Settings, stale_ms: float) -> None:
        self.settings = settings
        self.stale_ms = stale_ms
        self._tilt: float | None = None
        self._last_t: float | None = None
        self.raw: MotionState | None = None

    def reset(self) -> None:
        self._tilt = None
        self._last_t = None

    def shape(self, st: MotionState, now_ms: float) -> MotionState:
        self.raw = st
        s = self.settings
        tilt = st.tilt - s.tilt_offset
        if s.tilt_invert:
            tilt = -tilt
        tilt = max(-1.0, min(1.0, dead_zone(tilt, s.tilt_deadzone) * s.tilt_sensitivity))
        if self._tilt is None or s.tilt_smoothing_ms <= 0:
            self._tilt = tilt
        else:
            dt = max(0.0, now_ms - (self._last_t if self._last_t is not None else now_ms))
            alpha = 1.0 - math.exp(-dt / s.tilt_smoothing_ms)
            self._tilt += (tilt - self._tilt) * alpha
        self._last_t = now_ms
        reel = max(0.0, min(1.0, dead_zone(st.reel_rate, s.reel_deadzone) * s.reel_sensitivity))
        return replace(st, reel_rate=reel, tilt=self._tilt)

    def is_stale(self, st: MotionState, now_ms: float) -> bool:
        return not st.connected or now_ms - st.t_ms > self.stale_ms
