"""A round of Play (3:00) or Practice (no clock, overlay on, debug keys)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pygame

from fishing.input.motion import MotionEvent, MotionState, now_ms
from fishing.loop import FixedStep, deliver, step_hosts
from fishing.audio.bank import FIGHT_MUSIC_DUCK
from fishing.render.hud import ViewInfo
from fishing.scenes.base import Scene
from fishing.sim import events as ev
from fishing.sim import round as R
from fishing.sim.events import GameEvent
from fishing.ui.widgets import ActionRow, Menu

if TYPE_CHECKING:
    from fishing.app import App

SOUNDS = {
    ev.LURE_LAND: "plop",
    ev.NIBBLE: "nibble",
    ev.HOOKED: "hook",
    ev.SPECIAL_APPEARED: "chime",
    ev.CLOCK_TICK: "tick",
    ev.TIME_UP: "gong",
}


class PlayScene(Scene):
    def __init__(self, app: "App", practice: bool = False, seed: int | None = None) -> None:
        super().__init__(app)
        t = app.tuning
        self.practice = practice
        self.round = R.Round(
            t, practice=practice, difficulty=app.settings.difficulty,
            forgiving_hook=app.settings.forgiving_hook,
            seed=seed if seed is not None else app.args.seed,
        )
        self.stepper = FixedStep(1.0 / t.loop.step_hz, t.loop.max_frame_s, t.loop.max_steps)
        self.inbox: list[MotionEvent] = []
        self.view = app.make_view()
        self.paused = False
        self.stale = False
        self.over_for = 0.0
        self.st = MotionState(now_ms(), 0.0, 0.0)
        self.pause_menu = Menu(
            [ActionRow("Resume", self._resume), ActionRow("Restart", self._restart),
             ActionRow("Quit to title", self._quit)],
            on_move=lambda: app.audio.play("menu_move"), on_select=lambda: app.audio.play("menu_ok"),
        )
        self._next: Scene | None = None
        self._ended = False
        self.mode = "practice" if practice else "play"
        self.round_id = app.log.begin_round(self.mode)
        if practice:
            app.overlay.visible = True
        app.shaper.reset()
        self.track = "practice" if practice else "play"
        app.music(self.track)

    # ---------------------------------------------------------------- input
    def on_event(self, e: pygame.event.Event) -> None:
        if self.paused:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self._resume()
            else:
                self.pause_menu.handle_event(e)
            return
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.paused = True
            self.app.audio.play("menu_back")
        elif self.practice and e.key == pygame.K_b:
            if self.stale or self.app.connecting:  # never buzz a disconnected rod
                self.app.log.note("debug", now_ms(), accepted=False, reason="force_bite:disconnected")
            else:
                self._debug(self.round.force_bite)
        elif self.practice and e.key == pygame.K_k:
            self._debug(self.round.force_special)

    def _debug(self, fn) -> None:
        self.round.out = []
        fn()
        for e in self.round.out:
            self._route(e)

    def _resume(self) -> None:
        self.paused = False
        self.app._flush_input()  # the click or key that chose Resume is not a gesture

    def _restart(self) -> None:
        self._end_unfinished("restart")  # before the new round takes the next round_id
        self._next = PlayScene(self.app, self.practice)

    def _quit(self) -> None:
        from fishing.scenes.title import TitleScene

        self._end_unfinished("quit")
        self._next = TitleScene(self.app)

    def _end_unfinished(self, reason: str) -> None:
        """Practice and abandoned rounds still get a round_end row with their summary."""
        r = self.round
        if self._ended or not r.started or r.finished:
            return
        self._ended = True
        app = self.app
        for e in self.inbox:  # gestures still waiting for a step are logged, not lost
            app.log.note("gesture_unprocessed", e.t_ms, round_id=self.round_id, mode=self.mode, accepted=False,
                         reason=reason, strength=e.strength, detail={"raw": e.kind})
        self.inbox = []
        app.log.note(ev.ROUND_END, now_ms(), round_id=self.round_id, mode=self.mode, state=r.state, reason=reason,
                     value=r.score, detail=r.summary())

    # ---------------------------------------------------------------- frame
    def update(self, frame_s: float, st: MotionState, events: list[MotionEvent], stale: bool) -> Scene | None:
        self.st = st
        self.stale = stale
        app = self.app
        if self.paused:
            self.pause_menu.handle_motion(frame_s, st, events, app.source_name == "rod" and not stale)
            for e in events:
                app.log.note("gesture_paused", e.t_ms, accepted=False, reason="paused",
                             strength=e.strength, detail={"raw": e.kind})
            app.audio.reel_clicks(frame_s, 0.0, False)
            app.audio.tension(None)
            return self._next
        host_now = now_ms()
        self.inbox += events
        steps = self.stepper.advance(frame_s)
        if steps:
            hosts = iter(step_hosts(host_now, frame_s, steps))  # gestures keep their true timing
            self.inbox = deliver(steps, self.inbox, lambda evs: self._step(evs, st, next(hosts), stale))

        r = self.round
        reeling_states = R.LURE_STATES + (R.FIGHT,)
        app.audio.reel_clicks(frame_s, st.reel_rate, r.state in reeling_states and not r.frozen)
        app.audio.tension(r.fight.tension if r.state == R.FIGHT and r.fight else None)
        app.music(self.track, duck=FIGHT_MUSIC_DUCK if r.state in (R.HOOKED, R.FIGHT) else 1.0)
        self.view.update(frame_s, st)

        if r.finished:
            self.over_for += frame_s
            if self.over_for >= app.tuning.round.results_delay_s and self._next is None:
                from fishing.scenes.results import ResultsScene

                self._next = ResultsScene(app, r)
        return self._next

    def _step(self, evs: list[MotionEvent], st: MotionState, host_now: float, stale: bool) -> None:
        for e in self.round.step(self.stepper.step_s, st, evs, host_now, stale):
            self._route(e)

    def _route(self, e: GameEvent) -> None:
        app = self.app
        if e.kind == ev.BITE:
            try:
                app.source.send("BITE")
                result = "ok"
            except Exception as err:  # the buzzer must never crash the game
                result = f"error: {err}"
            self.round.mark_bite_sent(e.bite_id or 0, now_ms())
            e = replace(e, detail={**e.detail, "send": result})
            if app.settings.game_bite_sound:
                app.audio.play("bite")
        elif e.kind == ev.CAST and e.accepted:
            app.audio.play("cast")
        elif e.kind == ev.CATCH:
            app.audio.play("catch_special" if e.species == app.tuning.special.species else "catch")
        elif e.kind == ev.ESCAPE:
            app.audio.play("snap" if e.reason == "snap" else "escape")
        elif e.kind in SOUNDS:
            app.audio.play(SOUNDS[e.kind])
        app.log.event(e)
        app.note_game_event(e)
        self.view.on_event(e, self.round)

    # ---------------------------------------------------------------- drawing
    def draw(self, screen: pygame.Surface) -> None:
        app = self.app
        kb = app.source if app.source_name == "keyboard" else None
        charging = kb.charge if kb is not None and getattr(kb, "charging", False) else None
        info = ViewInfo(
            source_name=app.source_name, charging=charging, practice=self.practice,
            stale=self.stale and not app.connecting, connecting=app.connecting, paused=self.paused,
            host_now_ms=now_ms(),
        )
        self.view.draw(screen, self.round, self.st, info)
        if self.paused:
            from fishing.render import hud, palette

            w, h = screen.get_size()
            hud.panel(screen, pygame.Rect(w // 2 - 220, h // 2 - 130, 440, 260))
            hud.text(screen, app.fonts.get(palette.CARD_TITLE_SIZE), "Paused", (w // 2, h // 2 - 100),
                     palette.TEXT, "midtop")
            self.pause_menu.draw(screen, app.fonts, w // 2, h // 2 - 40)

    def overlay_lines(self) -> list[str]:
        r = self.round
        lines = [f"state {r.state:8s} {(r.sim_ms - r.state_since_ms) / 1000:5.2f} s   "
                 f"fish {len(r.fishes)}   bite_id {r.bite_id}   score {r.score}"]
        if r.fight is not None:
            f = r.fight
            lines.append(f"T {f.tension:4.2f}  strain {f.strain:4.2f}  stamina {f.stamina:4.2f}  "
                         f"dist {f.dist:5.0f}  {'RUN' if f.running else 'rest'}")
        ack = f"{r.last_ack_ms:.0f} ms" if r.last_ack_ms is not None else "-"
        lines.append(f"casts {r.stats.casts} (+{r.stats.casts_ignored} ignored)  bites {r.stats.bites} "
                     f"({r.stats.released} let go)  acks {r.stats.acks} (last {ack})")
        lines.append(f"hooked {r.stats.hooks['hooked']}  early {r.stats.hooks['early']}  "
                     f"late {r.stats.hooks['late'] + r.stats.escapes['late']}  "
                     f"no_bite {r.stats.hooks['no_bite']}  ignored {r.stats.hooks['ignored']}")
        return lines

    def on_exit(self) -> None:
        self._end_unfinished("exit")
        self.app.audio.reel_clicks(0.0, 0.0, False)
        self.app.audio.tension(None)
