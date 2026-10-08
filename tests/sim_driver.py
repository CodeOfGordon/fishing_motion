"""Helpers that drive a Round with scripted input on a fake host clock."""
from __future__ import annotations

import math
import random

from fishing.input.motion import MotionEvent, MotionState
from fishing.sim import round as R
from fishing.sim.fish import ATTACHED, WANDER

DT = 1 / 60
STEP_MS = DT * 1000


class Driver:
    def __init__(self, tuning, seed: int = 1, **kw) -> None:
        self.t = tuning
        self.r = R.Round(tuning, seed=seed, **kw)
        self.host = 100_000.0
        self.reel = 0.0
        self.tilt = 0.0
        self.stale = False
        self.log = []

    # -- stepping -----------------------------------------------------------
    def step(self, n: int = 1, events=()) -> list:
        out = []
        for i in range(n):
            st = MotionState(self.host, self.reel, self.tilt)
            out += self.r.step(DT, st, list(events) if i == 0 else [], self.host, self.stale)
            self.host += STEP_MS
        self.log += out
        return out

    def run_until(self, pred, max_steps: int = 20_000) -> None:
        for _ in range(max_steps):
            if pred():
                return
            self.step()
        raise AssertionError(f"condition never met; state={self.r.state}")

    def ev(self, kind: str, strength: float = 1.0, ago_ms: float = 0.0) -> MotionEvent:
        return MotionEvent(kind, self.host - ago_ms, strength)

    def kinds(self, kind: str) -> list:
        return [e for e in self.log if e.kind == kind]

    # -- situations -----------------------------------------------------------
    def clear_pond(self) -> None:
        self.r.fishes = []

    def wait_armed(self) -> None:
        self.step(int(self.t.cast.arm_delay_s / DT) + 2)

    def cast(self, strength: float = 0.5) -> None:
        self.wait_armed()
        self.step(1, [self.ev("cast", strength)])
        self.run_until(lambda: self.r.state != R.CASTING)

    def nibbling(self, species: str = "perch") -> object:
        """Cast, then put a fish of `species` on the lure, nibbling."""
        self.clear_pond()
        self.cast(0.5)
        spec = self.t.species_by_id(species)
        fish = self.r.spawner.make(spec, self.r.now_s)
        fish.alpha = 1.0
        fish.x, fish.y = self.r.lure.x, self.r.lure.y
        self.r.fishes.append(fish)
        self.r.lure.owner = fish.id
        self.r._begin_nibbles(fish)
        return fish

    def biting(self, species: str = "perch") -> object:
        fish = self.nibbling(species)
        self.r.nibble_times = []
        self.r.bite_at_ms = self.r.sim_ms
        self.run_until(lambda: self.r.state == R.BITE)
        return fish

    def bite_host_ms(self) -> float:
        return self.r.bite_start_ms + self.r.offset_ms

    def hooked(self, species: str = "perch") -> None:
        self.biting(species)
        self.step(10)
        self.step(1, [self.ev("hook_set")])
        assert self.r.state == R.HOOKED

    def fight_well(self, max_steps: int = 10_000) -> None:
        def done():
            f = self.r.fight
            if f is not None:
                self.reel = 1.0 if f.tension < 0.7 else 0.3
                self.tilt = -f.run_dir if f.running else 0.0
            return self.r.state not in (R.HOOKED, R.FIGHT)
        self.run_until(done, max_steps)
        self.reel = self.tilt = 0.0


def bot_round(tuning, seed: int, reaction_ms: float = 330.0, **kw) -> Driver:
    """Play a whole round with a simple competent bot."""
    d = Driver(tuning, seed=seed, **kw)
    rng = random.Random(seed + 7)
    pending: list[MotionEvent] = []
    for _ in range(int((tuning.round.length_s + tuning.round.overtime_cap_s + 30) / DT)):
        r = d.r
        if r.finished:
            break
        d.reel, d.tilt = 0.0, 0.0
        if r.state in (R.DRIFT, R.APPROACH):
            d.reel = 0.3
        elif r.state == R.FIGHT and r.fight is not None:
            d.reel = 1.0 if r.fight.tension < 0.7 else 0.3
            d.tilt = -r.fight.run_dir if r.fight.running else 0.0
        if not pending:
            if r.state == R.READY and d.host - (r.state_since_ms + r.offset_ms) > 700:
                pending.append(MotionEvent("cast", d.host + 30, rng.uniform(0.3, 1.0)))
            elif r.state == R.BITE and r.owner is not None and r.owner.spec.kind != "trap":
                pending.append(MotionEvent("hook_set", d.bite_host_ms() + max(80.0, rng.gauss(reaction_ms, 70)), 1.0))
        due = [p for p in pending if p.t_ms <= d.host]
        for p in due:
            pending.remove(p)
        d.step(1, due)
    return d


__all__ = ["Driver", "bot_round", "DT", "STEP_MS", "ATTACHED", "WANDER", "math"]
