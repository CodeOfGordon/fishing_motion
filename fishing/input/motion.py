"""The input boundary between the game and whatever is driving it.

Everything the game knows about the rod arrives through this module. The
keyboard/mouse source, the scripted test source and the rod's
``SerialMotionSource`` (``rod/serial_source.py``) all implement
``MotionSource``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

CAST = "cast"
HOOK_SET = "hook_set"
BITE_ACK = "bite_ack"
EVENT_KINDS = (CAST, HOOK_SET, BITE_ACK)


def now_ms() -> float:
    """The one clock shared by the game and every source, in milliseconds.

    Stamp samples and gestures with this (never the Arduino's ``millis()``),
    so the game can measure input age and judge hook-set timing.
    """
    return time.perf_counter() * 1000.0


@dataclass(frozen=True)
class MotionState:
    """The newest continuous reading."""

    t_ms: float  # now_ms() when the newest sample arrived
    reel_rate: float  # 0..1
    tilt: float  # -1 (left) .. 1 (right)
    connected: bool = True  # False before the first sample and after a dropout
    seq: int = 0  # increases by one per sample; used for rate and drop detection


@dataclass(frozen=True)
class MotionEvent:
    """A one-shot gesture (or an acknowledgement from the Nano)."""

    kind: str  # CAST | HOOK_SET | BITE_ACK
    t_ms: float  # now_ms() of the gesture's peak sample
    strength: float = 0.0  # cast: 0..1 distance; hook_set: jerk strength (logged)


@runtime_checkable
class MotionSource(Protocol):
    def poll(self) -> MotionState:
        """Return the newest continuous state. Never blocks, never returns None."""
        ...

    def drain_events(self) -> list[MotionEvent]:
        """Return every event since the previous call, oldest first, and forget them."""
        ...

    def send(self, msg: str) -> None:
        """Send a message to the device (e.g. "BITE"). Must not block."""
        ...

    def close(self) -> None:
        """Release the device. Safe to call more than once."""
        ...
