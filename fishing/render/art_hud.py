"""The art view's HUD. Same information as hud.draw_hud (score, streak, clock, bonus board,
crank, tension, cast power), restyled: each cluster sits on a dark pill so coloured text
reads over the grass. Adds a tilt gauge, a "+points" pop by the score, a FRENZY! pop and
HUD-band announcements (so nothing covers the far bank, where bites happen)."""
from __future__ import annotations

import math

import pygame

from fishing.config import Tuning
from fishing.render import catch_card, hud
from fishing.render import palette as P
from fishing.render.hud import ViewInfo
from fishing.sim import round as R
from fishing.ui.widgets import Fonts

Item = tuple[pygame.Surface, pygame.Surface, pygame.Rect]  # text, its shadow, where


def _ease_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _fade(age: float, life: float, fade: float) -> float:
    """1 until the last `fade` seconds of `life`, then down to 0."""
    return max(0.0, min(1.0, (life - age) / fade))


class ArtHud:
    def __init__(self, tuning: Tuning, fonts: Fonts) -> None:
        self.t = tuning
        self.fonts = fonts
        self._pills: dict[tuple[int, int], pygame.Surface] = {}
        self._text: dict[tuple, tuple[pygame.Surface, pygame.Surface]] = {}
        self.score_pop: tuple[str, tuple[int, int, int]] | None = None
        self.score_pop_age = math.inf
        self.announce = ""
        self.announce_age = math.inf

    # ------------------------------------------------------------------ events
    def on_catch(self, value: float) -> None:
        v = int(value)
        self.score_pop = (f"{v:+d}", P.GOOD if v > 0 else P.BAD)
        self.score_pop_age = 0.0

    def on_announce(self, message: str) -> None:
        self.announce = message
        self.announce_age = 0.0

    def clear(self) -> None:
        self.score_pop_age = self.announce_age = math.inf

    def update(self, dt: float) -> None:
        self.score_pop_age += dt
        self.announce_age += dt

    # ------------------------------------------------------------------ helpers
    def _render(self, s: str, size: int, colour) -> tuple[pygame.Surface, pygame.Surface]:
        key = (s, size, colour)
        hit = self._text.get(key)
        if hit is None:
            if len(self._text) >= P.HUD_TEXT_CACHE:
                self._text.clear()
            font = self.fonts.get(size)
            hit = (font.render(s, True, colour), font.render(s, True, P.TEXT_SHADOW))
            self._text[key] = hit
        return hit

    def _item(self, s: str, size: int, colour, anchor: str, pos: tuple[float, float]) -> Item:
        img, shadow = self._render(s, size, colour)
        return img, shadow, img.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})

    def _pill(self, screen: pygame.Surface, rects: list[pygame.Rect], alpha: int = 255) -> pygame.Rect:
        pad = P.HUD_PILL_PAD
        box = rects[0].unionall(rects[1:])
        box = pygame.Rect(box.left - pad, box.top - pad, box.width + 2 * pad + P.HUD_SHADOW_PX,
                          box.height + 2 * pad + P.HUD_SHADOW_PX)
        surf = self._pills.get(box.size)
        if surf is None:
            if len(self._pills) >= P.HUD_TEXT_CACHE:
                self._pills.clear()
            surf = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(surf, P.HUD_PILL, surf.get_rect(), border_radius=P.HUD_PILL_RADIUS)
            self._pills[box.size] = surf
        surf.set_alpha(alpha)  # shared: always set before blitting
        screen.blit(surf, box)
        return box

    @staticmethod
    def _blit(screen: pygame.Surface, item: Item, alpha: int = 255) -> None:
        img, shadow, rect = item
        img.set_alpha(alpha)  # shared (cached): always set before blitting
        shadow.set_alpha(alpha)
        screen.blit(shadow, rect.move(P.HUD_SHADOW_PX, P.HUD_SHADOW_PX))
        screen.blit(img, rect)

    def _cluster(self, screen: pygame.Surface, items: list[Item], alpha: int = 255) -> pygame.Rect:
        box = self._pill(screen, [it[2] for it in items], alpha)
        for it in items:
            self._blit(screen, it, alpha)
        return box

    # ------------------------------------------------------------------ drawing
    def draw(self, screen: pygame.Surface, rnd: R.Round, info: ViewInfo, reel: float, tilt: float,
             crank: float) -> None:
        w, h = screen.get_size()
        self._draw_score(screen, rnd)
        self._draw_centre(screen, rnd, info, w)
        self._draw_bonus(screen, rnd, w)
        self._draw_dials(screen, reel, tilt, crank, h)
        if rnd.state == R.FIGHT and rnd.fight is not None:
            self._draw_tension(screen, rnd.fight.tension, rnd.fight.strain / rnd.diff.snap_strain_s,
                               info.host_now_ms, w, h)
        if info.charging is not None and rnd.state == R.READY:
            self._draw_cast_power(screen, info.charging, h)

    def _draw_score(self, screen: pygame.Surface, rnd: R.Round) -> None:
        score = self._item(f"Score {rnd.score}", P.HUD_FONT_SIZE, P.TEXT, "topleft", (P.HUD_EDGE_PX, P.HUD_TOP_PX))
        items = [score]
        if rnd.streak >= 2:
            items.append(self._item(f"Streak x{rnd.streak}", P.HUD_SMALL_FONT_SIZE, P.WARN, "topleft",
                                    (P.HUD_EDGE_PX, score[2].bottom + P.HUD_LINE_GAP)))
        box = self._cluster(screen, items)
        if self.score_pop is not None and self.score_pop_age < P.SCORE_POP_S:
            text, colour = self.score_pop
            pop = self._item(text, P.HUD_FONT_SIZE, colour, "topleft", (box.right + P.SCORE_POP_GAP - P.HUD_PILL_PAD,
                                                                        P.HUD_TOP_PX))
            alpha = round(255 * _fade(self.score_pop_age, P.SCORE_POP_S, P.SCORE_POP_FADE_S))
            self._cluster(screen, [pop], alpha)

    def _draw_centre(self, screen: pygame.Surface, rnd: R.Round, info: ViewInfo, w: int) -> None:
        """The clock (or PRACTICE), FRENZY! under it, then any announcement."""
        cx = w / 2
        bottom = P.HUD_TOP_PX
        if rnd.time_left_s is not None:
            left = rnd.time_left_s
            warn = left <= self.t.round.frenzy_s
            pulse = 1.0 + (P.CLOCK_PULSE * math.sin(info.host_now_ms / P.CLOCK_PULSE_MS) if warn and left > 0 else 0)
            label = hud.fmt_clock(left)
            colour = P.BAD if warn else P.TEXT
            # the pill fits the biggest pulse, so it holds still while the digits throb
            big = self._item(label, int(P.HUD_FONT_SIZE * P.CLOCK_SCALE * (1 + P.CLOCK_PULSE)), colour, "midtop",
                             (cx, P.HUD_TOP_PX))
            clock = self._item(label, int(P.HUD_FONT_SIZE * P.CLOCK_SCALE * pulse), colour, "center",
                               big[2].center)
            rects = [big[2]]
            frenzy = None
            if rnd.frenzy:
                frenzy = self._item("FRENZY!", P.HUD_SMALL_FONT_SIZE, P.WARN, "midtop",
                                    (cx, big[2].bottom + P.HUD_LINE_GAP))
                rects.append(frenzy[2])
            box = self._pill(screen, rects)
            self._blit(screen, clock)
            if frenzy is not None:
                pop = _ease_out((self.t.round.frenzy_s - left) / P.FRENZY_POP_S)
                scale = P.FRENZY_POP_FROM + (1 - P.FRENZY_POP_FROM) * pop
                if scale > 1.01:
                    frenzy = self._item("FRENZY!", round(P.HUD_SMALL_FONT_SIZE * scale), P.WARN, "center",
                                        frenzy[2].center)
                self._blit(screen, frenzy)
            bottom = box.bottom
        elif info.practice:
            bottom = self._cluster(screen, [self._item("PRACTICE", P.HUD_FONT_SIZE, P.TEXT_DIM, "midtop",
                                                       (cx, P.HUD_TOP_PX))]).bottom
        if self.announce_age < P.ANNOUNCE_S:
            alpha = round(255 * _fade(self.announce_age, P.ANNOUNCE_S, P.ANNOUNCE_FADE_S))
            item = self._item(self.announce, P.HUD_SMALL_FONT_SIZE, P.GOLD, "midtop",
                              (cx, bottom + P.HUD_LINE_GAP + P.HUD_PILL_PAD))
            self._cluster(screen, [item], alpha)

    def _draw_bonus(self, screen: pygame.Surface, rnd: R.Round, w: int) -> None:
        if not rnd.bonus_species:
            return
        spec = rnd.t.species_by_id(rnd.bonus_species)
        right = w - P.HUD_EDGE_PX
        label = self._item(f"BONUS x{rnd.t.scoring.bonus_mult:g}", P.HUD_SMALL_FONT_SIZE, P.GOLD, "topright",
                           (right, P.HUD_TOP_PX))
        name = self._item(spec.name, P.HUD_FONT_SIZE, P.TEXT, "topright", (right, label[2].bottom + P.HUD_LINE_GAP))
        icon = catch_card.portrait(spec.id, P.BONUS_ICON)
        icon_rect = icon.get_rect(midright=(name[2].left - P.BONUS_ICON_GAP, name[2].centery))
        self._pill(screen, [label[2], name[2], icon_rect])
        icon.set_alpha(255)
        screen.blit(icon, icon_rect)
        self._blit(screen, label)
        self._blit(screen, name)

    def _draw_dials(self, screen: pygame.Surface, reel: float, tilt: float, crank: float, h: int) -> None:
        """Bottom-left: the crank (spins at the newest reel_rate, no smoothing) and the tilt gauge."""
        px, py, pw, ph = P.DIAL_PANEL
        self._pill(screen, [pygame.Rect(px + P.HUD_PILL_PAD, h - py + P.HUD_PILL_PAD,
                                        pw - 2 * P.HUD_PILL_PAD - P.HUD_SHADOW_PX,
                                        ph - 2 * P.HUD_PILL_PAD - P.HUD_SHADOW_PX)])
        small = P.HUD_SMALL_FONT_SIZE
        cx, cy = P.CRANK_AT[0], h - P.CRANK_AT[1]
        pygame.draw.circle(screen, P.TEXT_DIM, (cx, cy), P.CRANK_R, P.CRANK_RING_W)
        hx, hy = cx + math.cos(crank) * P.CRANK_ARM, cy + math.sin(crank) * P.CRANK_ARM
        pygame.draw.line(screen, P.ROD, (cx, cy), (hx, hy), P.CRANK_ARM_W)
        pygame.draw.circle(screen, P.LURE_WHITE, (round(hx), round(hy)), P.CRANK_KNOB_R)
        self._blit(screen, self._item(f"reel {reel:.2f}", small, P.TEXT_DIM, "midtop",
                                      (cx, cy + P.CRANK_R + P.DIAL_LABEL_GAP)))

        gx, gy = P.TILT_GAUGE_AT[0], h - P.TILT_GAUGE_AT[1]
        r = P.TILT_GAUGE_R
        span = math.radians(self.t.cast.aim_max_deg)
        rect = pygame.Rect(gx - r, gy - r, 2 * r, 2 * r)
        # a dark half-dial, the +-aim arc with ticks at the ends and the middle, then the needle
        pygame.draw.circle(screen, P.TEXT_SHADOW, (gx, gy), r + P.TILT_GAUGE_RIM, 0, True, True, False, False)
        pygame.draw.arc(screen, P.TEXT_DIM, rect, math.pi / 2 - span, math.pi / 2 + span, P.TILT_GAUGE_ARC_W)
        for a in (-span, 0.0, span):
            sx, sy = math.sin(a), -math.cos(a)
            pygame.draw.line(screen, P.TEXT_DIM, (gx + sx * (r - P.TILT_GAUGE_TICK), gy + sy * (r - P.TILT_GAUGE_TICK)),
                             (gx + sx * r, gy + sy * r), P.TILT_GAUGE_ARC_W)
        a = max(-1.0, min(1.0, tilt)) * span
        tip = r - P.TILT_GAUGE_ARC_W
        pygame.draw.line(screen, P.WARN, (gx, gy), (gx + math.sin(a) * tip, gy - math.cos(a) * tip), P.TILT_NEEDLE_W)
        pygame.draw.circle(screen, P.WARN, (gx, gy), P.TILT_HUB_R)
        self._blit(screen, self._item(f"tilt {tilt:+.2f}", small, P.TEXT_DIM, "midtop",
                                      (gx, gy + P.DIAL_LABEL_GAP + P.HUD_LINE_GAP)))

    def _draw_tension(self, screen: pygame.Surface, tension: float, strain_frac: float, t_ms: float, w: int,
                      h: int) -> None:
        right, bw, bh = P.TENSION_BAR
        rect = pygame.Rect(w - right, h // 2 - bh // 2, bw, bh)
        pygame.draw.rect(screen, P.TEXT_SHADOW, rect, border_radius=P.TENSION_BAR_RADIUS)
        frac = max(0.0, min(1.0, tension))
        colour = P.GOOD if frac < P.TENSION_WARN_AT else P.WARN if frac < P.TENSION_DANGER_AT else P.BAD
        if strain_frac > 0 and int(t_ms / P.TENSION_FLASH_MS) % 2:
            colour = P.LINE_DANGER_HOT  # straining toward a snap: flash hot, never the "safe" white
        inset = P.TENSION_BAR_INSET
        inner = rect.height - 2 * inset
        fill = pygame.Rect(rect.left + inset, rect.bottom - inset - round(inner * frac), rect.width - 2 * inset,
                           round(inner * frac))
        pygame.draw.rect(screen, colour, fill, border_radius=P.TENSION_BAR_RADIUS - inset)
        for mark in (P.TENSION_WARN_AT, P.TENSION_DANGER_AT):
            y = rect.bottom - inset - inner * mark
            pygame.draw.line(screen, P.TEXT_DIM, (rect.left - P.TENSION_MARK_OVERHANG, y),
                             (rect.right + P.TENSION_MARK_OVERHANG, y), P.TENSION_MARK_W)

    def _draw_cast_power(self, screen: pygame.Surface, charging: float, h: int) -> None:
        """On the grass right of the dock, clear of the rod and its reel."""
        x, y, bw, bh = P.CAST_POWER_RECT
        bar = pygame.Rect(x, h - y, bw, bh)
        label = self._item("CAST POWER", P.HUD_SMALL_FONT_SIZE, P.TEXT, "midbottom",
                           (bar.centerx, bar.top - P.CAST_POWER_LABEL_GAP))
        self._pill(screen, [label[2], bar])
        self._blit(screen, label)
        pygame.draw.rect(screen, P.TEXT_SHADOW, bar, border_radius=P.CAST_POWER_RADIUS)
        fill = bar.copy()
        fill.width = round(bar.width * max(0.0, min(1.0, charging)))
        if fill.width:
            pygame.draw.rect(screen, P.WARN, fill, border_radius=P.CAST_POWER_RADIUS)
