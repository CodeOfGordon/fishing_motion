"""Short-lived effects: ripple rings, splash droplets, screen shake, the hook flash
and pop-up text. Counts are capped so a busy moment can't slow the frame."""
from __future__ import annotations

import math
import random
from typing import Callable

import pygame

from fishing.render import palette as P
from fishing.render.pond import mix

DROP_SPEED_MIN = 0.3  # droplets leave at this to 1x the splash's ground speed
POP_FROM = 0.6  # pop-up text grows from this scale...
POP_OVERSHOOT = 0.25  # ...overshooting by this much...
FADE_FROM = 0.6  # ...and fades out over the last 40% of its life


class Effects:
    def __init__(self, water_colour: Callable[[float, float], tuple[int, ...]], seed: int = P.ART_SEED,
                 screen_w: int | None = None) -> None:
        self.water_colour = water_colour
        self.screen_w = screen_w  # floaters are kept inside the sides when known
        self.rng = random.Random(seed)
        self.ripples: list[list] = []  # [x, y, age, r0, r1, life, width, base colour]
        self.drops: list[list] = []  # [x, y, z, vx, vy, vz, r]
        self.floaters: list[list] = []  # [surface, shadow, x, y, age, highest centre y]
        self.shake_amp = 0.0
        self.shake_left = 0.0
        self.flash = 0.0
        self.hit_stop = 0.0

    # ------------------------------------------------------------------ spawning
    def ripple(self, x: float, y: float, kind: str, scale: float = 1.0) -> None:
        r0, r1, life, width = P.RIPPLES[kind]
        if len(self.ripples) >= P.RIPPLE_MAX:
            self.ripples.pop(0)
        self.ripples.append([x, y, 0.0, r0 * scale, r1 * scale, life, width, self.water_colour(x, y)])

    def splash(self, x: float, y: float, kind: str) -> None:
        count, ground, up, radius = P.SPLASHES[kind]
        rng = self.rng
        for _ in range(count):
            if len(self.drops) >= P.DROP_MAX:
                self.drops.pop(0)
            a = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(DROP_SPEED_MIN, 1.0) * ground
            self.drops.append([x, y, 0.0, math.cos(a) * sp, math.sin(a) * sp, rng.uniform(*up),
                               rng.uniform(*radius)])

    def shake(self, px: float) -> None:
        self.shake_amp = max(self.shake_amp if self.shake_left > 0 else 0.0, px)
        self.shake_left = P.SHAKE_S

    def start_flash(self, hit_stop_s: float) -> None:
        self.flash = 1.0
        self.hit_stop = hit_stop_s

    def floater(self, font: pygame.font.Font, text: str, x: float, y: float, colour,
                min_y: float | None = None) -> None:
        """Pop-up text centred at (x, y). It rises, but its centre never goes above min_y
        (default: just under the HUD band, POPUP_MIN_TOP)."""
        if len(self.floaters) >= P.FLOATER_MAX:
            self.floaters.pop(0)
        img = font.render(text, True, colour)
        w, h = img.get_size()
        if min_y is None:
            min_y = P.POPUP_MIN_TOP + h / 2
        if self.screen_w is not None:
            lo, hi = P.POPUP_SIDE_PX + w / 2, self.screen_w - P.POPUP_SIDE_PX - w / 2
            x = max(lo, min(hi, x)) if lo <= hi else self.screen_w / 2
        self.floaters.append([img, font.render(text, True, P.TEXT_SHADOW), x, max(y, min_y), 0.0, min_y])

    def clear(self) -> None:
        self.ripples.clear()
        self.drops.clear()
        self.floaters.clear()

    # ------------------------------------------------------------------ ticking
    def update(self, dt: float) -> None:
        """Advance everything. During the hit-stop only the flash keeps fading."""
        self.flash = max(0.0, self.flash - dt / P.FLASH_S)
        if self.hit_stop > 0:
            self.hit_stop -= dt
            return
        self.shake_left = max(0.0, self.shake_left - dt)
        for r in self.ripples:
            r[2] += dt
        self.ripples = [r for r in self.ripples if r[2] < r[5]]
        landed = []
        for d in self.drops:
            d[0] += d[3] * dt
            d[1] += d[4] * dt
            d[5] -= P.DROP_GRAVITY * dt
            d[2] += d[5] * dt
            if d[2] <= 0:
                landed.append(d)
        if landed:
            self.drops = [d for d in self.drops if d[2] > 0]
            for d in landed:
                if self.rng.random() < P.DROP_RIPPLE_CHANCE:
                    self.ripple(d[0], d[1], "drop")
        for f in self.floaters:
            f[4] += dt
            f[3] = max(f[3] - P.FLOATER_RISE * dt, f[5])
        self.floaters = [f for f in self.floaters if f[4] < P.FLOATER_LIFE_S]

    @property
    def frozen(self) -> bool:
        return self.hit_stop > 0

    def shake_offset(self) -> tuple[int, int]:
        if self.shake_left <= 0:
            return 0, 0
        k = self.shake_amp * self.shake_left / P.SHAKE_S
        return round(self.rng.uniform(-k, k)), round(self.rng.uniform(-k, k))

    # ------------------------------------------------------------------ drawing
    def draw_ripples(self, screen: pygame.Surface) -> None:
        for x, y, age, r0, r1, life, width, base in self.ripples:
            k = age / life
            r = r0 + (r1 - r0) * (1 - (1 - k) ** 2)  # fast, then slowing
            col = mix(P.RIPPLE_COLOUR, base, k)
            if r >= 1:
                pygame.draw.circle(screen, col, (round(x), round(y)), round(r), max(1, round(width * (1 - k * 0.5))))

    def draw_drops(self, screen: pygame.Surface) -> None:
        for x, y, z, _vx, _vy, _vz, r in self.drops:
            pygame.draw.circle(screen, P.DROP_SHADOW, (round(x), round(y)), max(1, round(r * 0.6)))
            pygame.draw.circle(screen, P.DROP_COLOUR, (round(x), round(y - z)), max(1, round(r)))

    def draw_floaters(self, screen: pygame.Surface, dx: int = 0, dy: int = 0) -> None:
        for surf, shadow, x, y, age, _ in self.floaters:
            fade = 1.0 - max(0.0, (age - P.FLOATER_LIFE_S * FADE_FROM) / (P.FLOATER_LIFE_S * (1 - FADE_FROM)))
            pop = min(1.0, age / P.FLOATER_POP_S)
            scale = POP_FROM + (1 - POP_FROM) * pop + POP_OVERSHOOT * math.sin(math.pi * pop)
            if abs(scale - 1.0) > 0.02:
                surf = pygame.transform.smoothscale_by(surf, scale)
                shadow = pygame.transform.smoothscale_by(shadow, scale)
            alpha = round(255 * fade)
            surf.set_alpha(alpha)
            shadow.set_alpha(alpha)
            rect = surf.get_rect(center=(round(x) + dx, round(y) + dy))
            screen.blit(shadow, rect.move(P.HUD_SHADOW_PX, P.HUD_SHADOW_PX))
            screen.blit(surf, rect)

    def draw_flash(self, screen: pygame.Surface) -> None:
        if self.flash > 0:
            v = round(P.FLASH_LEVEL * self.flash)
            screen.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
