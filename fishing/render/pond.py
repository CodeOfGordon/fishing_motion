"""The pond: pre-rendered water, bank, dock and lily pads, plus scrolling caustics,
sparkling glints and swaying reeds. Everything is drawn in code."""
from __future__ import annotations

import math
import random

import pygame

from fishing.config import PondConfig
from fishing.render import palette as P

_BASE_CACHE: dict[tuple, "_PondBase"] = {}


def mix(a, b, t: float) -> tuple[int, ...]:
    """Blend colour a toward b by t (0..1), component-wise."""
    t = max(0.0, min(1.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class _PondBase:
    """The static layers, built once per (pond, screen size) and shared."""

    def __init__(self, pond: PondConfig, size: tuple[int, int]) -> None:
        self.pond = pond
        self.size = size
        self.rng = random.Random(P.ART_SEED)
        self.tip = pond.rod_tip
        self.water = pygame.Rect(round(pond.water_left), round(pond.water_top),
                                 round(pond.water_right - pond.water_left),
                                 round(pond.water_bottom - pond.water_top))
        w, h = size
        self.max_d = math.ceil(math.hypot(max(self.tip[0], w - self.tip[0]), max(self.tip[1], h - self.tip[1]))) + 2
        self._build_lut()
        self.background = self._build_background()
        self.mask = self._build_caustic_mask()
        self.caustics = [self._build_caustic_layer(spec) for spec in P.CAUSTIC_LAYERS]
        self.overlay = self._build_overlay()
        self.reeds = self._build_reeds()
        self.glint_sprites = self._build_glints()

    # ------------------------------------------------------------------ depth
    def _bands(self) -> tuple[list[float], list[tuple[int, int, int]]]:
        p = self.pond
        edges = [p.shallow[0], (p.shallow[1] + p.mid[0]) / 2, (p.mid[1] + p.deep[0]) / 2, p.deep[1]]
        colours = [P.WATER_NEAR, P.ART_WATER_SHALLOW, P.ART_WATER_MID, P.ART_WATER_DEEP, P.WATER_ABYSS]
        return edges, colours

    def _build_lut(self) -> None:
        edges, colours = self._bands()
        bounds = [0.0] + edges + [float(self.max_d)]

        def pure(i: int, d: float) -> tuple[int, ...]:
            lo, hi = bounds[i], bounds[i + 1]
            frac = (d - lo) / max(1.0, hi - lo)
            return mix(colours[i], (0, 0, 0), P.WATER_BAND_SHADE * max(0.0, min(1.0, frac)))

        blend = P.WATER_BAND_BLEND_PX
        lut = []
        for d in range(self.max_d + 1):
            i = sum(1 for e in edges if d >= e)
            col = pure(i, d)
            for j, e in enumerate(edges):
                if abs(d - e) < blend:
                    t = smooth((d - e + blend) / (2 * blend))
                    col = mix(pure(j, d), pure(j + 1, d), t)
                    break
            lut.append(col)
        self.lut = lut
        self.edges = edges

    def colour_at(self, x: float, y: float) -> tuple[int, ...]:
        d = int(math.hypot(x - self.tip[0], y - self.tip[1]))
        return self.lut[max(0, min(len(self.lut) - 1, d))]

    def _build_background(self) -> pygame.Surface:
        w, h = self.size
        bg = pygame.Surface(self.size)
        bg.fill(self.lut[-1])
        tip = (round(self.tip[0]), round(self.tip[1]))
        for d in range(self.max_d, 0, -1):
            pygame.draw.circle(bg, self.lut[d], tip, d, 2)
        pygame.draw.circle(bg, self.lut[0], tip, 1)

        # low-frequency mottling (+ and -), then fine grain
        cell = P.WATER_NOISE_CELL_PX
        gw, gh = w // cell + 2, h // cell + 2
        for flag in (pygame.BLEND_RGB_ADD, pygame.BLEND_RGB_SUB):
            grid = pygame.Surface((gw, gh))
            for gy in range(gh):
                for gx in range(gw):
                    v = self.rng.randint(0, P.WATER_NOISE_AMP)
                    grid.set_at((gx, gy), (v, v, v))
            bg.blit(pygame.transform.smoothscale(grid, (gw * cell, gh * cell)), (-cell // 2, -cell // 2),
                    special_flags=flag)
        tile = P.WATER_GRAIN_TILE
        for flag in (pygame.BLEND_RGB_ADD, pygame.BLEND_RGB_SUB):
            grain = pygame.Surface((tile, tile))
            for gy in range(tile):
                for gx in range(tile):
                    v = self.rng.randint(0, P.WATER_GRAIN_AMP)
                    grain.set_at((gx, gy), (v, v, v))
            for ty in range(0, h, tile):
                for tx in range(0, w, tile):
                    bg.blit(grain, (tx, ty), special_flags=flag)

        # zone edges: faint rings so the depth bands read at a glance
        for e in self.edges:
            col = mix(self.lut[min(int(e), self.max_d)], P.WATER_CONTOUR, P.WATER_CONTOUR_MIX)
            pygame.draw.circle(bg, col, tip, round(e), P.WATER_CONTOUR_WIDTH)

        # pebbles on the bottom near the dock
        stones = pygame.Surface(self.size, pygame.SRCALPHA)
        near = self.pond.shallow[0] + (self.pond.shallow[1] - self.pond.shallow[0]) / 2
        for _ in range(P.WATER_STONES):
            a = math.radians(self.rng.uniform(-80, 80))
            r = self.rng.uniform(self.pond.dock_radius, near)
            x, y = self.tip[0] + math.sin(a) * r, self.tip[1] - math.cos(a) * r
            if not self.water.collidepoint(x, y):
                continue
            s = self.rng.uniform(*P.WATER_STONE_PX)
            col = (*self.rng.choice(P.WATER_STONE_COLOURS), P.WATER_STONE_ALPHA)
            pygame.draw.ellipse(stones, col, pygame.Rect(x - s, y - s * 0.7, 2 * s, 1.4 * s))
        bg.blit(stones, (0, 0))
        return bg

    # ------------------------------------------------------------------ caustics
    def _build_caustic_mask(self) -> pygame.Surface:
        """Grey levels: caustics are strongest in the shallows."""
        full = pygame.Surface(self.size)
        p = self.pond
        lo, hi = p.shallow[1], p.deep[0]
        tip = (round(self.tip[0]), round(self.tip[1]))
        for d in range(self.max_d, 0, -1):
            s = P.CAUSTIC_SHALLOW + (P.CAUSTIC_DEEP - P.CAUSTIC_SHALLOW) * smooth((d - lo) / max(1.0, hi - lo))
            v = round(255 * s)
            pygame.draw.circle(full, (v, v, v), tip, d, 2)
        return full.subsurface(self.water).copy()

    def _build_caustic_layer(self, spec) -> tuple[pygame.Surface, int, int, float, float]:
        colour, wavelength, amp, spacing, vertical, sx, sy, width = spec
        ww, wh = self.water.size
        period_along = wavelength
        period_across = spacing * P.CAUSTIC_PHASES
        along, across = (wh, ww) if vertical else (ww, wh)
        size_along, size_across = along + period_along, across + period_across
        surf = pygame.Surface((size_across, size_along) if vertical else (size_along, size_across))
        surf.fill((0, 0, 0))
        step = P.CAUSTIC_STEP_PX
        k = 0
        c = -spacing
        while c < size_across + spacing:
            phase = (k % P.CAUSTIC_PHASES) * 2 * math.pi / P.CAUSTIC_PHASES
            pts = []
            for u in range(0, size_along + step, step):
                v = c + amp * math.sin(2 * math.pi * u / wavelength + phase)
                pts.append((v, u) if vertical else (u, v))
            if width == 1:
                pygame.draw.aalines(surf, colour, False, pts)
            else:
                pygame.draw.lines(surf, colour, False, pts, width)
            c += spacing
            k += 1
        px, py = (period_across, period_along) if vertical else (period_along, period_across)
        return surf, px, py, sx, sy

    # ------------------------------------------------------------------ shore
    def outline(self, offset: float) -> list[tuple[float, float]]:
        """The water's edge: a rounded rect with a wobbly bank, pushed out by `offset`."""
        r = self.water
        rad = P.SHORE_CORNER_R
        L, T, R, B = r.left, r.top, r.right, r.bottom
        pts = []
        step = P.SHORE_SAMPLE_PX
        # corners: (centre, start angle) going clockwise from the top-left
        segs = [
            ((L + rad, T), (R - rad, T), (0, -1)),
            ((R - rad, T + rad), -90, None),
            ((R, T + rad), (R, B - rad), (1, 0)),
            ((R - rad, B - rad), 0, None),
            ((R - rad, B), (L + rad, B), (0, 1)),
            ((L + rad, B - rad), 90, None),
            ((L, B - rad), (L, T + rad), (-1, 0)),
            ((L + rad, T + rad), 180, None),
        ]
        for a, b, n in segs:
            if n is None:  # quarter arc
                cx, cy = a
                arc_len = math.pi / 2 * rad
                count = max(2, int(arc_len / step))
                for i in range(count):
                    ang = math.radians(b + 90 * i / count)
                    nx, ny = math.cos(ang), math.sin(ang)
                    pts.append((cx + nx * rad, cy + ny * rad, nx, ny))
            else:
                (x0, y0), (x1, y1) = a, b
                length = math.hypot(x1 - x0, y1 - y0)
                count = max(1, int(length / step))
                for i in range(count):
                    t = i / count
                    pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, n[0], n[1]))
        if not hasattr(self, "_wobble"):
            rng = random.Random(P.ART_SEED + 1)
            p1, p2 = rng.uniform(0, 6.3), rng.uniform(0, 6.3)
            lo, hi = P.SHORE_WOBBLE_PX
            self._wobble = [
                lo + (hi - lo) * (0.5 + 0.3 * math.sin(i * 0.21 + p1) + 0.2 * math.sin(i * 0.57 + p2))
                * rng.uniform(0.85, 1.0)
                for i in range(len(pts))
            ]
        return [(x + nx * (wob + offset), y + ny * (wob + offset))
                for (x, y, nx, ny), wob in zip(pts, self._wobble)]

    def _edge_point(self, edge: str, frac: float, inset: float) -> tuple[float, float, float]:
        """A point on the water rect's edge, moved `inset` px into the water; plus the outward angle."""
        r = self.water
        if edge == "bottom":
            return r.left + r.width * frac, r.bottom - inset, math.pi / 2
        if edge == "top":
            return r.left + r.width * frac, r.top + inset, -math.pi / 2
        if edge == "left":
            return r.left + inset, r.top + r.height * frac, math.pi
        return r.right - inset, r.top + r.height * frac, 0.0

    def _build_overlay(self) -> list[tuple[pygame.Surface, tuple[int, int], bool]]:
        w, h = self.size
        rng = self.rng
        ov = pygame.Surface(self.size, pygame.SRCALPHA)
        ov.fill((*P.GRASS, 255))
        for _ in range(P.GRASS_SPECKLES):
            col = rng.choice((P.GRASS_LIGHT, P.GRASS_DARK))
            pygame.draw.circle(ov, (*col, 255), (rng.randrange(w), rng.randrange(h)), rng.choice((1, 1, 2)))
        for _ in range(P.GRASS_TUFTS):
            x, y = rng.randrange(w), rng.randrange(h)
            s = rng.uniform(*P.GRASS_TUFT_PX)
            col = (*rng.choice((P.GRASS_DARK, P.GRASS_LIGHT, P.REED)), 255)
            for ang in (-0.5, 0.0, 0.5):
                pygame.draw.line(ov, col, (x, y), (x + math.sin(ang) * s, y - math.cos(ang) * s), 1)

        pygame.draw.polygon(ov, (*P.SHORE_SAND, 255), self.outline(P.SHORE_RIM_PX))
        for inset, alpha in P.SHORE_SHADE:
            pygame.draw.polygon(ov, (0, 0, 0, alpha), self.outline(-inset))
        pygame.draw.lines(ov, P.SHORE_FOAM, True, self.outline(0), 2)

        for edge, frac, radius, flower in P.LILY_PADS:
            x, y, _ = self._edge_point(edge, frac, P.LILY_INSET_PX)
            self._lily(ov, x, y, radius, rng.uniform(0, 360), flower)

        self._dock(ov)

        tiles = []
        t = P.OVERLAY_TILE
        for ty in range(0, h, t):
            for tx in range(0, w, t):
                rect = pygame.Rect(tx, ty, min(t, w - tx), min(t, h - ty))
                sub = ov.subsurface(rect)
                br = sub.get_bounding_rect(min_alpha=1)
                if br.width == 0 or br.height == 0:
                    continue
                piece = sub.subsurface(br).copy()
                opaque = pygame.mask.from_surface(piece, 254).count() == br.width * br.height
                tiles.append((piece, (tx + br.x, ty + br.y), opaque))
        return tiles

    def _lily(self, ov: pygame.Surface, x: float, y: float, r: float, rot_deg: float, flower: bool) -> None:
        sh = P.DOCK_SHADOW_PX // 3
        pygame.draw.circle(ov, P.LILY_SHADOW, (x + sh, y + sh), r)
        notch = math.radians(P.LILY_NOTCH_DEG) / 2
        rot = math.radians(rot_deg)
        pts = [(x, y)]
        n = 24
        for i in range(n + 1):
            a = rot + notch + (2 * math.pi - 2 * notch) * i / n
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        pygame.draw.polygon(ov, (*P.LILY, 255), pts)
        pygame.draw.lines(ov, (*P.LILY_EDGE, 255), False, pts[1:], 2)
        for i in range(1, 6):
            a = rot + notch + (2 * math.pi - 2 * notch) * i / 6
            pygame.draw.line(ov, (*P.LILY_VEIN, 255), (x, y), (x + math.cos(a) * r * 0.8, y + math.sin(a) * r * 0.8))
        if flower:
            fx, fy = x - r * 0.25, y + r * 0.1
            pr = max(3.0, r * 0.22)
            for i in range(6):
                a = rot + i * math.pi / 3
                pygame.draw.circle(ov, (*P.LILY_FLOWER, 255), (fx + math.cos(a) * pr, fy + math.sin(a) * pr), pr)
            pygame.draw.circle(ov, (*P.LILY_FLOWER_CENTRE, 255), (fx, fy), pr * 0.8)

    def dock_rect(self) -> pygame.Rect:
        top = self.water.bottom - P.DOCK_INTO_WATER
        return pygame.Rect(round(self.tip[0] - P.DOCK_HALF_W), top, 2 * P.DOCK_HALF_W, self.size[1] - top)

    def _dock(self, ov: pygame.Surface) -> None:
        rng = self.rng
        d = self.dock_rect()
        shadow = d.move(P.DOCK_SHADOW_PX, P.DOCK_SHADOW_PX // 2)
        ov.set_clip(pygame.Rect(0, 0, self.size[0], self.water.bottom))  # only on the water
        pygame.draw.rect(ov, P.DOCK_SHADOW, shadow)
        ov.set_clip(None)
        pygame.draw.rect(ov, (*P.DOCK_GAP, 255), d)
        y = d.top
        while y < d.bottom:
            jitter = rng.randint(-P.DOCK_PLANK_JITTER, P.DOCK_PLANK_JITTER)
            col = tuple(max(0, min(255, c + jitter)) for c in P.DOCK)
            plank = pygame.Rect(d.left, y + 1, d.width, P.DOCK_PLANK_H - 2)
            pygame.draw.rect(ov, (*col, 255), plank)
            pygame.draw.line(ov, (*P.DOCK_LIGHT, 255), plank.topleft, (plank.right - 1, plank.top))
            for _ in range(2):
                gx = rng.randint(plank.left + 6, plank.right - 30)
                gy = rng.randint(plank.top + 3, plank.bottom - 3)
                pygame.draw.line(ov, (*P.DOCK_GRAIN, 255), (gx, gy), (gx + rng.randint(12, 26), gy))
            for nx in (d.left + P.DOCK_RAIL_W + 4, d.right - P.DOCK_RAIL_W - 5):
                pygame.draw.circle(ov, (*P.DOCK_NAIL, 255), (nx, plank.centery), 1)
            y += P.DOCK_PLANK_H
        for rx in (d.left, d.right - P.DOCK_RAIL_W):
            pygame.draw.rect(ov, (*P.DOCK_DARK, 255), (rx, d.top, P.DOCK_RAIL_W, d.height))
        for px in (d.left, d.right):
            pygame.draw.circle(ov, (*P.DOCK_DARK, 255), (px, d.top + P.DOCK_POST_R), P.DOCK_POST_R)
            pygame.draw.circle(ov, (*P.DOCK_POST_TOP, 255), (px, d.top + P.DOCK_POST_R), P.DOCK_POST_R - 3)
            pygame.draw.circle(ov, (*P.DOCK_DARK, 255), (px, d.top + P.DOCK_POST_R), P.DOCK_POST_R - 6, 1)

    # ------------------------------------------------------------------ reeds, glints
    def _build_reeds(self) -> list[tuple]:
        rng = self.rng
        reeds = []
        for edge, frac in P.REED_CLUMPS:
            x, y, out = self._edge_point(edge, frac, -P.SHORE_WOBBLE_PX[1])
            for _ in range(rng.randint(*P.REED_PER_CLUMP)):
                bx = x + rng.uniform(-10, 10) * abs(math.sin(out)) + rng.uniform(-4, 4)
                by = y + rng.uniform(-10, 10) * abs(math.cos(out)) + rng.uniform(-4, 4)
                # lean back over the water: the opposite of the outward direction
                lean = out + math.pi + math.radians(rng.uniform(-P.REED_SPREAD_DEG, P.REED_SPREAD_DEG))
                reeds.append((bx, by, lean, rng.uniform(*P.REED_LEN_PX), rng.uniform(0, 6.3),
                              rng.uniform(*P.REED_SWAY_RAD_S), rng.random() < P.REED_HEAD_CHANCE,
                              rng.choice((P.REED, P.REED_LIGHT, P.BANK_DARK))))
        return reeds

    def _build_glints(self) -> dict[int, list[pygame.Surface]]:
        sprites = {}
        for size in P.GLINT_SIZES:
            levels = []
            for lv in range(1, P.GLINT_LEVELS + 1):
                k = lv / P.GLINT_LEVELS
                s = pygame.Surface((2 * size + 1, 2 * size + 1))
                s.fill((0, 0, 0))
                col = tuple(round(c * k) for c in P.GLINT_COLOUR)
                dim = tuple(round(c * k * 0.45) for c in P.GLINT_COLOUR)
                pygame.draw.line(s, dim, (0, size), (2 * size, size))
                pygame.draw.line(s, dim, (size, 0), (size, 2 * size))
                pygame.draw.line(s, col, (size - size // 2, size), (size + size // 2, size))
                pygame.draw.line(s, col, (size, size - size // 2), (size, size + size // 2))
                s.set_at((size, size), tuple(min(255, round(c * k * 1.2)) for c in P.GLINT_COLOUR))
                levels.append(s)
            sprites[size] = levels
        return sprites


class PondArt:
    """Per-view pond renderer. The heavy static layers are shared between views."""

    def __init__(self, pond: PondConfig, size: tuple[int, int]) -> None:
        key = (pond, size)
        if key not in _BASE_CACHE:
            _BASE_CACHE[key] = _PondBase(pond, size)
        self.base = _BASE_CACHE[key]
        self.water = self.base.water
        self.rng = random.Random(P.ART_SEED + 2)
        self.glints: list[list] = []  # [x, y, age, life, size]
        self._ready = False
        self.background = self.base.background
        self.caustics = self.base.caustics
        self.mask = self.base.mask
        self.overlay = self.base.overlay
        self.glint_sprites = self.base.glint_sprites
        self.scratch = pygame.Surface(self.water.size)
        self._shore_blits = [(s, pos) for s, pos, _ in self.overlay]

    def colour_at(self, x: float, y: float) -> tuple[int, ...]:
        return self.base.colour_at(x, y)

    def dock_rect(self) -> pygame.Rect:
        return self.base.dock_rect()

    def prepare(self) -> None:
        """Convert the layers to the display format once a display exists (fast blits)."""
        if self._ready or pygame.display.get_surface() is None:
            return
        self._ready = True
        self.background = self.background.convert()
        self.caustics = [(s.convert(), px, py, sx, sy) for s, px, py, sx, sy in self.caustics]
        self.mask = self.mask.convert()
        self.scratch = self.scratch.convert()
        self.overlay = [(s.convert() if opaque else s.convert_alpha(), pos, opaque)
                        for s, pos, opaque in self.overlay]
        self._shore_blits = [(s, pos) for s, pos, _ in self.overlay]
        self.glint_sprites = {k: [s.convert() for s in v] for k, v in self.glint_sprites.items()}

    # ------------------------------------------------------------------ per frame
    def update(self, dt: float) -> None:
        b = self.base
        for g in self.glints:
            g[2] += dt
        self.glints = [g for g in self.glints if g[2] < g[3]]
        tries = 0
        while len(self.glints) < P.GLINT_COUNT and tries < P.GLINT_COUNT:
            tries += 1
            x = self.rng.uniform(self.water.left, self.water.right)
            y = self.rng.uniform(self.water.top, self.water.bottom)
            if math.hypot(x - b.tip[0], y - b.tip[1]) < P.GLINT_DOCK_CLEAR_PX:
                continue
            self.glints.append([x, y, 0.0, self.rng.uniform(*P.GLINT_LIFE_S), self.rng.choice(P.GLINT_SIZES)])

    def draw_water(self, screen: pygame.Surface, t: float) -> None:
        screen.blit(self.background, (0, 0))
        ww, wh = self.water.size
        sc = self.scratch
        for i, (surf, px, py, sx, sy) in enumerate(self.caustics):
            area = pygame.Rect(round((sx * t) % px), round((sy * t) % py), ww, wh)
            sc.blit(surf, (0, 0), area, special_flags=0 if i == 0 else pygame.BLEND_RGB_ADD)
        sc.blit(self.mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        screen.blit(sc, self.water.topleft, special_flags=pygame.BLEND_RGB_ADD)

    def draw_glints(self, screen: pygame.Surface) -> None:
        for x, y, age, life, size in self.glints:
            k = math.sin(math.pi * age / life)
            lv = min(P.GLINT_LEVELS - 1, int(k * P.GLINT_LEVELS))
            spr = self.glint_sprites[size][lv]
            screen.blit(spr, (round(x) - size, round(y) - size), special_flags=pygame.BLEND_RGB_ADD)

    def draw_shore(self, screen: pygame.Surface) -> None:
        screen.fblits(self._shore_blits)

    def draw_reeds(self, screen: pygame.Surface, t: float) -> None:
        sway = math.radians(P.REED_SWAY_DEG)
        for bx, by, lean, length, phase, speed, head, col in self.base.reeds:
            s = math.sin(t * speed + phase) * sway
            pts = [(bx, by)]
            x, y = bx, by
            seg = length / 3
            for i in range(1, 4):
                a = lean + s * i * i / 9 * 3
                x += math.cos(a) * seg
                y += math.sin(a) * seg
                pts.append((x, y))
            pygame.draw.lines(screen, P.REED_OUTLINE, False, pts, P.REED_WIDTH + 1)
            pygame.draw.lines(screen, col, False, pts, P.REED_WIDTH - 1)
            if head:
                a = lean + s * 3
                hx, hy = pts[-2]
                pygame.draw.line(screen, P.REED_HEAD, (hx, hy),
                                 (hx + math.cos(a) * seg * 0.8, hy + math.sin(a) * seg * 0.8), P.REED_WIDTH + 2)
