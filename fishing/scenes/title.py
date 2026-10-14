"""Title screen: the pond animates behind the menu."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from fishing.input.motion import MotionEvent, MotionState, now_ms
from fishing.render import hud, motion_icons, palette
from fishing.render.hud import ViewInfo
from fishing.scenes.base import Scene
from fishing.sim import round as R
from fishing.ui.widgets import ActionRow, Menu

if TYPE_CHECKING:
    from fishing.app import App


class TitleScene(Scene):
    def __init__(self, app: "App") -> None:
        super().__init__(app)
        self._next: Scene | None = None
        self.demo = R.Round(app.tuning, practice=True, seed=12345)
        self.view = app.make_view()
        self.idle = MotionState(now_ms(), 0.0, 0.0)
        self.menu = Menu(
            [
                ActionRow("Play", self._play),
                ActionRow("Practice", self._practice),
                ActionRow("Rod Test", self._rod_test),
                ActionRow("Settings", self._settings),
                ActionRow("High Scores", self._scores),
                ActionRow("Quit", self._quit),
            ],
            on_move=lambda: app.audio.play("menu_move"), on_select=lambda: app.audio.play("menu_ok"),
        )
        app.overlay.visible = app.settings.show_fps
        app.log.end_round()
        app.music("menu")

    def _play(self) -> None:
        from fishing.scenes.play import PlayScene

        self._next = PlayScene(self.app, practice=False)

    def _practice(self) -> None:
        from fishing.scenes.play import PlayScene

        self._next = PlayScene(self.app, practice=True)

    def _rod_test(self) -> None:
        from fishing.scenes.rod_test import RodTestScene

        self._next = RodTestScene(self.app)

    def _settings(self) -> None:
        from fishing.scenes.settings_menu import SettingsScene

        self._next = SettingsScene(self.app)

    def _scores(self) -> None:
        from fishing.scenes.highscores import HighScoresScene

        self._next = HighScoresScene(self.app)

    def _quit(self) -> None:
        self.app.running = False

    def on_event(self, e: pygame.event.Event) -> None:
        if not self.menu.handle_event(e) and e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self._quit()

    def update(self, frame_s: float, st: MotionState, events: list[MotionEvent], stale: bool) -> Scene | None:
        self.menu.handle_motion(frame_s, st, events, self.app.source_name == "rod" and not stale)
        host = now_ms()
        self.idle = MotionState(host, 0.0, 0.0)
        self.demo.step(min(frame_s, self.app.tuning.loop.demo_max_dt_s), self.idle, [], host)
        self.view.update(frame_s, self.idle)
        return self._next

    def draw(self, screen: pygame.Surface) -> None:
        app = self.app
        w, h = screen.get_size()
        info = ViewInfo(app.source_name, None, True, False, False, False, now_ms(), attract=True)
        self.view.draw(screen, self.demo, self.idle, info)
        hud.text(screen, app.fonts.get(palette.TITLE_FONT_SIZE), "Rod Fishing", (w // 2, palette.TITLE_Y),
                 palette.TEXT, "midtop")
        src = "rod" if app.source_name == "rod" else "keyboard & mouse"
        small = app.fonts.get(palette.HUD_SMALL_FONT_SIZE)
        info_y = palette.TITLE_Y + palette.TITLE_FONT_SIZE * 3 // 4 + 8
        hud.text(screen, small, f"input: {src}", (w // 2, info_y), palette.TEXT, "midtop")
        if app.source_error:
            hud.text(screen, small, app.source_error, (w // 2, info_y + 26), palette.WARN, "midtop")
        menu_top = info_y + 64
        hud.panel(screen, pygame.Rect(w // 2 - 200, menu_top, 400, 300))
        self.menu.draw(screen, app.fonts, w // 2, menu_top + 16)
        if app.source_name == "rod":
            x = w // 2 + 200 + palette.TITLE_HOLD_GAP
            motion_icons.draw_icon(screen, motion_icons.HOLD, x, menu_top + palette.MOTION_ICON_SIZE // 2, True, now_ms())
            text_y = menu_top + palette.MOTION_ICON_SIZE + 8
            hud.text(screen, small, "Hold the rod upright,", (x, text_y), palette.TEXT)
            hud.text(screen, small, "leaning toward the screen", (x, text_y + 22), palette.TEXT)
            reel_y = text_y + 56
            motion_icons.draw_icon(screen, motion_icons.CIRCLE, x, reel_y + palette.MOTION_ICON_SIZE // 2, True, now_ms())
            hud.text(screen, small, "To reel: keep it upright and", (x, reel_y + palette.MOTION_ICON_SIZE + 8), palette.TEXT)
            hud.text(screen, small, "draw circles with the tip", (x, reel_y + palette.MOTION_ICON_SIZE + 30), palette.TEXT)
