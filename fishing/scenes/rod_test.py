"""Rod Test: prompts 10 casts and 10 bites and scores the pass criteria.

It only counts gesture events from the MotionSource; it records no raw IMU data.
"""
from __future__ import annotations

import random
import statistics
from typing import TYPE_CHECKING

import pygame

from fishing.input.motion import BITE_ACK, CAST, HOOK_SET, MotionEvent, MotionState, now_ms
from fishing.render import hud, palette
from fishing.scenes.base import Scene

if TYPE_CHECKING:
    from fishing.app import App

INTRO, CASTS, HOOKS, DONE = "intro", "casts", "hooks", "done"


class RodTestScene(Scene):
    def __init__(self, app: "App") -> None:
        super().__init__(app)
        self.cfg = app.tuning.rod_test
        self.margin_ms = app.tuning.hook.delivery_margin_ms
        self.ack_ms = app.tuning.hook.ack_match_ms
        self.rng = random.Random()
        self.phase = INTRO
        self.trial = 0
        self.cast_hits: list[float | None] = []  # strength, or None if missed
        self.hook_hits: list[float | None] = []  # reaction ms, or None if missed
        self.acks: dict[int, float | None] = {}  # bite trial -> ack latency ms (None = no ack)
        self.prompt_at = 0.0
        self.window_end = 0.0
        self.bite_sent = False
        self.sent_ms = 0.0
        self.ack_open: tuple[int, float] | None = None  # (trial, send time) awaiting an ACK
        self.stale = False
        self.feedback = ""
        self.feedback_until = 0.0
        self._next: Scene | None = None
        app.log.begin_round("rodtest")
        app.music(None)  # silence, so you hear only the Uno's buzzer

    # ---------------------------------------------------------------- flow
    def _start(self) -> None:
        self.phase = CASTS
        self.trial = 0
        self.cast_hits, self.hook_hits, self.acks = [], [], {}
        self.ack_open = None
        self.feedback = ""
        self._next_cast_prompt(now_ms())
        self.app.log.note("rodtest_start", now_ms())

    def _next_cast_prompt(self, t: float) -> None:
        self.prompt_at = t + self.cfg.gap_s * 1000
        self.window_end = self.prompt_at + self.cfg.cast_window_s * 1000

    def _next_hook_prompt(self, t: float) -> None:
        self.prompt_at = t + self.rng.uniform(*self.cfg.bite_delay_s) * 1000
        self.window_end = self.prompt_at + self.cfg.hook_window_s * 1000
        self.bite_sent = False

    def _feedback(self, msg: str, t: float) -> None:
        self.feedback = msg
        self.feedback_until = t + palette.ROD_TEST_FEEDBACK_MS

    def on_event(self, e: pygame.event.Event) -> None:
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            from fishing.scenes.title import TitleScene

            if self.phase not in (INTRO, DONE):
                self.app.log.note("rodtest_abort", now_ms(), detail=self._summary())
            self._next = TitleScene(self.app)
        elif e.key in (pygame.K_RETURN, pygame.K_SPACE) and self.phase in (INTRO, DONE):
            self._start()

    def update(self, frame_s: float, st: MotionState, events: list[MotionEvent], stale: bool) -> Scene | None:
        t = now_ms()
        log = self.app.log
        for e in events:  # acks are matched to their bite whatever else is going on
            if e.kind == BITE_ACK:
                self._on_ack(e)
        gestures = [e for e in events if e.kind != BITE_ACK]
        if self.phase == INTRO:
            if self.app.source_name == "rod" and not stale and any(e.kind == HOOK_SET for e in gestures):
                self._start()
            return self._next
        if self.phase == DONE:
            self._close_ack(t)
            return self._next

        if self._handle_stale(stale, frame_s, t, gestures):
            return self._next
        if self.phase == CASTS:
            self._update_casts(t, gestures)
        else:
            self._update_hooks(t, gestures)
        self._close_ack(t)
        return self._next

    def _handle_stale(self, stale: bool, frame_s: float, t: float, gestures: list[MotionEvent]) -> bool:
        """While the rod is unplugged the test pauses; returns True if it is paused."""
        log = self.app.log
        if stale != self.stale:
            self.stale = stale
            log.note("rodtest_disconnect" if stale else "rodtest_reconnect", t, value=self.trial + 1)
            if stale and self.phase == HOOKS and self.bite_sent:
                log.note("rodtest_void", t, value=self.trial + 1, reason="disconnected after BITE")
                self.ack_open = None
                self._next_hook_prompt(t)  # repeat this trial after reconnecting
        if not stale:
            return False
        shift = frame_s * 1000.0
        self.prompt_at += shift
        self.window_end += shift
        for e in gestures:
            log.note("rodtest_gesture", e.t_ms, accepted=False, reason="disconnected",
                     strength=e.strength, value=self.trial + 1, detail={"raw": e.kind})
        return True

    def _update_casts(self, t: float, gestures: list[MotionEvent]) -> None:
        log = self.app.log
        for e in gestures:
            if e.kind != CAST:
                log.note("rodtest_gesture", e.t_ms, accepted=False, reason=f"wrong_kind:{self.phase}",
                         strength=e.strength, value=self.trial + 1, detail={"raw": e.kind})
                continue
            in_window = self.prompt_at <= e.t_ms <= self.window_end
            reason = "" if in_window else ("before_prompt" if e.t_ms < self.prompt_at else "late")
            log.note("rodtest_cast", e.t_ms, accepted=in_window, reason=reason, strength=e.strength,
                     value=self.trial + 1)
            if in_window and len(self.cast_hits) == self.trial:
                self.cast_hits.append(e.strength)
                self._feedback(f"Cast {self.trial + 1}: registered ({e.strength:.2f})", t)
                self._advance_cast(t)
        # judged on the gesture's stamp: wait the delivery margin before calling it missed
        if t > self.window_end + self.margin_ms and len(self.cast_hits) == self.trial:
            self.cast_hits.append(None)
            log.note("rodtest_cast_missed", t, accepted=False, value=self.trial + 1)
            self._feedback(f"Cast {self.trial + 1}: nothing registered", t)
            self._advance_cast(t)

    def _update_hooks(self, t: float, gestures: list[MotionEvent]) -> None:
        log = self.app.log
        if not self.bite_sent and t >= self.prompt_at:
            try:
                self.app.source.send("BITE")
                result = "ok"
            except Exception as err:  # never crash the test on a buzzer problem
                result = f"error: {err}"
            self.bite_sent = True
            self.sent_ms = now_ms()
            self.window_end = self.sent_ms + self.cfg.hook_window_s * 1000
            self.ack_open = (self.trial, self.sent_ms)
            self.acks[self.trial] = None
            log.note("rodtest_bite", self.sent_ms, value=self.trial + 1, detail={"send": result})
        for e in gestures:
            if e.kind != HOOK_SET:
                log.note("rodtest_gesture", e.t_ms, accepted=False, reason=f"wrong_kind:{self.phase}",
                         strength=e.strength, value=self.trial + 1, detail={"raw": e.kind})
                continue
            reaction = e.t_ms - self.sent_ms if self.bite_sent else None
            in_window = self.bite_sent and self.sent_ms <= e.t_ms <= self.window_end
            if in_window:
                reason = ""
            elif not self.bite_sent or (reaction is not None and reaction < 0):
                reason = "before_bite"
            else:
                reason = "late"
            log.note("rodtest_hook", e.t_ms, accepted=in_window, reason=reason, strength=e.strength,
                     value=reaction, detail={"trial": self.trial + 1})
            if in_window and len(self.hook_hits) == self.trial:
                self.hook_hits.append(reaction)
                self._feedback(f"Hook {self.trial + 1}: {reaction:.0f} ms", t)
                self._advance_hook(t)
        if self.bite_sent and t > self.window_end + self.margin_ms and len(self.hook_hits) == self.trial:
            self.hook_hits.append(None)
            log.note("rodtest_hook_missed", t, accepted=False, value=self.trial + 1)
            self._feedback(f"Hook {self.trial + 1}: nothing registered", t)
            self._advance_hook(t)

    def _on_ack(self, e: MotionEvent) -> None:
        log = self.app.log
        if self.ack_open is None:
            log.note("rodtest_ack", e.t_ms, accepted=False, reason="unmatched")
            return
        trial, sent = self.ack_open
        latency = e.t_ms - sent
        ok = 0 <= latency <= self.ack_ms
        if ok:
            self.acks[trial] = latency
            self.ack_open = None
        log.note("rodtest_ack", e.t_ms, accepted=ok, reason="" if ok else "unmatched", value=latency,
                 detail={"trial": trial + 1})

    def _close_ack(self, t: float) -> None:
        """Give up on an ACK once its window (plus the delivery margin) has passed."""
        if self.ack_open is not None and t > self.ack_open[1] + self.ack_ms + self.margin_ms:
            self.app.log.note("rodtest_ack_missed", t, accepted=False, value=self.ack_open[0] + 1)
            self.ack_open = None

    def _advance_cast(self, t: float) -> None:
        self.trial += 1
        if self.trial >= self.cfg.trials:
            self.phase = HOOKS
            self.trial = 0
            self._next_hook_prompt(t + self.cfg.gap_s * 1000)
        else:
            self._next_cast_prompt(t)

    def _advance_hook(self, t: float) -> None:
        self.trial += 1
        if self.trial >= self.cfg.trials:
            self.phase = DONE
            self.app.log.note("rodtest_done", t, detail=self._summary())
            self.app.audio.play("catch")
        else:
            self._next_hook_prompt(t)

    def _summary(self) -> dict:
        reactions = [r for r in self.hook_hits if r is not None]
        return {
            "casts": sum(h is not None for h in self.cast_hits), "cast_trials": len(self.cast_hits),
            "hooks": len(reactions), "hook_trials": len(self.hook_hits),
            "acks": sum(a is not None for a in self.acks.values()), "bites": len(self.acks),
            "median_reaction_ms": round(statistics.median(reactions)) if reactions else None,
        }

    # ---------------------------------------------------------------- drawing
    def draw(self, screen: pygame.Surface) -> None:
        app = self.app
        w, h = screen.get_size()
        t = now_ms()
        screen.fill(palette.BG_MENU)
        big = app.fonts.get(palette.TITLE_FONT_SIZE)
        mid = app.fonts.get(palette.HUD_FONT_SIZE)
        small = app.fonts.get(palette.HUD_SMALL_FONT_SIZE)
        hud.text(screen, app.fonts.get(palette.CARD_TITLE_SIZE), "Rod Test", (w // 2, 20), palette.TEXT, "midtop")
        n = self.cfg.trials
        if self.phase == INTRO:
            lines = [
                f"Part 1: {n} casts. Flick forward when it says CAST.",
                f"Part 2: {n} bites. The Uno beeps; jerk up to set the hook.",
                "The game's own bite sound is off here, so you only hear the buzzer.",
                f"Input: {app.source_name}" + ("" if app.source_name == "rod" else "  (keyboard: Space = cast, J = hook)"),
                "Press Enter (or hook-set with the rod) to start.  Esc to leave.",
            ]
            for i, line in enumerate(lines):
                hud.text(screen, mid, line, (w // 2, 180 + i * 50), palette.TEXT, "midtop")
            return
        if self.phase in (CASTS, HOOKS) and self.stale:
            msg = "Connecting..." if app.connecting else "Rod disconnected: test paused"
            hud.text(screen, big, msg, (w // 2, h // 2 - 40), palette.WARN, "center")
        elif self.phase in (CASTS, HOOKS):
            label = "Casts" if self.phase == CASTS else "Hook-sets"
            hud.text(screen, mid, f"{label}: {self.trial + 1} / {n}", (w // 2, 90), palette.TEXT_DIM, "midtop")
            if t < self.prompt_at:
                hud.text(screen, big, "Get ready...", (w // 2, h // 2 - 40), palette.TEXT_DIM, "center")
            else:
                msg = "CAST!" if self.phase == CASTS else "BITE! Jerk now!"
                left = max(0.0, (self.window_end - t) / 1000)
                hud.text(screen, big, msg, (w // 2, h // 2 - 40), palette.WARN, "center")
                hud.text(screen, mid, f"{left:.1f} s", (w // 2, h // 2 + 30), palette.TEXT, "center")
        if t < self.feedback_until:
            hud.text(screen, mid, self.feedback, (w // 2, h // 2 + 90), palette.GOOD, "center")
        s = self._summary()
        lines = [f"Casts registered: {s['casts']} / {s['cast_trials'] or 0}",
                 f"Hook-sets registered: {s['hooks']} / {s['hook_trials'] or 0}",
                 f"BITE acks: {s['acks']} / {s['bites']}"]
        if s["median_reaction_ms"] is not None:
            lines.append(f"Median hook reaction: {s['median_reaction_ms']} ms")
        panel = pygame.Rect(w // 2 - 260, h - 230, 520, 190)
        hud.panel(screen, panel)
        for i, line in enumerate(lines):
            hud.text(screen, mid, line, (panel.left + 30, panel.top + 20 + i * 40))
        if self.phase == DONE:
            target = self.cfg.pass_threshold
            ok = s["casts"] >= target and s["hooks"] >= target
            verdict = "PASS" if ok else "not yet"
            hud.text(screen, big, f"{verdict}  (need {target}/{n})", (w // 2, h // 2 - 120),
                     palette.GOOD if ok else palette.WARN, "center")
            hud.text(screen, small, "Enter to run again, Esc for the title screen", (w // 2, h // 2 - 50),
                     palette.TEXT_DIM, "center")
