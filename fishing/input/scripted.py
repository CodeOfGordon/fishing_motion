"""A MotionSource that replays a script, for tests and headless runs."""
from __future__ import annotations

from typing import Callable, Iterable, NamedTuple

from fishing.input.motion import MotionEvent, MotionState, now_ms


class Keyframe(NamedTuple):
    t_ms: float
    reel_rate: float
    tilt: float
    connected: bool = True


class ScriptedSource:
    """Plays back keyframes (held until the next one) and timed events.

    ``clock`` defaults to the real host clock; tests pass a fake one.
    """

    def __init__(
        self,
        keyframes: Iterable[Keyframe] = (),
        events: Iterable[MotionEvent] = (),
        clock: Callable[[], float] = now_ms,
    ) -> None:
        self.keyframes = sorted(keyframes, key=lambda k: k.t_ms)
        self._pending = sorted(events, key=lambda e: e.t_ms)
        self.clock = clock
        self.sent: list[str] = []
        self.closed = False
        self._seq = 0

    def poll(self) -> MotionState:
        t = self.clock()
        current = Keyframe(t, 0.0, 0.0, True)
        for k in self.keyframes:
            if k.t_ms > t:
                break
            current = k
        self._seq += 1
        return MotionState(t, current.reel_rate, current.tilt, current.connected, self._seq)

    def drain_events(self) -> list[MotionEvent]:
        t = self.clock()
        due = [e for e in self._pending if e.t_ms <= t]
        self._pending = self._pending[len(due):]
        return due

    def send(self, msg: str) -> None:
        self.sent.append(msg)

    def close(self) -> None:
        self.closed = True
