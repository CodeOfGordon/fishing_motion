"""Settings: input source and serial port, shaping, gameplay and audio. Saved on exit."""
from __future__ import annotations

import glob
from typing import TYPE_CHECKING

import pygame

from fishing.input.motion import MotionEvent, MotionState
from fishing.render import hud, palette
from fishing.scenes.base import Scene
from fishing.ui.widgets import ActionRow, ChoiceRow, Menu, SliderRow, TextRow, ToggleRow

if TYPE_CHECKING:
    from fishing.app import App

PORT_GLOB = "/dev/cu.usbmodem*"
ROWS_VISIBLE = 11


class SettingsScene(Scene):
    def __init__(self, app: "App") -> None:
        super().__init__(app)
        self._next: Scene | None = None
        app.music("menu")
        self.status = ""
        s = app.settings
        diffs = list(app.tuning.difficulty)

        def setter(name):
            def set_(v):
                setattr(s, name, v)
                if name in ("master_volume", "music_volume"):
                    app.apply_volumes()
            return set_

        def getter(name):
            return lambda: getattr(s, name)

        self.menu = Menu(
            [
                ChoiceRow("Input", [("Keyboard & mouse", "keyboard"), ("Rod (serial)", "rod")],
                          getter("input_source"), setter("input_source")),
                TextRow("Serial port", getter("serial_port"), setter("serial_port"),
                        placeholder="/dev/cu.usbmodem..."),
                ActionRow("Scan for ports", self._scan),
                ChoiceRow("Baud", [(str(b), b) for b in (9600, 57600, 115200, 230400, 250000)],
                          getter("baud"), setter("baud")),
                ActionRow("Connect / apply input", self._apply_input),
                SliderRow("Tilt sensitivity", getter("tilt_sensitivity"), setter("tilt_sensitivity"), 0.5, 2.0, 0.1),
                SliderRow("Tilt dead zone", getter("tilt_deadzone"), setter("tilt_deadzone"), 0.0, 0.3, 0.02),
                SliderRow("Tilt smoothing (ms)", getter("tilt_smoothing_ms"), setter("tilt_smoothing_ms"),
                          0, 500, 25, "{:.0f}"),
                ToggleRow("Invert tilt", getter("tilt_invert"), setter("tilt_invert")),
                ActionRow("Recentre tilt (hold the rod level)", self._recentre),
                SliderRow("Reel sensitivity", getter("reel_sensitivity"), setter("reel_sensitivity"), 0.5, 2.0, 0.1),
                SliderRow("Reel dead zone", getter("reel_deadzone"), setter("reel_deadzone"), 0.0, 0.3, 0.02),
                ToggleRow("Forgiving hook-set", getter("forgiving_hook"), setter("forgiving_hook")),
                ChoiceRow("Difficulty", [(d.title(), d) for d in diffs], getter("difficulty"), setter("difficulty")),
                SliderRow("Master volume", getter("master_volume"), setter("master_volume"), 0.0, 1.0, 0.1),
                SliderRow("Music volume", getter("music_volume"), setter("music_volume"), 0.0, 1.0, 0.1),
                SliderRow("SFX volume", getter("sfx_volume"), setter("sfx_volume"), 0.0, 1.0, 0.1),
                ToggleRow("Game bite sound", getter("game_bite_sound"), setter("game_bite_sound")),
                ToggleRow("Simulated buzzer (keyboard)", getter("simulate_buzzer"), setter("simulate_buzzer")),
                ToggleRow("Show debug overlay", getter("show_fps"), setter("show_fps")),
                ActionRow("Back", self._back),
            ],
            on_move=lambda: app.audio.play("menu_move"), on_select=lambda: app.audio.play("menu_ok"),
        )

    def _scan(self) -> None:
        ports = sorted(glob.glob(PORT_GLOB))
        if not ports:
            self.status = f"No {PORT_GLOB} found. Is the Uno plugged in?"
            return
        current = self.app.settings.serial_port
        nxt = ports[(ports.index(current) + 1) % len(ports)] if current in ports else ports[0]
        self.app.settings.serial_port = nxt
        self.status = f"Found {len(ports)} port(s): using {nxt}"

    def _apply_input(self) -> None:
        self.app.switch_source()
        self.status = self.app.source_error or f"Input: {self.app.source_name}"

    def _recentre(self) -> None:
        raw = self.app.shaper.raw
        if raw is None:
            self.status = "No input yet"
            return
        self.app.settings.tilt_offset = raw.tilt
        self.status = f"Tilt centre set to {raw.tilt:+.2f}"

    def _back(self) -> None:
        from fishing.scenes.title import TitleScene

        self.app.save_settings()
        if (self.app.settings.input_source != self.app.source_name) and not self.app.source_error:
            self.app.switch_source()
        self._next = TitleScene(self.app)

    def on_event(self, e: pygame.event.Event) -> None:
        if self.menu.handle_event(e):
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self._back()

    def update(self, frame_s: float, st: MotionState, events: list[MotionEvent], stale: bool) -> Scene | None:
        self.menu.handle_motion(frame_s, st, events, self.app.source_name == "rod")
        self.live = st
        return self._next

    def draw(self, screen: pygame.Surface) -> None:
        app = self.app
        w, h = screen.get_size()
        screen.fill(palette.BG_MENU)
        hud.text(screen, app.fonts.get(palette.TITLE_FONT_SIZE), "Settings", (w // 2, 16), palette.TEXT, "midtop")
        self.menu.draw(screen, app.fonts, w // 2 - 120, 110, size=palette.HUD_FONT_SIZE, spacing=42,
                       max_rows=ROWS_VISIBLE)

        live = getattr(self, "live", None)
        panel = pygame.Rect(w - 330, 110, 300, 210)
        hud.panel(screen, panel)
        small = app.fonts.get(palette.HUD_SMALL_FONT_SIZE)
        hud.text(screen, small, "Live input", (panel.left + 16, panel.top + 12), palette.TEXT_DIM)
        hud.text(screen, small, f"source: {app.source_name}", (panel.left + 16, panel.top + 42))
        if live is not None:
            hud.text(screen, small, f"reel  {live.reel_rate:4.2f}", (panel.left + 16, panel.top + 72))
            bar = pygame.Rect(panel.left + 120, panel.top + 76, 160, 12)
            pygame.draw.rect(screen, palette.TEXT_SHADOW, bar)
            pygame.draw.rect(screen, palette.GOOD, (bar.left, bar.top, round(bar.width * live.reel_rate), bar.height))
            hud.text(screen, small, f"tilt {live.tilt:+5.2f}", (panel.left + 16, panel.top + 102))
            mid = panel.left + 200
            pygame.draw.line(screen, palette.TEXT_DIM, (panel.left + 120, panel.top + 112), (panel.right - 20, panel.top + 112), 2)
            pygame.draw.circle(screen, palette.WARN, (round(mid + live.tilt * 80), panel.top + 112), 7)
            hud.text(screen, small, "connected" if live.connected else "NOT connected",
                     (panel.left + 16, panel.top + 140), palette.GOOD if live.connected else palette.BAD)
        if self.status:
            hud.text(screen, small, self.status, (w // 2, h - 46), palette.WARN, "midtop")
        hud.text(screen, small, "Up/Down choose   Left/Right change   Enter edit/confirm   Esc save & back",
                 (w // 2, h - 22), palette.TEXT_DIM, "midtop")
