"""Results: score, medal, catches, and the accuracy panel with the pass-criteria numbers."""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pygame

from fishing.input.motion import MotionEvent, MotionState
from fishing.render import hud, palette
from fishing.scenes.base import Scene
from fishing.sim.round import Round
from fishing.ui.widgets import ActionRow, Menu, TextRow

if TYPE_CHECKING:
    from fishing.app import App


class ResultsScene(Scene):
    def __init__(self, app: "App", rnd: Round) -> None:
        super().__init__(app)
        self.round = rnd
        self.summary = rnd.summary()
        self._next: Scene | None = None
        self.saved_rank: int | None = None
        self.name = ""
        practice = rnd.practice
        self.qualifies = not practice and app.highscores.qualifies(rnd.score)
        rows = []
        if self.qualifies:
            self.name_row = TextRow("Your name", lambda: self.name, self._set_name, max_len=10,
                                    placeholder="(press Enter to type)")
            rows.append(self.name_row)
        rows += [ActionRow("Play again", self._again), ActionRow("High scores", self._scores),
                 ActionRow("Title", self._title)]
        self.menu = Menu(rows, on_move=lambda: app.audio.play("menu_move"),
                         on_select=lambda: app.audio.play("menu_ok"))
        app.music("results", loop=False)

    def _set_name(self, name: str) -> None:
        self.name = name
        if self.qualifies and self.saved_rank is None:
            self.saved_rank = self.app.highscores.add(self.round, name or "ANGLER", self.app.source_name,
                                                      self.app.settings.difficulty)

    def _save_default(self) -> None:
        if self.qualifies and self.saved_rank is None:
            self._set_name(self.name or "ANGLER")

    def _again(self) -> None:
        from fishing.scenes.play import PlayScene

        self._save_default()
        self._next = PlayScene(self.app, self.round.practice)

    def _scores(self) -> None:
        from fishing.scenes.highscores import HighScoresScene

        self._save_default()
        self._next = HighScoresScene(self.app, highlight=self.saved_rank)

    def _title(self) -> None:
        from fishing.scenes.title import TitleScene

        self._save_default()
        self._next = TitleScene(self.app)

    def on_event(self, e: pygame.event.Event) -> None:
        if not self.menu.handle_event(e) and e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self._title()

    def update(self, frame_s: float, st: MotionState, events: list[MotionEvent], stale: bool) -> Scene | None:
        self.menu.handle_motion(frame_s, st, events, self.app.source_name == "rod")
        return self._next

    def draw(self, screen: pygame.Surface) -> None:
        app = self.app
        s = self.summary
        stats = self.round.stats
        w, h = screen.get_size()
        screen.fill(palette.BG_MENU)
        big = app.fonts.get(palette.TITLE_FONT_SIZE)
        mid = app.fonts.get(palette.HUD_FONT_SIZE)
        small = app.fonts.get(palette.HUD_SMALL_FONT_SIZE)
        hud.text(screen, big, f"{s['score']} pts", (w // 2, 30), palette.TEXT, "midtop")
        medal = s["medal"]
        hud.text(screen, mid, f"{medal.upper()} MEDAL" if medal else "No medal this time",
                 (w // 2, 110), palette.MEDAL_COLOURS.get(medal, palette.TEXT_DIM), "midtop")

        left = pygame.Rect(60, 160, 520, 360)
        right = pygame.Rect(w - 580, 160, 520, 360)
        hud.panel(screen, left)
        hud.panel(screen, right)
        hud.text(screen, mid, "Catches", (left.left + 20, left.top + 14))
        counts = Counter(c.name for c in stats.catches)
        y = left.top + 54
        for name, n in counts.most_common(8):
            pts = sum(c.points for c in stats.catches if c.name == name)
            hud.text(screen, small, f"{name} x{n}", (left.left + 30, y))
            hud.text(screen, small, f"{pts:+d}", (left.right - 30, y), palette.TEXT_DIM, "topright")
            y += 28
        if not counts:
            hud.text(screen, small, "Nothing this time.", (left.left + 30, y), palette.TEXT_DIM)
        hud.text(screen, small, f"Biggest: {s['biggest'] or '-'}    Best streak: {s['best_streak']}",
                 (left.left + 20, left.bottom - 36), palette.WARN)

        hud.text(screen, mid, "Accuracy (your pass criteria)", (right.left + 20, right.top + 14))
        hooks = s["hooks"]
        esc = s["escapes"]
        lines = [
            f"Cast gestures: {s['casts']} accepted, {s['casts_ignored']} ignored",
            f"Bites: {s['bites']}    BITE acks: {s['acks']}",
            f"Hook-sets: {hooks['hooked']} hooked, {hooks['early']} early, {hooks['late']} late",
            f"           {hooks['no_bite']} with no bite, {hooks['ignored']} ignored",
            f"Escapes: {esc['snap']} snapped, {esc['slack']} slack, {esc['line_out']} line out",
            f"         {esc['late']} too late, {esc['early']} too early",
        ]
        if stats.reactions_ms:
            med = sorted(stats.reactions_ms)[len(stats.reactions_ms) // 2]
            lines.append(f"Median hook reaction: {med:.0f} ms")
        y = right.top + 54
        for line in lines:
            hud.text(screen, small, line, (right.left + 30, y))
            y += 30

        if self.qualifies and self.saved_rank is None:
            hud.text(screen, mid, "New high score! Enter your name:", (w // 2, h - 230), palette.GOLD, "midtop")
        elif self.saved_rank is not None:
            hud.text(screen, mid, f"Saved as #{self.saved_rank}", (w // 2, h - 230), palette.GOLD, "midtop")
        self.menu.draw(screen, app.fonts, w // 2, h - 190)
