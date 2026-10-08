"""Reel-fight maths: tension, fish runs, stamina, snap and slack. Pure logic."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from fishing.config import FightConfig, Species

LAND = "land"
SNAP = "snap"
SLACK = "slack"
LINE_OUT = "line_out"


@dataclass
class Fight:
    spec: Species
    dist: float  # px from the rod tip
    angle: float  # radians from straight ahead (up the screen); + is to the right
    strength_mult: float = 1.0
    tension: float = 0.0
    stamina: float = 1.0
    strain: float = 0.0
    slack_for: float = 0.0
    running: bool = True
    phase_left: float = 0.0
    run_dir: int = 1  # +1: the fish runs to the right
    elapsed: float = 0.0
    pull: float = 0.0
    side_pressure: bool = False
    new_run: bool = False

    @property
    def is_junk(self) -> bool:
        return self.spec.kind == "junk"


def start_fight(
    spec: Species, dist: float, angle: float, cfg: FightConfig, rng: random.Random,
    strength_mult: float = 1.0,
) -> Fight:
    f = Fight(spec, dist, angle, strength_mult=strength_mult)
    if f.is_junk:
        f.running = False
    else:
        f.phase_left = cfg.first_run_s
        f.run_dir = rng.choice((-1, 1))
        f.new_run = True
    return f


def step_fight(
    f: Fight, dt: float, reel: float, tilt: float, cfg: FightConfig, rng: random.Random,
    land_radius: float, snap_strain_s: float,
) -> str | None:
    """Advance one step. Returns LAND, SNAP, SLACK, LINE_OUT or None."""
    f.elapsed += dt
    f.new_run = False
    base = f.spec.strength * f.strength_mult
    if f.is_junk:
        pull = base
    else:
        f.phase_left -= dt
        if f.phase_left <= 0:
            if f.running:
                f.running = False
                f.phase_left = rng.uniform(*cfg.rest_s)
            elif f.stamina >= cfg.no_runs_below_stamina:
                f.running = True
                f.phase_left = rng.uniform(*cfg.run_s)
                f.run_dir = rng.choice((-1, 1))
                f.new_run = True
            else:
                f.phase_left = rng.uniform(*cfg.rest_s)
        floor = cfg.pull_stamina_floor
        pull = base * (floor + (1 - floor) * f.stamina) * (1.0 if f.running else cfg.rest_pull)

    f.side_pressure = (
        not f.is_junk and f.running and tilt * f.run_dir <= -cfg.side_pressure_min_tilt
    )
    if f.side_pressure:
        pull *= 1 - cfg.side_pressure_pull_cut * min(1.0, abs(tilt))
    f.pull = pull

    target = reel * (cfg.tension_reel + cfg.tension_pull * pull)
    tau = cfg.tau_up_s if target > f.tension else cfg.tau_down_s
    f.tension += (target - f.tension) * (1 - math.exp(-dt / tau))

    f.dist += (pull * f.spec.run_speed - reel * cfg.reel_speed) * dt
    if f.running:
        limit = math.radians(cfg.lateral_max_deg)
        f.angle = max(-limit, min(limit, f.angle + f.run_dir * cfg.lateral_rate * pull * dt))

    if not f.is_junk:
        drain = (cfg.stamina_base + cfg.stamina_tension * f.tension) / f.spec.stamina_s
        if f.side_pressure:
            drain *= cfg.side_pressure_drain_mult
        f.stamina = max(0.0, f.stamina - drain * dt)

    if f.tension >= 1.0:
        f.strain += dt
    else:
        f.strain = max(0.0, f.strain - cfg.strain_recover * dt)
    f.slack_for = f.slack_for + dt if f.tension < cfg.slack_tension else 0.0

    if f.dist <= land_radius:
        return LAND
    if f.strain >= snap_strain_s:
        return SNAP
    if f.slack_for >= cfg.slack_s:
        return SLACK
    if f.dist >= cfg.line_out:
        return LINE_OUT
    return None
