"""Who is in the pond: weighted spawns, respawn timing, the special fish. Pure logic."""
from __future__ import annotations

import math
import random

from fishing.config import Species, Tuning
from fishing.sim.fish import Fish
from fishing.sim.scoring import roll_size

SPAWN_TRIES = 30  # attempts to find an in-water spawn point


class Spawner:
    def __init__(self, tuning: Tuning, rng: random.Random, practice: bool, length_s: float) -> None:
        self.t = tuning
        self.rng = rng
        self.practice = practice
        self.length_s = length_s
        self.next_id = 1
        self.respawn_in = rng.uniform(*tuning.spawn.respawn_s)
        self.special = tuning.species_by_id(tuning.special.species)
        self.junk = tuning.species_by_id(tuning.junk.species)
        self.special_at_s: float | None = None
        self.special_done = False
        if not practice and rng.random() < tuning.special.chance:
            self.special_at_s = rng.uniform(*tuning.special.window) * length_s

    # -- choosing ----------------------------------------------------------
    def weights(self, progress: float, counts: dict[str, int]) -> dict[str, float]:
        """Effective spawn weight per species id at this point of the round."""
        out = {}
        cap = self.t.spawn.per_species_max
        for s in self.t.species:
            if s.kind not in ("fish", "trap"):
                continue
            w0, w1 = s.weight
            w = w0 + (w1 - w0) * max(0.0, min(1.0, progress))
            if w > 0 and counts.get(s.id, 0) < cap:
                out[s.id] = w
        return out

    def choose(self, progress: float, counts: dict[str, int]) -> Species | None:
        w = self.weights(progress, counts)
        if not w:
            return None
        ids = list(w)
        sid = self.rng.choices(ids, weights=[w[i] for i in ids])[0]
        return self.t.species_by_id(sid)

    # -- making fish ---------------------------------------------------------
    def make(self, spec: Species, now_s: float) -> Fish:
        pond = self.t.pond
        rng = self.rng
        band = (min(pond.zone(z)[0] for z in spec.zones), max(pond.zone(z)[1] for z in spec.zones))
        tip_x, tip_y = pond.rod_tip
        m = self.t.fish_ai.edge_margin
        x = y = 0.0
        for _ in range(SPAWN_TRIES):
            r = rng.uniform(band[0] + m / 2, band[1] - m / 2)
            arc = self.t.spawn.spawn_arc_deg
            a = math.radians(rng.uniform(-arc, arc))
            x, y = tip_x + r * math.sin(a), tip_y - r * math.cos(a)
            if pond.water_left + m < x < pond.water_right - m and pond.water_top + m < y < pond.water_bottom - m:
                break
        size_cm, frac = roll_size(spec, self.t.scoring, rng)
        if spec.kind == "junk":
            lifetime = math.inf
        elif spec.kind == "special":
            lifetime = self.t.special.stay_s
        else:
            lifetime = rng.uniform(*self.t.spawn.lifetime_s)
        fish = Fish(
            id=self.next_id, spec=spec, x=x, y=y, heading=rng.uniform(-math.pi, math.pi),
            band=band, size_cm=size_cm, size_frac=frac, born_s=now_s, lifetime_s=lifetime,
        )
        self.next_id += 1
        return fish

    def initial(self, now_s: float, progress: float) -> list[Fish]:
        fishes: list[Fish] = []
        counts: dict[str, int] = {}
        for _ in range(self.t.spawn.initial):
            spec = self.choose(progress, counts)
            if spec is None:
                break
            counts[spec.id] = counts.get(spec.id, 0) + 1
            fishes.append(self.make(spec, now_s))
        for _ in range(self.t.junk.count):
            fishes.append(self.make(self.junk, now_s))
        return fishes

    # -- over time -----------------------------------------------------------
    def update(
        self, dt: float, now_s: float, elapsed_s: float, progress: float, frenzy: bool,
        swimming: list[Fish],
    ) -> list[Fish]:
        """Return newly spawned fish (regular respawns and the scheduled special)."""
        new: list[Fish] = []
        counts: dict[str, int] = {}
        for f in swimming:
            counts[f.spec.id] = counts.get(f.spec.id, 0) + 1
        live = sum(1 for f in swimming if f.spec.kind in ("fish", "trap"))
        if live < self.t.spawn.max:
            self.respawn_in -= dt * (1 / self.t.spawn.frenzy_respawn_mult if frenzy else 1.0)
            if self.respawn_in <= 0:
                spec = self.choose(progress, counts)
                if spec is not None:
                    new.append(self.make(spec, now_s))
                self.respawn_in = self.rng.uniform(*self.t.spawn.respawn_s)
        if self.special_at_s is not None and not self.special_done and elapsed_s >= self.special_at_s:
            new.append(self.spawn_special(now_s))
        return new

    def spawn_special(self, now_s: float) -> Fish:
        self.special_done = True
        return self.make(self.special, now_s)
