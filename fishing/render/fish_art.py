"""Fish shadows: translucent dark shapes with a wagging tail, rotated to their heading.

Sprites are cached per (shape, length, heading every 5 degrees, wag frame), so a frame
only blits. The real species colours appear only on the catch card (catch_card.py).
"""
from __future__ import annotations

import math
from typing import Callable

import pygame

from fishing.config import Tuning
from fishing.render import palette as P
from fishing.render.pond import smooth
from fishing.sim import round as R
from fishing.sim.fish import ATTACHED, angle_diff

TAU = 2 * math.pi
ANGLE_STEPS = round(360 / P.FISH_ANGLE_STEP_DEG)
BODY_POINTS = 20  # polygon points around a body ellipse
REAR_TAPER = 0.62  # the body's rear is this much narrower than its front
TAIL_ROOT = 0.92  # tail joins this far back (x half-length)
TAIL_SPREAD = 0.45  # half-height of the tail fan (x tail length)
TAIL_NOTCH = 0.7  # the tail's fork notch (x tail length)


def fish_length(size_cm: float) -> float:
    return P.FISH_LEN_BASE + P.FISH_LEN_PER_CM * size_cm


def _rot(points, ang: float, cx: float, cy: float, scale: float) -> list[tuple[float, float]]:
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + (x * ca - y * sa) * scale, cy + (x * sa + y * ca) * scale) for x, y in points]


def fish_outline(length: float, shape: str, wag: float) -> list[list[tuple[float, float]]]:
    """Polygons (body, tail, fins) of a fish facing +x, centred on its body, tail swung by wag -1..1."""
    wf, tf = P.FISH_SHAPES.get(shape, P.FISH_SHAPES["default"])
    half, w, tail = length / 2, length * wf / 2, length * tf
    swing = math.radians(P.FISH_WAG_DEG) * wag
    bend = math.sin(swing) * P.FISH_BEND * w * 2

    def bent(x: float, y: float) -> tuple[float, float]:
        if x < 0:
            y += bend * (x / half) ** 2
        return x, y

    body = []
    for k in range(BODY_POINTS):
        th = TAU * k / BODY_POINTS
        x = half * math.cos(th)
        taper = REAR_TAPER + (1 - REAR_TAPER) * (math.cos(th) + 1) / 2
        body.append(bent(x, w * math.sin(th) * taper))
    rx, ry = bent(-half * TAIL_ROOT, 0.0)
    ca, sa = math.cos(swing), math.sin(swing)
    tail_local = [(0.0, w * 0.3), (-tail, tail * TAIL_SPREAD), (-tail * TAIL_NOTCH, 0.0),
                  (-tail, -tail * TAIL_SPREAD), (0.0, -w * 0.3)]
    tail_pts = [(rx + x * ca - y * sa, ry + x * sa + y * ca) for x, y in tail_local]
    polys = [body, tail_pts]
    if shape != "bait_thief":
        for s in (1, -1):
            polys.append([(length * 0.16, s * w * 0.8), (-length * 0.02, s * w * 1.55),
                          (-length * 0.06, s * w * 0.8)])
    return polys


BOOT = [(-0.36, -0.62), (0.02, -0.62), (0.04, -0.08), (0.3, -0.02), (0.46, 0.06), (0.5, 0.2), (0.48, 0.28),
        (-0.36, 0.28), (-0.38, 0.12), (-0.33, 0.0)]  # side view, toe toward +x, shaft up (-y)


def boot_outline(length: float) -> list[list[tuple[float, float]]]:
    """An old boot lying on its side, centred."""
    return [[(x * length, y * length) for x, y in BOOT]]


class FishArt:
    def __init__(self, tuning: Tuning, on_turn: Callable[[float, float], None] | None = None) -> None:
        self.t = tuning
        self.on_turn = on_turn  # called with (x, y) when a fish turns sharply
        self.cache: dict[tuple, tuple[pygame.Surface, int]] = {}
        self.glow_cache: dict[int, list[pygame.Surface]] = {}
        self.phase: dict[int, float] = {}
        self.last_heading: dict[int, float] = {}
        self.turn_wait: dict[int, float] = {}
        self.nudge_age = math.inf  # time since the last nibble
        self._convert = False
        p = tuning.pond
        self._fade_from, self._fade_to = p.shallow[1], p.deep[0]

    # ------------------------------------------------------------------ sprites
    def _sprite(self, kind: str, shape: str, length: int, angle_idx: int, wag_idx: int,
                colour: tuple[int, int, int], core: int, edge: int) -> tuple[pygame.Surface, int]:
        key = (kind, shape, length, angle_idx, wag_idx, colour)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        if len(self.cache) >= P.FISH_CACHE_MAX:
            self.cache.clear()
        if kind == "boot":
            polys = boot_outline(length)
        else:
            wag = (wag_idx / (P.FISH_WAG_FRAMES - 1)) * 2 - 1
            polys = fish_outline(length, shape, wag)
        reach = max(math.hypot(x, y) for poly in polys for x, y in poly) * P.FISH_SHADOW_EDGE_GROW
        half = math.ceil(reach) + 2
        ss = P.FISH_SUPERSAMPLE
        big = pygame.Surface((2 * half * ss, 2 * half * ss), pygame.SRCALPHA)
        ang = math.radians(angle_idx * P.FISH_ANGLE_STEP_DEG)
        c = half * ss
        for poly in polys:
            pygame.draw.polygon(big, (*colour, edge), _rot(poly, ang, c, c, ss * P.FISH_SHADOW_EDGE_GROW))
        for poly in polys:
            pygame.draw.polygon(big, (*colour, core), _rot(poly, ang, c, c, ss))
        surf = pygame.transform.smoothscale(big, (2 * half, 2 * half))
        if self._convert:
            surf = surf.convert_alpha()
        self.cache[key] = (surf, half)
        return surf, half

    def _glow(self, length: int) -> list[pygame.Surface]:
        levels = self.glow_cache.get(length)
        if levels is not None:
            return levels
        radius = max(2, round(length * P.KOI_GLOW_RADIUS))
        levels = []
        for lv in range(1, P.KOI_GLOW_LEVELS + 1):
            k = lv / P.KOI_GLOW_LEVELS
            s = pygame.Surface((2 * radius, 2 * radius))
            s.fill((0, 0, 0))
            for r in range(radius, 0, -1):
                f = k * (1 - r / radius) ** 2
                pygame.draw.circle(s, tuple(round(c * f) for c in P.KOI_GLOW_COLOUR), (radius, radius), r)
            levels.append(s.convert() if self._convert else s)
        self.glow_cache[length] = levels
        return levels

    def prepare(self) -> None:
        if not self._convert and pygame.display.get_surface() is not None:
            self._convert = True
            self.cache.clear()
            self.glow_cache.clear()

    # ------------------------------------------------------------------ per frame
    def nibble(self) -> None:
        self.nudge_age = 0.0

    def depth_alpha(self, x: float, y: float) -> float:
        """Shadows get darker with depth: FISH_SHADOW_SHALLOW_K in the shallows, 1 in the deep."""
        tip = self.t.pond.rod_tip
        d = math.hypot(x - tip[0], y - tip[1])
        k = P.FISH_SHADOW_SHALLOW_K
        return k + (1 - k) * smooth((d - self._fade_from) / max(1.0, self._fade_to - self._fade_from))

    def _turn_check(self, fid: int, heading: float, x: float, y: float, dt: float) -> None:
        last = self.last_heading.get(fid)
        self.last_heading[fid] = heading
        wait = self.turn_wait.get(fid, 0.0) - dt
        self.turn_wait[fid] = wait
        if last is None or dt <= 0 or wait > 0 or self.on_turn is None:
            return
        if abs(angle_diff(heading, last)) / dt > P.FISH_TURN_RAD_S:
            self.turn_wait[fid] = P.FISH_TURN_GAP_S
            self.on_turn(x, y)

    def mouth_heading(self, rnd: R.Round, t: float) -> float | None:
        """The hooked fish's visual heading during a fight (None if not fighting)."""
        fight = rnd.fight if rnd.state == R.FIGHT else None
        if fight is None:
            return None
        tip = self.t.pond.rod_tip
        out = math.atan2(rnd.lure.y - tip[1], rnd.lure.x - tip[0])
        if fight.running:
            return out + fight.run_dir * math.radians(P.FIGHT_RUN_TURN_DEG)
        return out + math.radians(P.FIGHT_REST_WOBBLE_DEG) * math.sin(t * math.pi)

    def draw(self, screen: pygame.Surface, rnd: R.Round, t: float, dt: float,
             owner_offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw every fish. owner_offset shifts the fish on the lure (the bait thief's sideways drag)."""
        self.nudge_age += dt
        owner = rnd.lure.owner
        fight_heading = self.mouth_heading(rnd, t)
        live = set()
        junk = [f for f in rnd.fishes if f.spec.kind == "junk"]
        swimmers = [f for f in rnd.fishes if f.spec.kind != "junk"]
        for f in junk:  # on the bottom, under everything
            length = self._bucket(fish_length(f.size_cm) * P.BOOT_SCALE)
            x, y = f.x, f.y
            tilt_steps = P.BOOT_TILT_DEG // P.FISH_ANGLE_STEP_DEG
            ang_idx = ((f.id * 7) % (2 * tilt_steps + 1) - tilt_steps) % ANGLE_STEPS
            spr, half = self._sprite("boot", "boot", length, ang_idx, 0, P.BOOT_SHADOW, P.BOOT_ALPHA,
                                     P.BOOT_ALPHA // 2)
            spr.set_alpha(round(255 * max(0.0, min(1.0, f.alpha)) * self.depth_alpha(x, y)))
            screen.blit(spr, (round(x) - half, round(y) - half))
        for f in swimmers:
            live.add(f.id)
            length = self._bucket(fish_length(f.size_cm))
            heading, speed, wag_mult = f.heading, f.speed, 1.0
            attached = f.mode == ATTACHED and f.id == owner
            if attached and fight_heading is not None:
                heading = fight_heading
                if rnd.fight is not None and rnd.fight.running:
                    speed = f.spec.run_speed
                    wag_mult = P.FIGHT_RUN_WAG_MULT
            kind = f.spec.kind
            if kind == "trap":
                hz1, hz2 = P.TRAP_JITTER_HZ
                heading += math.radians(P.TRAP_JITTER_DEG) * math.sin(t * TAU * hz1 + f.id) * math.sin(t * TAU * hz2)
                wag_mult *= P.TRAP_WAG_MULT
            x, y = f.x, f.y
            if attached:
                self.last_heading.pop(f.id, None)  # the fight has its own ripples
            elif f.alpha >= 1.0:
                self._turn_check(f.id, f.heading, x, y, dt)
            if attached:  # the lure is in its mouth
                x += owner_offset[0]
                y += owner_offset[1]
                push = length * P.FISH_MOUTH
                if self.nudge_age < P.NIBBLE_TWITCH_S and rnd.state == R.NIBBLE:
                    push -= P.NIBBLE_NUDGE_PX * math.sin(math.pi * self.nudge_age / P.NIBBLE_TWITCH_S)
                x -= math.cos(heading) * push
                y -= math.sin(heading) * push
            ph = self.phase.get(f.id, f.id * 1.7) + TAU * (P.FISH_WAG_BASE_HZ + P.FISH_WAG_PER_PX * speed) * wag_mult * dt
            self.phase[f.id] = ph % TAU
            wag_idx = round((math.sin(ph) + 1) / 2 * (P.FISH_WAG_FRAMES - 1))
            ang_idx = round(math.degrees(heading) / P.FISH_ANGLE_STEP_DEG) % ANGLE_STEPS
            colour = P.KOI_SHADOW if kind == "special" else P.FISH_SHADOW
            spr, half = self._sprite("fish", f.spec.id if f.spec.id in P.FISH_SHAPES else "default",
                                     length, ang_idx, wag_idx, colour, P.FISH_SHADOW_ALPHA, P.FISH_SHADOW_EDGE_ALPHA)
            alpha = max(0.0, min(1.0, f.alpha))
            if kind == "special":
                glow = self._glow(length)
                pulse = 0.5 + 0.5 * math.sin(t * TAU * P.KOI_PULSE_HZ)
                lv = min(len(glow) - 1, int(pulse * alpha * len(glow)))
                g = glow[lv]
                screen.blit(g, (round(x) - g.get_width() // 2, round(y) - g.get_height() // 2),
                            special_flags=pygame.BLEND_RGB_ADD)
            spr.set_alpha(round(255 * alpha * self.depth_alpha(x, y)))  # sprites are shared: set, then blit at once
            screen.blit(spr, (round(x) - half, round(y) - half))
        for table in (self.phase, self.last_heading, self.turn_wait):
            for fid in [k for k in table if k not in live]:
                del table[fid]

    @staticmethod
    def _bucket(length: float) -> int:
        """Round a sprite length so similar fish share cached sprites."""
        b = P.FISH_LEN_BUCKET
        return max(b, int(round(length / b) * b))
