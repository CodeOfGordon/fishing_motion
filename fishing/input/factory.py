"""Pick the input source from settings, falling back to keyboard if the rod isn't ready."""
from __future__ import annotations

from fishing.config import Tuning
from fishing.input.keyboard_mouse import KeyboardMouseSource
from fishing.input.motion import MotionSource
from fishing.settings import Settings

KEYBOARD = "keyboard"
ROD = "rod"


def make_keyboard(tuning: Tuning) -> KeyboardMouseSource:
    w, h = tuning.window.width, tuning.window.height
    return KeyboardMouseSource(tuning.keyboard, centre=(w / 2, h / 2))


def make_source(settings: Settings, tuning: Tuning) -> tuple[MotionSource, str, str | None]:
    """Return (source, name, error). On any rod problem: keyboard plus the error text."""
    if settings.input_source == ROD:
        try:
            from rod.serial_source import SerialMotionSource  # lazy: pyserial may be absent

            return SerialMotionSource(settings.serial_port, settings.baud), ROD, None
        except Exception as err:  # the stub's NotImplementedError, ImportError, SerialException...
            reason = str(err) or type(err).__name__
            return make_keyboard(tuning), KEYBOARD, f"Rod source not available: {reason}"
    return make_keyboard(tuning), KEYBOARD, None
