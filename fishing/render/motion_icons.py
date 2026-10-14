"""Animated icons for the four rod gestures, drawn in code. Used by the key-hint row for the rod source."""
from __future__ import annotations

import math

import pygame

from fishing.render import palette as P

FLICK = "@flick"  # forward flick: cast
JERK = "@jerk"  # upward jerk: hook-set
CIRCLE = "@circle"  # wrist circles: reel
CIRCLE_SLOW = "@circle_slow"  # slow circles: ease off
TILT = "@tilt"  # tilt both ways: steer
TILT_LEFT = "@tilt_left"
TILT_RIGHT = "@tilt_right"
HOLD = "@hold"  # how to hold the rod: upright, leaning slightly toward the screen
ICONS = (FLICK, JERK, CIRCLE, CIRCLE_SLOW, TILT, TILT_LEFT, TILT_RIGHT, HOLD)


def _ease(p: float) -> float:
    return 1 - (1 - p) ** 3


def _arrow(surface: pygame.Surface, colour, tip: tuple[float, float], angle: float) -> None:
    """Arrowhead at tip pointing along angle (radians, screen coordinates)."""
    a = P.MOTION_ARROW_PX
    pts = [tip] + [(tip[0] - a * math.cos(angle + s * 0.5), tip[1] - a * math.sin(angle + s * 0.5)) for s in (-1, 1)]
    pygame.draw.polygon(surface, colour, pts)


def _rod(surface: pygame.Surface, colour, pivot: tuple[float, float], deg: float, width: int = P.MOTION_ROD_W) -> tuple[float, float]:
    """A rod from pivot at deg (0 = right, 90 = up). Returns its tip."""
    r = math.radians(deg)
    tip = (pivot[0] + math.cos(r) * P.MOTION_ROD_LEN, pivot[1] - math.sin(r) * P.MOTION_ROD_LEN)
    pygame.draw.line(surface, colour, pivot, tip, width)
    return tip


def _ghost_rod(surface: pygame.Surface, colour, pivot: tuple[float, float], deg: float) -> None:
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    _rod(layer, (*colour[:3], P.MOTION_GHOST_ALPHA), pivot, deg)
    surface.blit(layer, (0, 0))


def draw_icon(surface: pygame.Surface, name: str, x: int, cy: int, live: bool, t_ms: float) -> None:
    """Draw one icon tile with its left edge at x, centred on cy."""
    size = P.MOTION_ICON_SIZE
    tile = pygame.Rect(x, cy - size // 2, size, size)
    pygame.draw.rect(surface, P.MOTION_TILE, tile, border_radius=P.KEYHINT_KEY_RADIUS)
    pygame.draw.rect(surface, P.MOTION_TILE_EDGE, tile, 2, border_radius=P.KEYHINT_KEY_RADIUS)
    ink = P.WARN if live else P.TEXT_DIM
    rod = P.ROD if live else P.ROD_DARK
    art = surface.subsurface(tile.inflate(-4, -4))
    _DRAW[name](art, ink, rod, (art.get_width() / 2, art.get_height() / 2), t_ms)


def _flick(s, ink, rod, c, t):
    pivot = (c[0] - 14, c[1] + 16)
    p = (t % P.MOTION_FLICK_PERIOD_MS) / P.MOTION_FLICK_PERIOD_MS
    k = _ease(min(1.0, p / P.MOTION_FLICK_SWING))
    _ghost_rod(s, rod, pivot, P.MOTION_FLICK_FROM_DEG)
    _ghost_rod(s, rod, pivot, P.MOTION_FLICK_TO_DEG)
    _rod(s, rod, pivot, P.MOTION_FLICK_FROM_DEG + (P.MOTION_FLICK_TO_DEG - P.MOTION_FLICK_FROM_DEG) * k)
    y = c[1] - 18
    pygame.draw.line(s, ink, (c[0] - 4, y), (c[0] + 14, y), 3)  # forward arrow
    _arrow(s, ink, (c[0] + 20, y), 0.0)


def _jerk(s, ink, rod, c, t):
    p = (t % P.MOTION_JERK_PERIOD_MS) / P.MOTION_JERK_PERIOD_MS
    k = _ease(p / P.MOTION_JERK_RISE) if p < P.MOTION_JERK_RISE else 1 - (p - P.MOTION_JERK_RISE) / (1 - P.MOTION_JERK_RISE)
    lift = P.MOTION_JERK_TRAVEL_PX * k
    base = (c[0], c[1] + 22 - lift)
    _ghost_rod(s, rod, (c[0], c[1] + 22), 90)
    _rod(s, rod, base, 90)
    pygame.draw.line(s, ink, (c[0] + 18, c[1] + 4), (c[0] + 18, c[1] - 14), 3)  # upward arrow
    _arrow(s, ink, (c[0] + 18, c[1] - 22), -math.pi / 2)


def _circle(period):
    def draw(s, ink, rod, c, t):
        rx = P.MOTION_CIRCLE_RADIUS
        ry = rx * P.MOTION_CIRCLE_SQUASH
        top = (c[0], c[1] - P.MOTION_CIRCLE_TOP)
        ring = pygame.Rect(0, 0, 2 * rx, 2 * ry)
        ring.center = (round(top[0]), round(top[1]))
        pygame.draw.ellipse(s, P.MOTION_TILE_EDGE, ring, 2)
        a = 2 * math.pi * (t % period) / period
        tip = (top[0] + math.cos(a) * rx, top[1] + math.sin(a) * ry)
        pygame.draw.line(s, rod, (c[0] - 4, c[1] + 24), tip, P.MOTION_ROD_W - 1)  # the rod stays upright, the tip circles
        pygame.draw.circle(s, ink, (round(tip[0]), round(tip[1])), 5)
        _arrow(s, ink, (top[0] + rx + 4, top[1] + 3), math.pi / 2)  # a static "which way" cue on the right edge
    return draw


def _tilt(direction: int | None):
    """direction: -1 left, +1 right, None = swing both ways."""
    def draw(s, ink, rod, c, t):
        pivot = (c[0], c[1] + 22)
        sw = P.MOTION_TILT_DEG
        if direction is None:
            lean = math.sin(2 * math.pi * (t % P.MOTION_TILT_PERIOD_MS) / P.MOTION_TILT_PERIOD_MS) * sw
        else:
            p = (t % P.MOTION_TILT_PERIOD_MS) / P.MOTION_TILT_PERIOD_MS
            lean = direction * sw * math.sin(math.pi * p)  # lean out and back
        _ghost_rod(s, rod, pivot, 90)
        _rod(s, rod, pivot, 90 - lean)
        y = c[1] - 20
        for sign in ((-1, 1) if direction is None else (direction,)):
            pygame.draw.line(s, ink, (c[0] + sign * 3, y), (c[0] + sign * 16, y), 3)
            _arrow(s, ink, (c[0] + sign * 22, y), 0.0 if sign > 0 else math.pi)
    return draw


def _hold(s, ink, rod, c, t):
    pivot = (c[0] - 8, c[1] + 22)
    sway = math.sin(2 * math.pi * (t % P.MOTION_HOLD_PERIOD_MS) / P.MOTION_HOLD_PERIOD_MS) * P.MOTION_HOLD_SWAY_DEG
    _ghost_rod(s, rod, pivot, 90)
    _rod(s, rod, pivot, P.MOTION_HOLD_DEG + sway)
    pygame.draw.rect(s, ink, (c[0] + 22, c[1] - P.MOTION_SCREEN_H // 2, P.MOTION_SCREEN_W, P.MOTION_SCREEN_H))


_DRAW = {
    FLICK: _flick,
    JERK: _jerk,
    CIRCLE: _circle(P.MOTION_CIRCLE_PERIOD_MS),
    CIRCLE_SLOW: _circle(P.MOTION_CIRCLE_SLOW_PERIOD_MS),
    TILT: _tilt(None),
    TILT_LEFT: _tilt(-1),
    TILT_RIGHT: _tilt(1),
    HOLD: _hold,
}
