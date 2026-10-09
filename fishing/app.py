"""The app: window, input source, fixed-timestep loop, scenes, logging and audio."""
from __future__ import annotations

import argparse
import time
from dataclasses import asdict
from pathlib import Path

import pygame

from fishing.audio.bank import SoundBank
from fishing.config import load_tuning
from fishing.highscores import HighScores
from fishing.input.factory import KEYBOARD, ROD, make_source
from fishing.input.motion import MotionEvent, MotionSource, MotionState, now_ms
from fishing.input.shaping import InputShaper
from fishing.render.debug_overlay import DebugOverlay, RateMeter
from fishing.scenes.base import Scene
from fishing.session_log import LOG_DIR, SessionLog
from fishing.settings import DATA_DIR, load_settings, save_settings
from fishing.sim import events as ev
from fishing.sim.events import GameEvent
from fishing.ui.widgets import Fonts, configure_nav

MIXER_ARGS = (44100, -16, 2, 512)  # rate, int16, stereo, ~11.6 ms buffer
MUSIC_DIR = Path(__file__).resolve().parent.parent / "assets" / "music"
MUSIC_EXTS = (".ogg", ".mp3")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m fishing", description="Rod Fishing")
    p.add_argument("--practice", action="store_true", help="start straight into Practice")
    p.add_argument("--source", choices=(KEYBOARD, ROD), default=None,
                   help="input source for this run (Settings keeps the saved choice)")
    p.add_argument("--seed", type=int, default=None, help="seed the round's random numbers")
    p.add_argument("--windowed", action="store_true", help="run in a window, not fullscreen")
    return p.parse_args(argv)


class App:
    def __init__(self, args: argparse.Namespace, data_dir: Path | None = None,
                 log_dir: Path | None = None) -> None:
        self.args = args
        self.data_dir = data_dir or DATA_DIR
        self.tuning = load_tuning()
        self.settings = load_settings(self.data_dir / "settings.json")
        self.source_override: str | None = args.source  # --source applies to this run only
        configure_nav(self.tuning.menu.tilt_nav, self.tuning.menu.tilt_nav_repeat_s)

        w, h = self.tuning.window.width, self.tuning.window.height
        flags = pygame.SCALED | (0 if args.windowed else pygame.FULLSCREEN)
        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption("Rod Fishing")

        self.fonts = Fonts()
        self.log = SessionLog(log_dir or LOG_DIR)
        self.audio = SoundBank(self.settings)
        self.highscores = HighScores(self.data_dir / "highscores.json")
        self.shaper = InputShaper(self.settings, self.tuning.input.stale_ms)
        self.overlay = DebugOverlay(visible=self.settings.show_fps or args.practice)
        self.rate = RateMeter()
        self.clock = pygame.Clock()
        self.running = True
        self.last_gesture: MotionEvent | None = None
        self.last_verdict = ""
        self.connecting = False
        self._music_track: str | None = None

        self.source: MotionSource
        self.source_name = KEYBOARD
        self.source_error: str | None = None
        self.source_key: tuple = ()
        self.log.note("session_start", now_ms(), detail={"settings": asdict(self.settings),
                                                         "seed": args.seed})
        self.switch_source()
        self.apply_volumes()

        if args.practice:
            from fishing.scenes.play import PlayScene

            self.scene: Scene = PlayScene(self, practice=True)
        else:
            from fishing.scenes.title import TitleScene

            self.scene = TitleScene(self)

    # ---------------------------------------------------------------- services
    def make_view(self):
        from fishing.render.plain import PlainView

        try:
            from fishing.render.art import ArtView
        except ImportError:
            return PlainView(self.tuning, self.fonts)
        return ArtView(self.tuning, self.fonts)

    def requested_source(self) -> tuple:
        """What the settings (or --source) currently ask for, to detect changes."""
        name = self.source_override or self.settings.input_source
        s = self.settings
        return (name, s.serial_port, s.baud) if name == ROD else (name,)

    def switch_source(self, name: str | None = None) -> None:
        """(Re)open the input source. ``name`` forces one for this session without saving it."""
        old = getattr(self, "source", None)
        if old is not None:
            try:
                old.close()
            except Exception as err:
                self.log.note("source_error", now_ms(), reason=f"close: {err}")
        want = name or self.source_override or self.settings.input_source
        self.source, self.source_name, self.source_error = make_source(self.settings, self.tuning, want)
        self.source_key = self.requested_source() if name is None else (want,)
        self.log.input = self.source_name
        self.connecting = self.source_name == ROD
        self.shaper.reset()
        if self.source_name == KEYBOARD:
            self.source.on_send = self._keyboard_buzzer  # type: ignore[attr-defined]
        if self.source_error:
            self.log.note("source_error", now_ms(), reason=self.source_error)
        self.log.note("source_change", now_ms(), detail={"source": self.source_name,
                                                          "port": self.settings.serial_port,
                                                          "baud": self.settings.baud})

    def _keyboard_buzzer(self, msg: str) -> None:
        if msg == "BITE" and self.settings.simulate_buzzer:
            self.audio.play("buzzer")

    def apply_volumes(self) -> None:
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.settings.master_volume * self.settings.music_volume)

    def music(self, track: str | None, duck: float = 1.0, loop: bool = True) -> None:
        """Play assets/music/<track>.ogg|mp3 (silently skipped if missing; None stops it)."""
        if not pygame.mixer.get_init():
            return
        base = self.settings.master_volume * self.settings.music_volume
        pygame.mixer.music.set_volume(base * duck)
        if track == self._music_track:
            return
        self._music_track = track
        path = next((MUSIC_DIR / f"{track}{ext}" for ext in MUSIC_EXTS
                     if track and (MUSIC_DIR / f"{track}{ext}").exists()), None)
        if path is None:
            pygame.mixer.music.stop()
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play(loops=-1 if loop else 0, fade_ms=600 if loop else 0)
        except pygame.error as err:
            self.log.note("music_error", now_ms(), reason=str(err))

    def note_game_event(self, e: GameEvent) -> None:
        if e.kind in (ev.CAST, ev.HOOK_ATTEMPT):
            self.last_verdict = "accepted" if e.accepted else f"{e.reason}" + (
                f" ({e.detail['why']})" if e.detail.get("why") else "")
            if e.kind == ev.HOOK_ATTEMPT and e.accepted:
                self.last_verdict = "hooked"

    # ---------------------------------------------------------------- loop
    def overlay_lines(self, raw: MotionState, st: MotionState, stale: bool) -> list[str]:
        age = now_ms() - raw.t_ms
        status = "connecting" if self.connecting else "STALE" if stale else "connected" if raw.connected else "NOT CONNECTED"
        lines = [
            f"fps {self.clock.get_fps():5.1f}   frame {self.clock.get_time():3d} ms",
            f"input {self.source_name}  {status}   rate {self.rate.hz:5.1f} Hz   age {age:6.1f} ms",
            f"reel_rate {raw.reel_rate:4.2f} -> {st.reel_rate:4.2f}   tilt {raw.tilt:+5.2f} -> {st.tilt:+5.2f}",
        ]
        g = self.last_gesture
        if g is None:
            lines.append("last gesture: none")
        else:
            lines.append(f"last gesture: {g.kind} {g.strength:.2f}  {now_ms() - g.t_ms:6.0f} ms ago  "
                         f"{self.last_verdict}")
        return lines + self.scene.overlay_lines()

    def _flush_input(self) -> None:
        """Gestures made in one scene never leak into the next (e.g. Space in a menu)."""
        self.source.drain_events()
        reset = getattr(self.source, "reset", None)
        if reset is not None:
            reset()

    def save_settings(self) -> None:
        save_settings(self.settings, self.data_dir / "settings.json")

    def run(self, max_frames: int | None = None) -> None:
        prev = time.perf_counter()
        frames = 0
        while self.running and (max_frames is None or frames < max_frames):
            frames += 1
            now = time.perf_counter()
            frame_s, prev = now - prev, now
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                    self.overlay.toggle()
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                else:
                    handler = getattr(self.source, "handle_event", None)
                    if handler is not None:
                        handler(e)
                    self.scene.on_event(e)

            try:
                raw = self.source.poll()  # read input once per frame
                events = self.source.drain_events()
            except Exception as err:  # a broken source must not kill the game
                self.log.note("source_error", now_ms(), reason=f"poll: {err}")
                self.switch_source(KEYBOARD)  # for this session only; settings are untouched
                self.source_error = f"Rod source stopped: {err}"
                raw, events = self.source.poll(), self.source.drain_events()
            host = now_ms()
            st = self.shaper.shape(raw, host)
            stale = self.shaper.is_stale(raw, host)
            if raw.connected:
                self.connecting = False
            self.rate.update(raw.seq, host)
            self.overlay.push(st.reel_rate, st.tilt)
            if events:
                self.last_gesture = events[-1]
                self.last_verdict = "..."

            nxt = self.scene.update(frame_s, st, events, stale)
            if nxt is not None:
                self.scene.on_exit()
                self.scene = nxt
                self._flush_input()

            self.scene.draw(self.screen)
            self.overlay.draw(self.screen, self.overlay_lines(raw, st, stale))
            pygame.display.flip()
            self.clock.tick(self.tuning.loop.fps_cap)

    def shutdown(self) -> None:
        self.scene.on_exit()
        try:
            self.source.close()
        finally:
            self.log.note("session_end", now_ms())
            self.log.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pygame.mixer.pre_init(*MIXER_ARGS)
    pygame.init()
    try:
        app = App(args)
        try:
            app.run()
        finally:
            app.shutdown()
    finally:
        pygame.quit()
    return 0
