"""Scene interface. The app owns the window, the input source and the session log."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from fishing.input.motion import MotionEvent, MotionState

if TYPE_CHECKING:
    from fishing.app import App


class Scene:
    def __init__(self, app: "App") -> None:
        self.app = app

    def on_event(self, e: pygame.event.Event) -> None:
        pass

    def update(self, frame_s: float, st: MotionState, events: list[MotionEvent], stale: bool) -> "Scene | None":
        """Advance one frame; return the next scene to switch to, or None to stay."""
        return None

    def draw(self, screen: pygame.Surface) -> None:
        pass

    def overlay_lines(self) -> list[str]:
        return []

    def on_exit(self) -> None:
        pass
