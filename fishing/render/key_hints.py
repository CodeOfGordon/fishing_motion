"""Prompts for what to do right now: keycaps for the keyboard source, animated gesture icons for the rod."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from fishing.render import hud, motion_icons as M, palette
from fishing.render.hud import ViewInfo
from fishing.sim import round as R
from fishing.ui.widgets import Fonts

UP = "UP"  # drawn as an arrow: the font may have no glyph for one
CLICK = "click"


@dataclass(frozen=True)
class Hint:
    keys: tuple[str, ...]  # alternatives: any one of them works
    label: str
    live: bool  # press it now (bright, pulsing) vs. hold off (dim)


def hints_for(rnd: R.Round, rod: bool = False) -> list[Hint]:
    if rod:
        return rod_hints_for(rnd)
    if rnd.state == R.BITE:
        return [Hint(("J", UP, CLICK), "HOOK IT!", True)]
    if rnd.state == R.NIBBLE:
        return [Hint(("W",), "wait for the bite", False)]
    if rnd.state == R.FIGHT and rnd.fight is not None:
        f = rnd.fight
        if not f.running:
            return [Hint(("W",), "REEL", True)]
        against = "A" if f.run_dir > 0 else "D"  # the fish runs right: tilt left (A) to oppose it
        return [Hint(("W",), "don't reel", False), Hint(("S",), "EASE OFF", True), Hint((against,), "STEER BACK", True)]
    return []


def rod_hints_for(rnd: R.Round) -> list[Hint]:
    if rnd.state == R.READY:
        return [Hint((M.FLICK,), "FLICK to cast", True)]
    if rnd.state in (R.DRIFT, R.APPROACH):
        return [Hint((M.CIRCLE,), "CIRCLE to reel", True), Hint((M.TILT,), "TILT to steer", True)]
    if rnd.state == R.NIBBLE:
        return [Hint((M.CIRCLE,), "hold still", False)]
    if rnd.state == R.BITE:
        return [Hint((M.JERK,), "JERK UP!", True)]
    if rnd.state == R.FIGHT and rnd.fight is not None:
        f = rnd.fight
        if not f.running:
            return [Hint((M.CIRCLE,), "REEL", True)]
        against = M.TILT_LEFT if f.run_dir > 0 else M.TILT_RIGHT  # the fish runs right: tilt left
        return [Hint((M.CIRCLE_SLOW,), "EASE OFF", True), Hint((against,), "TILT BACK", True)]
    return []


def _cap_width(font: pygame.font.Font, name: str) -> int:
    if name in M.ICONS:
        return palette.MOTION_ICON_SIZE
    if name == UP or len(name) == 1:
        return palette.KEYHINT_KEY_SIZE
    return max(palette.KEYHINT_KEY_SIZE, font.size(name)[0] + palette.KEYHINT_KEY_PAD)


def _draw_cap(surface: pygame.Surface, font: pygame.font.Font, name: str, x: int, cy: int, live: bool,
              grow: int, t_ms: float) -> None:
    """Draw one keycap (or gesture icon) with its left edge at x (a key swells about its centre by `grow`)."""
    if name in M.ICONS:
        M.draw_icon(surface, name, x, cy, live, t_ms)
        return
    w = _cap_width(font, name)
    rect = pygame.Rect(0, 0, w + grow, palette.KEYHINT_KEY_SIZE + grow)
    rect.center = (x + w // 2, cy)
    fill = palette.KEYHINT_CAP if live else palette.KEYHINT_CAP_DIM
    ink = palette.KEYHINT_CAP_INK if live else palette.KEYHINT_CAP_INK_DIM
    pygame.draw.rect(surface, fill, rect, border_radius=palette.KEYHINT_KEY_RADIUS)
    pygame.draw.rect(surface, palette.KEYHINT_CAP_EDGE, rect, 2, border_radius=palette.KEYHINT_KEY_RADIUS)
    if name == UP:
        a = palette.KEYHINT_ARROW_PX
        cx, c = rect.center
        pygame.draw.polygon(surface, ink, [(cx, c - a), (cx - a, c + a // 2 + 1), (cx + a, c + a // 2 + 1)])
    else:
        img = font.render(name, True, ink)
        surface.blit(img, img.get_rect(center=rect.center))


def _group_width(fonts: Fonts, h: Hint) -> int:
    key_font = fonts.get(palette.HUD_FONT_SIZE)
    or_w = fonts.get(palette.HUD_SMALL_FONT_SIZE).size("or")[0]
    caps = sum(_cap_width(key_font, k) for k in h.keys)
    gaps = (len(h.keys) - 1) * (or_w + 2 * palette.KEYHINT_KEY_GAP)
    return caps + gaps + palette.KEYHINT_LABEL_GAP + key_font.size(h.label)[0]


def draw_key_hints(surface: pygame.Surface, fonts: Fonts, rnd: R.Round, info: ViewInfo) -> None:
    rod = info.source_name == "rod"
    if info.source_name not in ("keyboard", "rod") or info.attract or info.paused or rnd.frozen \
            or info.stale or info.connecting:
        return
    hints = hints_for(rnd, rod)
    if not hints:
        return
    font = fonts.get(palette.HUD_FONT_SIZE)
    small = fonts.get(palette.HUD_SMALL_FONT_SIZE)
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * info.host_now_ms / palette.KEYHINT_PULSE_MS)

    widths = [_group_width(fonts, h) for h in hints]
    total = sum(widths) + palette.KEYHINT_GROUP_GAP * (len(hints) - 1)
    w, screen_h = surface.get_size()
    pad = palette.KEYHINT_PILL_PAD
    row_h = palette.MOTION_ICON_SIZE if rod else palette.KEYHINT_KEY_SIZE
    cy = screen_h - palette.KEYHINT_BOTTOM_PX - row_h // 2 - pad
    pill = pygame.Rect(0, 0, total + 2 * pad, row_h + 2 * pad)
    pill.center = (w // 2, cy)
    hud.panel(surface, pill, palette.HUD_PILL, palette.HUD_PILL_RADIUS)

    x = pill.left + pad
    for h in hints:
        grow = round(palette.KEYHINT_PULSE_GROW * pulse) if h.live and not rod else 0
        for i, k in enumerate(h.keys):
            if i:
                x += palette.KEYHINT_KEY_GAP
                x = hud.text(surface, small, "or", (x, cy), palette.TEXT_DIM, "midleft").right + palette.KEYHINT_KEY_GAP
            _draw_cap(surface, font, k, x, cy, h.live, grow, info.host_now_ms)
            x += _cap_width(font, k)
        colour = palette.WARN if h.live else palette.TEXT_DIM
        x = hud.text(surface, font, h.label, (x + palette.KEYHINT_LABEL_GAP, cy), colour, "midleft").right
        x += palette.KEYHINT_GROUP_GAP
