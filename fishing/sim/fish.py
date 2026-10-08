"""Fish in the pond: wandering, fleeing, leaving. Pure logic (no pygame)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from fishing.config import FishAIConfig, PondConfig, Species

WANDER = "wander"
COMMITTED = "committed"  # swimming to the lure
ATTACHED = "attached"  # nibbling, biting or hooked: follows the lure
FLEE = "flee"
LEAVING = "leaving"


def angle_diff(a: float, b: float) -> float:
    """Smallest signed difference a - b, in (-pi, pi]."""
    return (a - b + math.pi) % (2 * math.pi) - math.pi


@dataclass
class Fish:
    id: int
    spec: Species
    x: float
    y: float
    heading: float  # radians, atan2 convention on screen axes (0 = right, +pi/2 = down)
    band: tuple[float, float]  # distance band from the rod tip it likes to stay in
    size_cm: float
    size_frac: float
    born_s: float
    lifetime_s: float
    speed: float = 0.0
    mode: str = WANDER
    mode_left: float = 0.0
    cooldown_until: float = 0.0
    curious_until: float = 0.0
    alpha: float = 0.0  # fade in/out, 0..1
    turn_rate: float = 0.0
    flee_from: tuple[float, float] = (0.0, 0.0)
    gone: bool = False

    @property
    def is_static(self) -> bool:
        return self.spec.kind == "junk"

    def dist_to(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, self.y - y)

    def flee(self, from_xy: tuple[float, float], until_s: float, cfg: FishAIConfig) -> None:
        if self.is_static:
            return
        self.mode = FLEE
        self.mode_left = cfg.flee_s
        self.flee_from = from_xy
        self.cooldown_until = max(self.cooldown_until, until_s)

    def leave(self) -> None:
        if not self.is_static and self.mode in (WANDER, FLEE):
            self.mode = LEAVING


def _steer(heading: float, desired: float, max_turn: float) -> float:
    d = angle_diff(desired, heading)
    return heading + max(-max_turn, min(max_turn, d))


def update_fish(
    f: Fish, dt: float, pond: PondConfig, cfg: FishAIConfig, rng: random.Random
) -> None:
    """Move a free-swimming fish (not COMMITTED or ATTACHED; the round moves those)."""
    if f.is_static:
        f.alpha = min(1.0, f.alpha + dt / cfg.fade_s)
        return
    if f.mode == LEAVING:
        f.alpha -= dt / cfg.fade_s
        if f.alpha <= 0:
            f.gone = True
            return
    elif f.mode in (WANDER, FLEE):
        f.alpha = min(1.0, f.alpha + dt / cfg.fade_s)

    tip_x, tip_y = pond.rod_tip
    max_turn = cfg.steer_turn_mult * cfg.wander_turn_rate * dt
    if f.mode == FLEE:
        away = math.atan2(f.y - f.flee_from[1], f.x - f.flee_from[0])
        f.heading = _steer(f.heading, away, cfg.flee_turn_mult * max_turn)
        f.speed = f.spec.cruise * cfg.flee_speed_mult
        f.mode_left -= dt
        if f.mode_left <= 0:
            f.mode = WANDER
    elif f.mode in (WANDER, LEAVING):
        f.turn_rate += rng.uniform(-1.0, 1.0) * cfg.wander_turn_rate * cfg.wander_noise * dt
        f.turn_rate = max(-cfg.wander_turn_rate, min(cfg.wander_turn_rate, f.turn_rate))
        f.heading += f.turn_rate * dt
        f.speed = f.spec.cruise * (1 - cfg.cruise_jitter * (0.5 + 0.5 * math.sin(f.born_s + f.id)))
        r = math.hypot(f.x - tip_x, f.y - tip_y)
        to_tip = math.atan2(tip_y - f.y, tip_x - f.x)
        if f.mode == LEAVING:
            side = pond.water_left if f.x < (pond.water_left + pond.water_right) / 2 else pond.water_right
            f.heading = _steer(f.heading, 0.0 if side > f.x else math.pi, max_turn)
        elif r < f.band[0]:
            f.heading = _steer(f.heading, to_tip + math.pi, max_turn)
        elif r > f.band[1]:
            f.heading = _steer(f.heading, to_tip, max_turn)
        m = cfg.edge_margin
        if not (pond.water_left + m < f.x < pond.water_right - m
                and pond.water_top + m < f.y < pond.water_bottom - m) and f.mode != LEAVING:
            centre = ((pond.water_left + pond.water_right) / 2, (pond.water_top + pond.water_bottom) / 2)
            f.heading = _steer(f.heading, math.atan2(centre[1] - f.y, centre[0] - f.x), 2 * max_turn)

    f.x += math.cos(f.heading) * f.speed * dt
    f.y += math.sin(f.heading) * f.speed * dt
    if f.mode == LEAVING:
        if f.x < pond.water_left - cfg.leave_margin or f.x > pond.water_right + cfg.leave_margin:
            f.gone = True
    else:
        f.x = max(pond.water_left, min(pond.water_right, f.x))
        f.y = max(pond.water_top, min(pond.water_bottom, f.y))
