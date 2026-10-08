import os

# Headless: no window, no sound device. Must be set before pygame is imported.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pytest  # noqa: E402

from fishing.config import load_tuning  # noqa: E402


@pytest.fixture(scope="session")
def tuning():
    return load_tuning()


class FakeClock:
    """A controllable now_ms() for sources and sims."""

    def __init__(self, t_ms: float = 0.0) -> None:
        self.t = t_ms

    def __call__(self) -> float:
        return self.t

    def advance(self, ms: float) -> None:
        self.t += ms


@pytest.fixture
def clock():
    return FakeClock(1000.0)
