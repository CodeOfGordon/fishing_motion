"""Milestone-1 view: plain shapes. Readable, fast, and replaced by the art view later."""
from __future__ import annotations

import math

import pygame

from fishing.config import Tuning
from fishing.input.motion import MotionState
from fishing.render import hud, palette
from fishing.render.hud import ViewInfo
from fishing.sim import events as ev
from fishing.sim import round as R
from fishing.sim.events import GameEvent
from fishing.ui.widgets import Fonts

CAST_ARC_HEIGHT = 90  # px the lure rises mid-cast (visual only)


class PlainView:
    def __init__(self, tuning: Tuning, fonts: Fonts) -> None:
        self.t = tuning
        self.fonts = fonts
        self.crank = 0.0
        self.floaters: list[list] = []  # [text, x, y, age, colour]

    def on_event(self, e: GameEvent, rnd: R.Round) -> None:
        if e.kind == ev.CATCH:
            self.floaters.append([f"{int(e.value):+d}", rnd.lure.x, rnd.lure.y, 0.0, palette.GOOD])
        elif e.kind == ev.HOOK_ATTEMPT and e.reason == "early":
            self.floaters.append(["Too early!", rnd.lure.x, rnd.lure.y - 20, 0.0, palette.WARN])
        elif e.kind == ev.BITE:
            self.floaters.append(["!", rnd.lure.x, rnd.lure.y - 30, 0.0, palette.BAD])

    def update(self, frame_s: float, st: MotionState) -> None:
        self.crank += st.reel_rate * 2 * math.pi * 2.5 * frame_s
        for f in self.floaters:
            f[3] += frame_s
            f[2] -= 30 * frame_s
        self.floaters = [f for f in self.floaters if f[3] < 1.2]

    def draw(self, screen: pygame.Surface, rnd: R.Round, st: MotionState, info: ViewInfo) -> None:
        p = self.t.pond
        tip = p.rod_tip
        screen.fill(palette.SKY_BANK)
        water = pygame.Rect(p.water_left, p.water_top, p.water_right - p.water_left, p.water_bottom - p.water_top)
        screen.set_clip(water)
        screen.fill(palette.WATER_DEEP)
        for zone, colour in (("deep", palette.WATER_DEEP), ("mid", palette.WATER_MID), ("shallow", palette.WATER_SHALLOW)):
            pygame.draw.circle(screen, colour, tip, p.zone(zone)[1])
        screen.set_clip(None)
        pygame.draw.rect(screen, palette.WATER_EDGE, water, 3)
        pygame.draw.rect(screen, palette.DOCK, (tip[0] - 50, p.water_bottom - 10, 100, 110))

        for f in rnd.fishes:
            colour = palette.KOI_GLOW if f.spec.kind == "special" else palette.FISH_SHADOW
            if f.spec.kind == "junk":
                pygame.draw.rect(screen, palette.DOCK_DARK, (f.x - 10, f.y - 6, 20, 12))
                continue
            length = 10 + f.size_cm * 0.45
            dx, dy = math.cos(f.heading), math.sin(f.heading)
            alpha_col = [int(c + (palette.WATER_MID[i] - c) * (1 - f.alpha)) for i, c in enumerate(colour)]
            pygame.draw.line(screen, alpha_col, (f.x - dx * length / 2, f.y - dy * length / 2),
                             (f.x + dx * length / 2, f.y + dy * length / 2), max(3, int(length / 3)))

        lure = rnd.lure
        rod_end = (tip[0] + st.tilt * 30, tip[1] - 60)
        pygame.draw.line(screen, palette.ROD, tip, rod_end, 5)
        if rnd.state == R.READY:
            aim = math.radians(st.tilt * self.t.cast.aim_max_deg)
            end = (tip[0] + math.sin(aim) * 160, tip[1] - math.cos(aim) * 160)
            pygame.draw.line(screen, palette.TEXT_DIM, rod_end, end, 2)
        elif rnd.state != R.OVER:
            lift = math.sin(math.pi * lure.flight_progress) * CAST_ARC_HEIGHT if rnd.state == R.CASTING else 0
            lx, ly = lure.x, lure.y - lift
            tension = rnd.fight.tension if rnd.fight else 0.0
            line_col = palette.LINE_DANGER if tension > 0.9 else palette.LINE_TAUT if tension > 0.6 else palette.LINE
            pygame.draw.line(screen, line_col, rod_end, (lx, ly), 2)
            r = 5 if rnd.state == R.BITE else 8
            pygame.draw.circle(screen, palette.LURE, (round(lx), round(ly)), r)

        if info.attract:
            return
        for text_, x, y, age, colour in self.floaters:
            hud.text(screen, self.fonts.get(palette.HUD_FONT_SIZE), text_, (x, y), colour, "center")
        hud.draw_hud(screen, self.fonts, rnd, info, st.reel_rate, self.crank)
        if rnd.card is not None:
            total = (self.t.round.catch_card_s if rnd.card.kind == "catch" else self.t.round.escape_card_s) * 1000
            hud.draw_card(screen, self.fonts, rnd, 1 - (rnd.card.until_ms - rnd.sim_ms) / total)
        hud.draw_status(screen, self.fonts, rnd, info)
