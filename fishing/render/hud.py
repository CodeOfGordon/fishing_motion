"""HUD and on-screen text shared by the plain and art views."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from fishing.render import palette
from fishing.sim import round as R
from fishing.ui.widgets import Fonts


@dataclass
class ViewInfo:
    """Things the view needs that aren't in the round."""

    source_name: str
    charging: float | None  # keyboard cast power while Space is held
    practice: bool
    stale: bool
    connecting: bool
    paused: bool
    host_now_ms: float
    attract: bool = False  # title-screen backdrop: no HUD


def text(surface: pygame.Surface, font: pygame.font.Font, s: str, pos: tuple[float, float],
         colour=palette.TEXT, anchor: str = "topleft", shadow: bool = True) -> pygame.Rect:
    img = font.render(s, True, colour)
    rect = img.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    if shadow:
        surface.blit(font.render(s, True, palette.TEXT_SHADOW), rect.move(2, 2))
    surface.blit(img, rect)
    return rect


def panel(surface: pygame.Surface, rect: pygame.Rect, colour=palette.PANEL, radius: int = 12) -> None:
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, colour, s.get_rect(), border_radius=radius)
    surface.blit(s, rect)


def fmt_clock(seconds: float) -> str:
    s = max(0, math.ceil(seconds))
    return f"{s // 60}:{s % 60:02d}"


def draw_hud(surface: pygame.Surface, fonts: Fonts, rnd: R.Round, info: ViewInfo, reel: float,
             crank_angle: float) -> None:
    w, h = surface.get_size()
    big = fonts.get(palette.HUD_FONT_SIZE)
    small = fonts.get(palette.HUD_SMALL_FONT_SIZE)

    text(surface, big, f"Score {rnd.score}", (20, 14))
    if rnd.streak >= 2:
        text(surface, small, f"Streak x{rnd.streak}", (20, 46), palette.WARN)

    if rnd.time_left_s is not None:
        warn = rnd.time_left_s <= rnd.t.round.frenzy_s
        pulse = 1.0 + (0.12 * math.sin(info.host_now_ms / 90) if warn and rnd.time_left_s > 0 else 0)
        font = fonts.get(int(palette.HUD_FONT_SIZE * 1.25 * pulse))
        text(surface, font, fmt_clock(rnd.time_left_s), (w / 2, 12),
             palette.BAD if warn else palette.TEXT, "midtop")
        if rnd.frenzy:
            text(surface, small, "FRENZY!", (w / 2, 52), palette.WARN, "midtop")
    elif info.practice:
        text(surface, big, "PRACTICE", (w / 2, 12), palette.TEXT_DIM, "midtop")

    if rnd.bonus_species:
        spec = rnd.t.species_by_id(rnd.bonus_species)
        r = text(surface, small, f"BONUS x{rnd.t.scoring.bonus_mult:g}", (w - 20, 14), palette.GOLD, "topright")
        text(surface, big, spec.name, (w - 20, r.bottom + 2), palette.TEXT, "topright")

    # crank: spins at the newest reel_rate (no smoothing)
    cx, cy = 70, h - 70
    pygame.draw.circle(surface, palette.ROD_DARK, (cx, cy), 30, 4)
    hx = cx + math.cos(crank_angle) * 24
    hy = cy + math.sin(crank_angle) * 24
    pygame.draw.line(surface, palette.ROD, (cx, cy), (hx, hy), 5)
    pygame.draw.circle(surface, palette.LURE_WHITE, (round(hx), round(hy)), 6)
    text(surface, small, f"reel {reel:.2f}", (cx, cy + 38), palette.TEXT_DIM, "midtop")

    if rnd.state == R.FIGHT and rnd.fight is not None:
        draw_tension_bar(surface, rnd.fight.tension, rnd.fight.strain / rnd.diff.snap_strain_s,
                         pygame.Rect(w - 52, h // 2 - 150, 26, 300), info.host_now_ms)

    if info.charging is not None and rnd.state == R.READY:
        bar = pygame.Rect(w // 2 - 120, h - 40, 240, 16)
        pygame.draw.rect(surface, palette.TEXT_SHADOW, bar, border_radius=6)
        fill = bar.copy()
        fill.width = round(bar.width * info.charging)
        pygame.draw.rect(surface, palette.WARN, fill, border_radius=6)
        text(surface, small, "CAST POWER", (w // 2, bar.top - 4), palette.TEXT, "midbottom")


def draw_tension_bar(surface: pygame.Surface, tension: float, strain_frac: float, rect: pygame.Rect,
                     t_ms: float) -> None:
    pygame.draw.rect(surface, palette.TEXT_SHADOW, rect, border_radius=8)
    frac = max(0.0, min(1.0, tension))
    colour = palette.GOOD if frac < 0.6 else palette.WARN if frac < 0.9 else palette.BAD
    if strain_frac > 0 and int(t_ms / 80) % 2:
        colour = palette.LURE_WHITE
    fill = pygame.Rect(rect.left + 3, rect.bottom - 3 - round((rect.height - 6) * frac), rect.width - 6,
                       round((rect.height - 6) * frac))
    pygame.draw.rect(surface, colour, fill, border_radius=6)
    for mark in (0.6, 0.9):
        y = rect.bottom - 3 - (rect.height - 6) * mark
        pygame.draw.line(surface, palette.TEXT_DIM, (rect.left - 4, y), (rect.right + 4, y), 2)


def draw_card(surface: pygame.Surface, fonts: Fonts, rnd: R.Round, progress: float) -> None:
    """The catch/escape card in the middle of the screen."""
    card = rnd.card
    if card is None:
        return
    w, h = surface.get_size()
    slide = 1 - (1 - min(1.0, progress * 4)) ** 3  # ease out
    if card.kind == "catch" and card.catch is not None:
        c = card.catch
        rect = pygame.Rect(0, 0, 440, 200)
        rect.center = (w // 2, round(h // 2 + (1 - slide) * 120))
        panel(surface, rect)
        title = fonts.get(palette.CARD_TITLE_SIZE)
        small = fonts.get(palette.HUD_SMALL_FONT_SIZE)
        colour = palette.GOLD if c.kind == "special" else palette.BAD if c.kind == "trap" else palette.TEXT
        text(surface, title, c.name, (rect.centerx, rect.top + 18), colour, "midtop")
        size = f"{c.size_cm:.0f} cm" if c.kind != "junk" else "a soggy boot"
        text(surface, fonts.get(palette.HUD_FONT_SIZE), size, (rect.centerx, rect.top + 70), palette.TEXT, "midtop")
        pts = f"{c.points:+d} pts"
        text(surface, title, pts, (rect.centerx, rect.top + 104), palette.GOOD if c.points > 0 else palette.BAD,
             "midtop")
        extras = []
        if c.bonus:
            extras.append("BONUS x2")
        if c.streak_mult > 1:
            extras.append(f"streak x{c.streak_mult:.1f}")
        if c.perfect:
            extras.append("PERFECT HOOK")
        if extras:
            text(surface, small, "   ".join(extras), (rect.centerx, rect.bottom - 30), palette.WARN, "midtop")
    else:
        font = fonts.get(palette.CARD_TITLE_SIZE)
        colour = palette.WARN if card.kind == "early" else palette.BAD
        text(surface, font, card.text, (w // 2, round(h * 0.38)), colour, "center")


def draw_status(surface: pygame.Surface, fonts: Fonts, rnd: R.Round, info: ViewInfo) -> None:
    """Disconnects, pause and the end of the round."""
    w, h = surface.get_size()
    big = fonts.get(palette.CARD_TITLE_SIZE)
    small = fonts.get(palette.HUD_FONT_SIZE)
    if info.connecting or info.stale or rnd.frozen:
        panel(surface, pygame.Rect(w // 2 - 300, h // 2 - 70, 600, 140))
        if info.connecting:
            msg, sub = "Connecting...", "The Nano resets when the port opens (about 2 s)"
        elif info.stale:
            msg, sub = "Rod disconnected", "Check the USB cable. The round is paused."
        else:
            left = max(0.0, (rnd.resume_at_ms or info.host_now_ms) - info.host_now_ms) / 1000
            msg, sub = f"Resuming in {left:.1f}", "Rod reconnected"
        text(surface, big, msg, (w // 2, h // 2 - 22), palette.WARN, "center")
        text(surface, small, sub, (w // 2, h // 2 + 26), palette.TEXT, "center")
    if rnd.finished:
        text(surface, fonts.get(palette.TITLE_FONT_SIZE), "Time's up!", (w // 2, h // 2), palette.WARN, "center")
