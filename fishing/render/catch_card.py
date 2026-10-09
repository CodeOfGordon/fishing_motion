"""The catch card (a large coloured drawing of the fish, its name, size, points and
multipliers), the escape banner, and small species icons for the bonus board."""
from __future__ import annotations

import math
import random

import pygame

from fishing.render import hud
from fishing.render import palette as P
from fishing.render.pond import mix
from fishing.sim import round as R
from fishing.ui.widgets import Fonts

_PORTRAITS: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}
_PANELS: dict[tuple[int, int, tuple], pygame.Surface] = {}

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
STALK = 0.2  # tail-root thickness (x body height)
HUMP = 1.3  # >1 moves the deepest point of the body toward the head
TAIL_LEN = 0.26  # x body length
FILL_W = 0.9  # the fish spans this much of the portrait width...
FILL_H = 0.62  # ...and its body at most this much of the height


def _ease_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def portrait(sid: str, size: tuple[int, int]) -> pygame.Surface:
    """A side-on drawing of the species in its real colours (cached)."""
    key = (sid, size)
    surf = _PORTRAITS.get(key)
    if surf is None:
        surf = _boot(size) if sid == "old_boot" else _fish(sid, size)
        _PORTRAITS[key] = surf
    return surf


def _fish(sid: str, size: tuple[int, int]) -> pygame.Surface:
    ss = P.PORTRAIT_SUPERSAMPLE
    w, h = size[0] * ss, size[1] * ss
    aspect, tail_style, marks = P.PORTRAITS.get(sid, (0.34, "fork", ()))
    base = P.SPECIES_COLOURS.get(sid, P.TEXT_DIM)
    back, belly = mix(base, BLACK, 0.38), mix(base, WHITE, 0.55)
    fin = P.MARK_ORANGE if "orange_fins" in marks else mix(base, BLACK, 0.22)
    rng = random.Random(sid)

    bl = w * FILL_W / (1 + TAIL_LEN)
    bl = min(bl, h * FILL_H / aspect)
    bh, tl = aspect * bl, TAIL_LEN * bl
    left = (w - bl - tl) / 2
    root = left + tl
    cy = h * 0.52

    def half_h(u: float) -> float:
        nose = 0.55 if "snout" in marks else 0.75
        return bh / 2 * max(STALK, math.sin(math.pi * u ** HUMP) ** nose)

    n = 48
    top = [(root + bl * i / n, cy - half_h(i / n) * 1.04) for i in range(n + 1)]
    bot = [(root + bl * i / n, cy + half_h(i / n) * 0.96) for i in range(n + 1)]
    body = top + bot[::-1]

    def top_at(u):
        return top[round(u * n)]

    def bot_at(u):
        return bot[round(u * n)]

    out = pygame.Surface((w, h), pygame.SRCALPHA)
    if "glow" in marks:
        glow_r = bl * 0.62
        for r in range(int(glow_r), 0, -ss * 2):
            a = round(70 * max(0.0, 1 - r / glow_r) ** 1.5)
            pygame.draw.circle(out, (*P.CARD_GLOW, a), (w / 2, cy), r)

    # fins behind the body
    th = bh * (0.62 if tail_style == "fork" else 0.5)
    if tail_style == "fork":
        tail = [(root + tl * 0.1, cy - bh * 0.1), (left, cy - th), (left + tl * 0.42, cy), (left, cy + th),
                (root + tl * 0.1, cy + bh * 0.1)]
    else:
        tail = [(root + tl * 0.1, cy - bh * 0.1), (left + tl * 0.12, cy - th), (left, cy - th * 0.35),
                (left, cy + th * 0.35), (left + tl * 0.12, cy + th), (root + tl * 0.1, cy + bh * 0.1)]
    d0, d1 = (0.08, 0.3) if "snout" in marks else (0.36, 0.72)
    (ax, ay), (bx, by) = top_at(d0), top_at(d1)
    dorsal = [(ax, ay + 2 * ss), (ax + bl * 0.07, ay - bh * 0.34), (bx - bl * 0.05, by - bh * 0.22), (bx, by + 2 * ss)]
    (cx0, cy0), (cx1, cy1) = bot_at(0.12), bot_at(0.3)
    anal = [(cx0, cy0 - 2 * ss), (cx0 + bl * 0.03, cy0 + bh * 0.2), (cx1, cy1 - 2 * ss)]
    px, py = bot_at(0.56)
    pelvic = [(px - bl * 0.04, py - 2 * ss), (px - bl * 0.1, py + bh * 0.2), (px + bl * 0.03, py - 2 * ss)]
    for poly in (tail, dorsal, anal, pelvic):
        pygame.draw.polygon(out, (*fin, 255), poly)
        pygame.draw.lines(out, (*P.PORTRAIT_OUTLINE, 255), True, poly, ss * 2)
    for i in range(1, 5):  # fin rays on the tail
        y = cy - th * 0.8 + th * 1.6 * i / 5
        pygame.draw.line(out, (*mix(fin, BLACK, 0.25), 255), (root, cy + (y - cy) * 0.2), (left + tl * 0.2, y), ss)

    # body: back -> base -> belly gradient, markings, then cut to the outline
    grad = pygame.Surface((w, h), pygame.SRCALPHA)
    y0 = cy - bh / 2
    for y in range(h):
        k = (y - y0) / bh
        col = mix(back, base, k / 0.45) if k < 0.45 else mix(base, belly, (k - 0.45) / 0.4)
        pygame.draw.line(grad, (*col, 255), (0, y), (w, y))
    dark = mix(base, BLACK, 0.5)
    if "line" in marks:
        pygame.draw.line(grad, (*dark, 255), (root, cy - bh * 0.04), (root + bl * 0.86, cy - bh * 0.08), ss * 2)
    if "bars" in marks:
        for i in range(6):
            x = root + bl * (0.2 + 0.11 * i)
            pygame.draw.line(grad, (*mix(base, BLACK, 0.42), 255), (x, 0), (x - bl * 0.02, cy + bh * 0.22),
                             round(bl * 0.045))
    if "breast" in marks:
        pygame.draw.ellipse(grad, (*mix(belly, P.MARK_ORANGE, 0.55), 255),
                            pygame.Rect(root + bl * 0.52, cy + bh * 0.05, bl * 0.34, bh * 0.4))
    if "pink_stripe" in marks:
        pygame.draw.line(grad, (*P.MARK_PINK, 255), (root, cy - bh * 0.02), (root + bl * 0.84, cy - bh * 0.06),
                         round(bh * 0.16))
    if "band" in marks:
        pts = [(root + bl * i / 12, cy - bh * 0.02 + (bh * 0.05 if i % 2 else -bh * 0.05)) for i in range(11)]
        pygame.draw.lines(grad, (*mix(base, BLACK, 0.55), 255), False, pts, round(bh * 0.13))
    if "spots" in marks:
        for _ in range(26):
            x = root + rng.uniform(0.05, 0.9) * bl
            y = cy - rng.uniform(0.05, 0.45) * bh
            pygame.draw.circle(grad, (*mix(base, BLACK, 0.6), 255), (x, y), rng.uniform(1.2, 2.4) * ss)
    if "light_spots" in marks:
        for row in range(3):
            for i in range(9):
                x = root + bl * (0.1 + 0.085 * i + 0.04 * (row % 2))
                y = cy - bh * 0.3 + bh * 0.25 * row
                pygame.draw.ellipse(grad, (*mix(base, WHITE, 0.55), 255), pygame.Rect(x, y, bl * 0.045, bh * 0.1))
    if "patches" in marks:
        for _ in range(5):
            x = root + rng.uniform(0.15, 0.85) * bl
            y = cy + rng.uniform(-0.4, 0.2) * bh
            r = rng.uniform(0.09, 0.16) * bl
            col = rng.choice((P.MARK_WHITE, P.MARK_KOI_RED))
            pygame.draw.ellipse(grad, (*col, 255), pygame.Rect(x - r, y - r * 0.6, 2 * r, 1.2 * r))
    eye = (root + bl * (0.9 if "snout" not in marks else 0.86), cy - bh * 0.12)
    if "mask" in marks:  # a bandit's mask across the eye
        pygame.draw.rect(grad, (*P.MARK_DARK, 255),
                         pygame.Rect(eye[0] - bl * 0.13, eye[1] - bh * 0.11, bl * 0.3, bh * 0.22), border_radius=ss * 3)
    if "ear" in marks:
        pygame.draw.circle(grad, (*P.MARK_DARK, 255), (root + bl * 0.74, cy - bh * 0.06), bh * 0.09)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), body)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(grad, (0, 0))

    # details on top
    gx, gy = top_at(0.78)
    pygame.draw.arc(out, (*mix(base, BLACK, 0.45), 255),
                    pygame.Rect(gx - bh * 0.25, cy - bh * 0.42, bh * 0.4, bh * 0.84), -1.1, 1.1, ss * 2)
    pec = [(root + bl * 0.7, cy + bh * 0.08), (root + bl * 0.58, cy + bh * 0.22), (root + bl * 0.6, cy + bh * 0.05)]
    pygame.draw.polygon(out, (*mix(fin, WHITE, 0.15), 230), pec)
    er = max(3 * ss, bh * 0.09)
    pygame.draw.circle(out, (*P.PORTRAIT_EYE, 255), eye, er)
    pygame.draw.circle(out, (*P.PORTRAIT_PUPIL, 255), (eye[0] + er * 0.2, eye[1]), er * 0.6)
    pygame.draw.circle(out, (*WHITE, 255), (eye[0] + er * 0.4, eye[1] - er * 0.3), er * 0.22)
    nose = (root + bl, cy)
    mouth = bl * (0.14 if "big_mouth" in marks else 0.06)
    pygame.draw.line(out, (*P.PORTRAIT_OUTLINE, 255), (nose[0] - ss, cy + bh * 0.06),
                     (nose[0] - mouth, cy + bh * 0.1), ss * 2)
    if "whiskers" in marks:
        for k in (-1, 1, 2):
            pts = [(nose[0] - bl * 0.02, cy + bh * 0.04)]
            for i in range(1, 6):
                pts.append((nose[0] + bl * 0.03 * i * (1 if k > 0 else 0.8),
                            cy + bh * (0.04 + 0.06 * k * i / 5) + bh * 0.05 * i * i / 25 * k))
            pygame.draw.lines(out, (*P.PORTRAIT_OUTLINE, 255), False, pts, ss * 2)
    pygame.draw.lines(out, (*P.PORTRAIT_OUTLINE, 255), True, body, ss * 2)
    return pygame.transform.smoothscale(out, size)


def _boot(size: tuple[int, int]) -> pygame.Surface:
    ss = P.PORTRAIT_SUPERSAMPLE
    w, h = size[0] * ss, size[1] * ss
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    leather = P.SPECIES_COLOURS["old_boot"]
    dark, light = mix(leather, BLACK, 0.35), mix(leather, WHITE, 0.2)
    ol = (*P.PORTRAIT_OUTLINE, 255)
    s = min(w / 1.6, h * 0.92)  # boot units
    ox, oy = (w - s * 1.15) / 2, (h - s * 0.92) / 2

    def pt(x, y):
        return ox + x * s, oy + y * s

    boot = [pt(0.05, 0.0), pt(0.42, 0.0), pt(0.44, 0.48), pt(0.8, 0.56), pt(1.0, 0.64), pt(1.08, 0.76),
            pt(1.06, 0.82), pt(0.02, 0.82), pt(0.06, 0.4)]
    pygame.draw.polygon(out, (*leather, 255), boot)
    pygame.draw.polygon(out, (*light, 255), [pt(0.1, 0.04), pt(0.2, 0.04), pt(0.18, 0.7), pt(0.1, 0.7)])
    pygame.draw.rect(out, (*P.BOOT_SOLE, 255), pygame.Rect(*pt(0.0, 0.8), s * 1.1, s * 0.1), border_radius=ss * 3)
    for i in range(4):  # laces
        y = 0.12 + 0.11 * i
        pygame.draw.line(out, (*P.BOOT_LACE, 255), pt(0.36, y), pt(0.46, y + 0.08), ss * 2)
        pygame.draw.line(out, (*P.BOOT_LACE, 255), pt(0.36, y + 0.08), pt(0.46, y), ss * 2)
    pygame.draw.ellipse(out, (*dark, 255), pygame.Rect(*pt(0.66, 0.62), s * 0.1, s * 0.06))  # a hole
    pygame.draw.rect(out, (*dark, 255), pygame.Rect(*pt(0.03, -0.02), s * 0.42, s * 0.06), border_radius=ss * 2)
    pygame.draw.lines(out, ol, True, boot, ss * 2)
    for x, y in ((0.3, 0.95), (0.7, 0.97), (0.95, 0.93)):  # drips
        pygame.draw.circle(out, (*P.DROP_COLOUR, 255), pt(x, y), ss * 2.5)
    return pygame.transform.smoothscale(out, size)


def _panel(size: tuple[int, int], border: tuple) -> pygame.Surface:
    key = (size[0], size[1], border)
    surf = _PANELS.get(key)
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        r = surf.get_rect()
        pygame.draw.rect(surf, P.PANEL, r, border_radius=P.PANEL_RADIUS)
        pygame.draw.rect(surf, (*border, P.PANEL_BORDER_ALPHA), r, P.PANEL_BORDER_W, border_radius=P.PANEL_RADIUS)
        pygame.draw.rect(surf, (*border, P.PANEL_INNER_ALPHA), r.inflate(-2 * P.PANEL_INNER_INSET, -2 * P.PANEL_INNER_INSET),
                         1, border_radius=P.PANEL_INNER_RADIUS)
        _PANELS[key] = surf
    return surf


def _catch_extras(rnd: R.Round, c: R.Catch) -> list[str]:
    extras = []
    if c.bonus:
        extras.append(f"BONUS x{rnd.t.scoring.bonus_mult:g}")
    if c.streak_mult > 1:
        extras.append(f"streak x{c.streak_mult:.1f}")
    if c.perfect:
        extras.append("PERFECT HOOK")
    if c.kind == "trap":
        extras.append("bait thief: streak lost")
    return extras


class Cards:
    """The catch card and the escape banner. Each card is rendered once (panel and text)
    into its own surface, then faded in as a whole with the portrait."""

    def __init__(self, fonts: Fonts) -> None:
        self.fonts = fonts
        self._card: R.Card | None = None  # the card the surface was built for (held, so ids can't be reused)
        self._surf: pygame.Surface | None = None

    def _cached(self, card: R.Card, build) -> pygame.Surface:
        if card is not self._card or self._surf is None:
            self._card, self._surf = card, build()
        return self._surf

    def _build_catch(self, rnd: R.Round, c: R.Catch) -> pygame.Surface:
        accent = P.SPECIES_COLOURS.get(c.species, P.CARD_BORDER)
        surf = _panel(P.CARD_SIZE, mix(accent, WHITE, P.PANEL_BORDER_LIGHTEN)).copy()
        cx = surf.get_width() // 2
        colour = P.GOLD if c.kind == "special" else P.BAD if c.kind == "trap" else P.TEXT
        title = self.fonts.get(P.CARD_TITLE_SIZE)
        y = P.CARD_PORTRAIT_TOP + P.CARD_PORTRAIT[1] + P.CARD_NAME_GAP
        r = hud.text(surf, title, c.name, (cx, y), colour, "midtop")
        size = f"{c.size_cm:.0f} cm" if c.kind != "junk" else "a soggy boot"
        r = hud.text(surf, self.fonts.get(P.HUD_FONT_SIZE), size, (cx, r.bottom + P.CARD_SIZE_GAP), P.TEXT, "midtop")
        hud.text(surf, title, f"{c.points:+d} pts", (cx, r.bottom + P.CARD_POINTS_GAP),
                 P.GOOD if c.points > 0 else P.BAD, "midtop")
        extras = _catch_extras(rnd, c)
        if extras:
            hud.text(surf, self.fonts.get(P.HUD_SMALL_FONT_SIZE), "   ".join(extras),
                     (cx, surf.get_height() - P.CARD_EXTRAS_FROM_BOTTOM), P.WARN, "midtop")
        return surf

    def draw_catch_card(self, surface: pygame.Surface, rnd: R.Round, progress: float, t: float) -> None:
        card = rnd.card
        if card is None or card.catch is None:
            return
        c = card.catch
        w, h = surface.get_size()
        slide = _ease_out(progress / P.CARD_SLIDE_IN)
        alpha = round(255 * min(1.0, slide * P.CARD_FADE_IN))
        rect = pygame.Rect((0, 0), P.CARD_SIZE)
        rect.center = (w // 2, round(h // 2 + (1 - slide) * P.CARD_SLIDE_PX))
        surf = self._cached(card, lambda: self._build_catch(rnd, c))
        surf.set_alpha(alpha)
        surface.blit(surf, rect)
        pic = portrait(c.species, P.CARD_PORTRAIT)
        bob = math.sin(t * P.CARD_BOB_RAD_S) * P.CARD_BOB_PX
        pic.set_alpha(alpha)
        surface.blit(pic, pic.get_rect(midtop=(rect.centerx, rect.top + P.CARD_PORTRAIT_TOP + bob)))

    def _build_escape(self, card: R.Card) -> pygame.Surface:
        colour = P.WARN if card.kind == "early" else P.BAD
        surf = _panel(P.ESCAPE_CARD_SIZE, colour).copy()
        hud.text(surf, self.fonts.get(P.CARD_TITLE_SIZE), card.text, surf.get_rect().center, colour, "center")
        return surf

    def draw_escape_card(self, surface: pygame.Surface, rnd: R.Round, progress: float) -> pygame.Rect | None:
        card = rnd.card
        if card is None:
            return None
        w, _ = surface.get_size()
        rect = pygame.Rect((0, 0), P.ESCAPE_CARD_SIZE)
        # keep the bobber in view: sit above it, or below it when it's near the top
        y = rnd.lure.y - P.ESCAPE_CARD_GAP
        if y - rect.height / 2 < P.ESCAPE_CARD_MIN_TOP:
            y = rnd.lure.y + P.ESCAPE_CARD_GAP
        rect.center = (w // 2, round(y))
        surf = self._cached(card, lambda: self._build_escape(card))
        surf.set_alpha(round(255 * _ease_out(progress / P.ESCAPE_POP_IN)))
        surface.blit(surf, rect)
        return rect
