"""Scripted players for headless rounds (tuning, medals, tests). Pure logic."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from fishing.config import Tuning
from fishing.input.motion import CAST, HOOK_SET, MotionEvent, MotionState
from fishing.sim import round as R

DT = 1 / 60


@dataclass(frozen=True)
class Profile:
    name: str
    aimed: bool  # aim at a good fish (else random casts)
    retrieve: float  # reel rate while the lure drifts
    reaction_ms: tuple[float, float]  # mean, sd for hook-sets
    hooks_trap: float  # chance of (wrongly) hooking the trap fish
    fight_threshold: float  # ease off above this tension
    fight_ease: float  # reel rate while easing off
    uses_tilt: bool
    react_steps: int  # delay before reacting to tension changes


NOVICE = Profile("novice", False, 0.6, (450, 120), 0.7, 0.95, 0.0, False, 30)
SKILLED = Profile("skilled", True, 0.3, (330, 70), 0.1, 0.7, 0.3, True, 15)
PROFILES = {p.name: p for p in (NOVICE, SKILLED)}


class Bot:
    def __init__(self, profile: Profile, tuning: Tuning, seed: int) -> None:
        self.p = profile
        self.t = tuning
        self.rng = random.Random(seed)
        self.pending: list[MotionEvent] = []
        self.aim_tilt = 0.0
        self.reel_queue: list[float] = []
        self.planned_bite: int | None = None

    def _aim_at(self, rnd: R.Round) -> tuple[float, float] | None:
        """(tilt, strength) to land just in front of the best reachable fish."""
        c = self.t.cast
        tip = self.t.pond.rod_tip
        best = None
        for f in rnd.fishes:
            if f.is_static or f.spec.kind == "trap" or f.mode != "wander" or f.alpha < 1:
                continue
            value = f.spec.points * (self.t.scoring.bonus_mult if f.spec.id == rnd.bonus_species else 1)
            px = f.x + math.cos(f.heading) * 60
            py = f.y + math.sin(f.heading) * 60
            aim = math.atan2(px - tip[0], tip[1] - py)
            dist = math.hypot(px - tip[0], py - tip[1])
            strength = (dist - c.min_dist) / c.dist_per_strength
            if abs(math.degrees(aim)) > c.aim_max_deg or not 0 <= strength <= 1:
                continue
            if best is None or value > best[0]:
                best = (value, math.degrees(aim) / c.aim_max_deg, strength)
        return None if best is None else (best[1], best[2])

    def act(self, rnd: R.Round, host: float) -> tuple[float, float, list[MotionEvent]]:
        """Return (reel, tilt, events due now) for this step."""
        reel, tilt = 0.0, self.aim_tilt
        s = rnd.state
        if s == R.READY and not self.pending:
            in_ready = host - (rnd.state_since_ms + rnd.offset_ms)
            if in_ready > 700:
                plan = self._aim_at(rnd) if self.p.aimed else None
                if plan is None:
                    plan = (self.rng.uniform(-0.6, 0.6), self.rng.uniform(0.2, 1.0))
                self.aim_tilt, strength = plan
                tilt = self.aim_tilt
                # hold the aim for a moment, then flick
                self.pending.append(MotionEvent(CAST, host + 250, strength))
        elif s in (R.DRIFT, R.APPROACH):
            reel, tilt = self.p.retrieve, 0.0
            self.aim_tilt = 0.0
        elif s == R.NIBBLE:
            reel = 0.0
        elif s == R.BITE and not self.pending and self.planned_bite != rnd.bite_id:
            self.planned_bite = rnd.bite_id
            owner = rnd.owner
            trap = owner is not None and owner.spec.kind == "trap"
            if not trap or self.rng.random() < self.p.hooks_trap:
                delay = max(120.0, self.rng.gauss(*self.p.reaction_ms))
                self.pending.append(MotionEvent(HOOK_SET, rnd.bite_start_ms + rnd.offset_ms + delay, 1.0))
        elif s == R.FIGHT and rnd.fight is not None:
            f = rnd.fight
            want = 1.0 if f.tension < self.p.fight_threshold else self.p.fight_ease
            self.reel_queue.append(want)
            reel = self.reel_queue.pop(0) if len(self.reel_queue) > self.p.react_steps else 1.0
            tilt = -f.run_dir if (self.p.uses_tilt and f.running) else 0.0
        if s not in (R.FIGHT, R.HOOKED):
            self.reel_queue.clear()
        due = [e for e in self.pending if e.t_ms <= host]
        self.pending = [e for e in self.pending if e.t_ms > host]
        return reel, tilt, due


def play_round(tuning: Tuning, profile: Profile, seed: int, **round_kw) -> R.Round:
    """Play one full round headless and return it."""
    rnd = R.Round(tuning, seed=seed, **round_kw)
    bot = Bot(profile, tuning, seed + 1)
    host = 1_000_000.0
    limit = int((tuning.round.length_s + tuning.round.overtime_cap_s + 30) / DT)
    for _ in range(limit):
        if rnd.finished:
            break
        reel, tilt, events = bot.act(rnd, host)
        rnd.step(DT, MotionState(host, reel, tilt), events, host)
        host += DT * 1000
    return rnd
