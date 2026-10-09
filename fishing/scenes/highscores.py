"""The top-10 table."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from fishing.input.motion import HOOK_SET, MotionEvent, MotionState
from fishing.render import hud, palette
from fishing.scenes.base import Scene

if TYPE_CHECKING:
    from fishing.app import App


class HighScoresScene(Scene):
    def __init__(self, app: "App", highlight: int | None = None) -> None:
        super().__init__(app)
        self.highlight = highlight
        self._next: Scene | None = None

    def _back(self) -> None:
        from fishing.scenes.title import TitleScene

        self.app.audio.play("menu_back")
        self._next = TitleScene(self.app)

    def on_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self._back()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._back()

    def update(self, frame_s: float, st: MotionState, events: list[MotionEvent], stale: bool) -> Scene | None:
        if self.app.source_name == "rod" and any(e.kind == HOOK_SET for e in events):
            self._back()
        return self._next

    def draw(self, screen: pygame.Surface) -> None:
        app = self.app
        w, h = screen.get_size()
        screen.fill(palette.BG_MENU)
        hud.text(screen, app.fonts.get(palette.TITLE_FONT_SIZE), "High Scores", (w // 2, 30), palette.TEXT, "midtop")
        table = pygame.Rect(w // 2 - 520, 130, 1040, 500)
        hud.panel(screen, table)
        font = app.fonts.get(palette.HUD_FONT_SIZE)
        small = app.fonts.get(palette.HUD_SMALL_FONT_SIZE)
        cols = [(40, "#"), (90, "Name"), (300, "Score"), (430, "Medal"), (560, "Best fish"), (800, "Input"),
                (900, "Date")]
        for x, title in cols:
            hud.text(screen, small, title, (table.left + x, table.top + 16), palette.TEXT_DIM)
        entries = app.highscores.entries
        if not entries:
            hud.text(screen, font, "No scores yet. Go catch something!", table.center, palette.TEXT_DIM, "center")
        for i, e in enumerate(entries):
            y = table.top + 56 + i * 42
            colour = palette.GOLD if self.highlight == i + 1 else palette.TEXT
            values = [str(i + 1), e.name, str(e.score), e.medal or "-", e.best_fish or "-", e.input, e.date]
            for (x, _), v in zip(cols, values):
                c = palette.MEDAL_COLOURS.get(v, colour) if v in palette.MEDAL_COLOURS else colour
                hud.text(screen, font, v, (table.left + x, y), c)
        hud.text(screen, small, "Esc / Enter / click to go back", (w // 2, h - 40), palette.TEXT_DIM, "midtop")
