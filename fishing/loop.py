"""Fixed-timestep accumulator and exactly-once event delivery (no pygame)."""
from __future__ import annotations

from typing import Callable, TypeVar

E = TypeVar("E")


class FixedStep:
    """Turns irregular frame times into a whole number of fixed sim steps."""

    def __init__(self, step_s: float, max_frame_s: float, max_steps: int) -> None:
        self.step_s = step_s
        self.max_frame_s = max_frame_s
        self.max_steps = max_steps
        self.acc = 0.0

    def advance(self, frame_s: float) -> int:
        """Add one frame's elapsed time and return how many steps to run now."""
        self.acc += min(max(frame_s, 0.0), self.max_frame_s)
        steps = 0
        while self.acc >= self.step_s and steps < self.max_steps:
            self.acc -= self.step_s
            steps += 1
        if self.acc >= self.step_s:
            # Too far behind (a hitch): drop the backlog rather than fast-forward.
            self.acc = 0.0
        return steps

    @property
    def alpha(self) -> float:
        """Fraction of a step left in the accumulator (for render interpolation)."""
        return self.acc / self.step_s


def deliver(steps: int, inbox: list[E], step_fn: Callable[[list[E]], None]) -> list[E]:
    """Run ``step_fn`` ``steps`` times, handing the inbox to the first step only.

    Returns what must carry over to the next frame: the untouched inbox when no
    step ran, otherwise an empty list. Every event is delivered exactly once.
    """
    if steps <= 0:
        return inbox
    for i in range(steps):
        step_fn(inbox if i == 0 else [])
    return []
