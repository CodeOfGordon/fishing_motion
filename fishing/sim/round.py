"""One round of fishing: the state machine, lure, fish, fight, timer and score.

Pure logic: no pygame. Each fixed step takes the shaped MotionState, the
gesture events delivered this frame and the host time, and returns the
GameEvents that happened. Gestures are judged by their own timestamps.
"""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field

from fishing.config import Species, Tuning
from fishing.input.motion import BITE_ACK, CAST, HOOK_SET, MotionEvent, MotionState
from fishing.sim import events as ev
from fishing.sim.events import GameEvent
from fishing.sim.fight import Fight, start_fight, step_fight
from fishing.sim.fish import ATTACHED, COMMITTED, FLEE, LEAVING, WANDER, Fish, angle_diff, update_fish
from fishing.sim.scoring import score_catch
from fishing.sim.spawner import Spawner

READY = "READY"
CASTING = "CASTING"
DRIFT = "DRIFT"
APPROACH = "APPROACH"
NIBBLE = "NIBBLE"
BITE = "BITE"
HOOKED = "HOOKED"
FIGHT = "FIGHT"
CATCH = "CATCH"
ESCAPE = "ESCAPE"
OVER = "OVER"

LURE_STATES = (DRIFT, APPROACH, NIBBLE, BITE)  # lure in the water, free to move
HISTORY_LEN = 64  # state transitions kept for judging late-arriving gestures
TIME_EPS_MS = 1e-6  # float slack when comparing a gesture stamp with a transition time

HOOK_RESULTS = ("hooked", "early", "late", "no_bite", "ignored")
ESCAPE_REASONS = ("snap", "slack", "line_out", "late", "early", "overtime")


@dataclass
class Lure:
    x: float
    y: float
    in_water: bool = False
    owner: int | None = None
    vx: float = 0.0
    vy: float = 0.0
    start: tuple[float, float] = (0.0, 0.0)
    target: tuple[float, float] = (0.0, 0.0)
    flight_t: float = 0.0
    flight_len: float = 0.0

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    @property
    def flight_progress(self) -> float:
        return min(1.0, self.flight_t / self.flight_len) if self.flight_len else 1.0


@dataclass
class Catch:
    species: str
    name: str
    kind: str
    size_cm: float
    points: int
    bonus: bool
    streak_mult: float
    perfect: bool
    fight_s: float


@dataclass
class Stats:
    casts: int = 0
    casts_ignored: int = 0
    empty_retrieves: int = 0
    bites: int = 0
    acks: int = 0
    hooks: dict[str, int] = field(default_factory=lambda: {r: 0 for r in HOOK_RESULTS})
    escapes: dict[str, int] = field(default_factory=lambda: {r: 0 for r in ESCAPE_REASONS})
    catches: list[Catch] = field(default_factory=list)
    best_streak: int = 0
    released: int = 0  # trap fish that let go of the bait (no penalty)
    reactions_ms: list[float] = field(default_factory=list)


@dataclass
class Card:
    kind: str  # "catch" | "escape" | "early"
    text: str
    catch: Catch | None = None
    until_ms: float = 0.0


class Round:
    def __init__(
        self,
        tuning: Tuning,
        rng: random.Random | None = None,
        *,
        practice: bool = False,
        difficulty: str = "normal",
        forgiving_hook: bool = True,
        seed: int | None = None,
    ) -> None:
        self.t = tuning
        self.seed = seed if seed is not None else random.randrange(2**31)
        self.rng = rng if rng is not None else random.Random(self.seed)
        self.practice = practice
        self.diff = tuning.difficulty.get(difficulty, tuning.difficulty["normal"])
        self.difficulty = difficulty if difficulty in tuning.difficulty else "normal"
        self.forgiving_hook = forgiving_hook
        self.length_s = tuning.round.length_s

        self.sim_ms = 0.0
        self.offset_ms = 0.0
        self.state = READY
        self.state_since_ms = 0.0
        self.history: deque[tuple[float, str]] = deque([(0.0, READY)], maxlen=HISTORY_LEN)
        self.inputs: deque[tuple[float, float, float]] = deque()  # (sim_ms, reel, tilt)
        self.reel = 0.0
        self.tilt = 0.0

        self.time_left_s: float | None = None if practice else self.length_s
        self.overtime_s = 0.0
        self.frozen = False
        self.resume_at_ms: float | None = None

        tip = tuning.pond.rod_tip
        self.lure = Lure(tip[0], tip[1])
        self.spawner = Spawner(tuning, self.rng, practice, self.length_s)
        self.fishes: list[Fish] = self.spawner.initial(0.0, self.progress)
        for f in self.fishes:
            f.alpha = 1.0  # the starting population is already there
        self.seen_species: set[str] = {f.spec.id for f in self.fishes if not f.is_static}
        self.global_flee_until_s = 0.0

        self.fight: Fight | None = None
        self.bite_id = 0
        self.bite_start_ms = -1e9
        self.bite_window_ms = 0.0
        self.bite_sent_host_ms = -1e12  # host time the last BITE was sent (acks are matched to it)
        self.acked_bite_id = 0
        self.last_ack_ms: float | None = None
        self.nibble_times: list[float] = []
        self.nibble_start_ms = 0.0
        self.bite_at_ms = 0.0
        self.spook_hold_s = 0.0
        self.hooked_until_ms = 0.0
        self.reaction_ms = 0.0
        self.perfect = False

        self.score = 0
        self.streak = 0
        self.stats = Stats()
        self.card: Card | None = None
        self.bonus_species: str | None = None
        self.bonus_next_s = 0.0
        self.frenzy_announced = False
        self.out: list[GameEvent] = []
        self.started = False

    # ------------------------------------------------------------------ helpers
    @property
    def now_s(self) -> float:
        return self.sim_ms / 1000.0

    @property
    def elapsed_s(self) -> float:
        return self.now_s

    @property
    def progress(self) -> float:
        if self.practice:
            return self.t.spawn.practice_progress
        return max(0.0, min(1.0, self.sim_ms / 1000.0 / self.length_s))

    @property
    def time_up(self) -> bool:
        return self.time_left_s is not None and self.time_left_s <= 0

    @property
    def frenzy(self) -> bool:
        return self.time_left_s is not None and 0 < self.time_left_s <= self.t.round.frenzy_s

    @property
    def finished(self) -> bool:
        return self.state == OVER

    def fish_by_id(self, fid: int | None) -> Fish | None:
        for f in self.fishes:
            if f.id == fid:
                return f
        return None

    @property
    def owner(self) -> Fish | None:
        return self.fish_by_id(self.lure.owner)

    def _emit(self, kind: str, **kw) -> GameEvent:
        e = GameEvent(kind, self.sim_ms + self.offset_ms, self.state, **kw)
        self.out.append(e)
        return e

    def _set_state(self, new: str) -> None:
        old = self.state
        self.state = new
        self.state_since_ms = self.sim_ms
        self.history.append((self.sim_ms, new))
        self._emit(ev.STATE, detail={"from": old, "to": new})
        if new == OVER:
            self._emit(ev.ROUND_END, value=self.score, detail=self.summary())

    def state_at(self, t_sim_ms: float) -> str | None:
        """The state that was active at a past sim time (None if too old to know)."""
        found = None
        for t, s in self.history:
            if t <= t_sim_ms + TIME_EPS_MS:
                found = s
            else:
                break
        return found

    def _input_at(self, t_sim_ms: float) -> tuple[float, float]:
        """(reel, tilt) as they were at a past sim time (oldest known if earlier)."""
        reel, tilt = self.reel, self.tilt
        for t, r, ti in reversed(self.inputs):
            reel, tilt = r, ti
            if t <= t_sim_ms:
                break
        return reel, tilt

    def _effective_wariness(self, spec: Species) -> float:
        w = spec.wariness + self.diff.wariness_add
        if self.frenzy:
            w -= self.t.spawn.frenzy_wariness_drop
        return max(0.0, min(1.0, w))

    def _reset_lure(self) -> None:
        tip = self.t.pond.rod_tip
        self.lure = Lure(tip[0], tip[1])

    def _dist_to_tip(self, x: float, y: float) -> float:
        tip = self.t.pond.rod_tip
        return math.hypot(x - tip[0], y - tip[1])

    # ------------------------------------------------------------------ step
    def step(
        self, dt: float, st: MotionState, events: list[MotionEvent], host_now_ms: float,
        stale: bool = False,
    ) -> list[GameEvent]:
        self.out = []
        if self.finished:
            for e in events:
                if e.kind == BITE_ACK:
                    self._on_ack(e)
                else:
                    self._emit_ignored(e, "state:OVER", count=False)
            return self.out
        if stale or self.frozen:
            if not self._handle_freeze(stale, events, host_now_ms):
                return self.out
        self.offset_ms = host_now_ms - self.sim_ms
        if not self.started:
            self.started = True
            self._emit(ev.ROUND_START, detail={"seed": self.seed, "practice": self.practice,
                                               "difficulty": self.difficulty})
            self._rotate_bonus()
        self.reel, self.tilt = st.reel_rate, st.tilt
        self.inputs.append((self.sim_ms, self.reel, self.tilt))
        while self.inputs and self.sim_ms - self.inputs[0][0] > self.t.input.history_ms:
            self.inputs.popleft()

        for e in events:
            self._on_motion_event(e)

        self.sim_ms += dt * 1000.0
        self._tick_timer(dt)
        self._tick_population(dt)
        self._tick_state(dt)
        return self.out

    def _handle_freeze(self, stale: bool, events: list[MotionEvent], host_now_ms: float) -> bool:
        """Returns True when play may continue this step."""
        if stale:
            if not self.frozen:
                self.frozen = True
                self._emit(ev.DISCONNECT)
            self.resume_at_ms = None
            for e in events:
                self._ack_or_ignore(e, "disconnected")
            return False
        if self.resume_at_ms is None:
            self.resume_at_ms = host_now_ms + self.t.round.resume_countdown_s * 1000.0
        if host_now_ms < self.resume_at_ms:
            for e in events:
                self._ack_or_ignore(e, "resuming")
            return False
        self.frozen = False
        self.resume_at_ms = None
        self.offset_ms = host_now_ms - self.sim_ms
        self._emit(ev.RECONNECT)
        return True

    def _ack_or_ignore(self, e: MotionEvent, reason: str) -> None:
        if e.kind == BITE_ACK:
            self._on_ack(e)
        else:
            self._emit_ignored(e, reason)

    def _emit_ignored(self, e: MotionEvent, reason: str, count: bool = True) -> None:
        detail = {"why": reason, "raw": e.kind, "gesture_t_ms": round(e.t_ms, 1)}
        if e.kind == CAST:
            if count:
                self.stats.casts_ignored += 1
            self._emit(ev.CAST, accepted=False, reason=reason, strength=e.strength, detail=detail)
        elif e.kind == HOOK_SET:
            if count:
                self.stats.hooks["ignored"] += 1
            self._emit(ev.HOOK_ATTEMPT, accepted=False, reason="ignored", strength=e.strength, detail=detail)

    def mark_bite_sent(self, bite_id: int, host_ms: float) -> None:
        """The play scene calls this right after send("BITE"): acks are timed from here."""
        if bite_id == self.bite_id:
            self.bite_sent_host_ms = host_ms

    def _on_ack(self, e: MotionEvent) -> None:
        """An ACK from the Nano after it beeped, matched to the last bite on the host clock."""
        latency = e.t_ms - self.bite_sent_host_ms
        dup = self.bite_id > 0 and self.acked_bite_id == self.bite_id
        ok = self.bite_id > 0 and not dup and 0 <= latency <= self.t.hook.ack_match_ms
        if ok:
            self.acked_bite_id = self.bite_id
            self.stats.acks += 1
            self.last_ack_ms = latency
        self._emit(ev.BITE_ACK, accepted=ok, reason="duplicate" if dup else ("" if ok else "unmatched"),
                   bite_id=self.bite_id or None, value=latency if self.bite_id else None)

    # ------------------------------------------------------------------ gestures
    def _on_motion_event(self, e: MotionEvent) -> None:
        if e.kind == BITE_ACK:
            self._on_ack(e)
            return
        te = e.t_ms - self.offset_ms  # the gesture's time on the sim clock
        s_at = self.state_at(te)
        if e.kind == CAST:
            if self.state == BITE and s_at == BITE and self.forgiving_hook:
                self._hook_attempt(e, te, s_at)
            else:
                self._try_cast(e, te, s_at)
        elif e.kind == HOOK_SET:
            self._hook_attempt(e, te, s_at)

    def _try_cast(self, e: MotionEvent, te: float, s_at: str | None) -> None:
        reel_then, _ = self._input_at(te)
        if self.state != READY or s_at != READY:
            reason = f"state:{self.state if self.state != READY else s_at}"
        elif te - self.state_since_ms < self.t.cast.arm_delay_s * 1000.0:
            reason = "not_armed:too_soon"
        elif reel_then >= self.t.cast.arm_max_reel:
            reason = "not_armed:reeling"
        elif self.time_up:
            reason = "time_up"
        else:
            self._start_cast(e, te)
            return
        self.stats.casts_ignored += 1
        self._emit(ev.CAST, accepted=False, reason=reason, strength=e.strength,
                   detail={"gesture_t_ms": round(e.t_ms, 1)})

    def _start_cast(self, e: MotionEvent, te: float) -> None:
        c = self.t.cast
        strength = max(0.0, min(1.0, e.strength))
        _, tilt_then = self._input_at(te - c.aim_lookback_ms)
        aim = math.radians(tilt_then * c.aim_max_deg)
        dist = c.min_dist + c.dist_per_strength * strength
        tip = self.t.pond.rod_tip
        tx, ty = self._clamp_ray(tip, aim, dist)
        self.lure = Lure(tip[0], tip[1], start=tip, target=(tx, ty),
                         flight_len=c.flight_base_s + c.flight_per_strength_s * strength)
        self.stats.casts += 1
        self._emit(ev.CAST, accepted=True, strength=strength, value=self._dist_to_tip(tx, ty),
                   detail={"aim_deg": round(math.degrees(aim), 1), "x": round(tx), "y": round(ty),
                           "gesture_t_ms": round(e.t_ms, 1)})
        self._set_state(CASTING)

    def _clamp_ray(self, tip: tuple[float, float], aim: float, dist: float) -> tuple[float, float]:
        """Point `dist` along the aim ray from the tip, pulled back to stay on the water."""
        p = self.t.pond
        dx, dy = math.sin(aim), -math.cos(aim)
        limit = dist
        if dx > 1e-9:
            limit = min(limit, (p.water_right - tip[0]) / dx)
        elif dx < -1e-9:
            limit = min(limit, (p.water_left - tip[0]) / dx)
        if dy < -1e-9:
            limit = min(limit, (p.water_top - tip[1]) / dy)
        return tip[0] + dx * limit, tip[1] + dy * limit

    def _hook_attempt(self, e: MotionEvent, te: float, s_at: str | None) -> None:
        h = self.t.hook
        reel_then, _ = self._input_at(te)
        fish = self.owner
        reaction = None
        why = ""
        if s_at is None:
            result, why = "ignored", "stale_event"
        elif s_at == BITE and self.state == BITE:
            if te <= self._bite_end_ms:
                result = "hooked"
                reaction = te - self.bite_start_ms
            else:
                result = "late"
        elif s_at in (BITE, HOOKED) and self.state in (HOOKED, FIGHT):
            result, why = "ignored", "already_hooked"
        elif s_at == BITE:
            result = "late"  # stamped during a bite that has since ended
        elif s_at == NIBBLE and self.state in (NIBBLE, BITE):
            if e.kind != HOOK_SET:
                result, why = "ignored", "cast_in_nibble"
            elif reel_then > h.nibble_ignore_hook_reel:
                result, why = "ignored", "reeling"
            else:
                result = "early"
        elif s_at in (READY, CASTING, DRIFT, APPROACH, NIBBLE):
            result = "no_bite"
        else:
            result, why = "ignored", f"state:{s_at}"

        bid = self.bite_id if (self.state in (BITE, HOOKED, FIGHT) or s_at in (BITE, HOOKED)) else None
        if result == "late" and bid:
            reaction = te - self.bite_start_ms
        self.stats.hooks[result] += 1
        self._emit(
            ev.HOOK_ATTEMPT, accepted=result == "hooked", reason=result, bite_id=bid,
            species=fish.spec.id if fish and result in ("hooked", "early", "late") else "",
            strength=e.strength, value=reaction,
            detail={"raw": e.kind, "why": why, "gesture_t_ms": round(e.t_ms, 1)},
        )
        if result == "hooked":
            self._hooked(reaction or 0.0)
        elif result == "early":
            self._early(bid)
        elif result == "late" and self.state == BITE:
            self._bite_over()

    # ------------------------------------------------------------------ transitions
    def _early(self, bite_id: int | None) -> None:
        fish = self.owner
        self.stats.escapes["early"] += 1
        self._emit(ev.ESCAPE, reason="early", bite_id=bite_id, species=fish.spec.id if fish else "")
        self._break_streak()
        self._release_owner(flee=True, leave=True)
        self.card = Card("early", "Too early!", until_ms=self.sim_ms + self.t.round.escape_card_s * 1000)
        self._set_state(DRIFT)

    def _hooked(self, reaction_ms: float) -> None:
        fish = self.owner
        self.reaction_ms = reaction_ms
        self.perfect = reaction_ms <= self.t.hook.perfect_ms
        self.stats.reactions_ms.append(reaction_ms)
        self._emit(ev.HOOKED, bite_id=self.bite_id, species=fish.spec.id if fish else "",
                   value=reaction_ms, detail={"perfect": self.perfect})
        self.hooked_until_ms = self.sim_ms + self.t.round.hooked_s * 1000.0
        self._set_state(HOOKED)

    def _flee(self, fish: Fish, from_xy: tuple[float, float], until_s: float, leave: bool) -> None:
        """A fish darts away; no fish may take the lure for a moment after any flee."""
        fish.flee(from_xy, until_s, self.t.fish_ai, leave=leave)
        self.global_flee_until_s = max(self.global_flee_until_s,
                                       self.now_s + self.t.fish_ai.global_flee_cooldown_s)

    def _release_owner(self, flee: bool, leave: bool = False) -> None:
        fish = self.owner
        self.lure.owner = None
        if fish is None:
            return
        if fish.is_static:
            fish.mode = WANDER
            fish.cooldown_until = self.now_s + self.t.fish_ai.flee_cooldown_s
        elif flee:
            self._flee(fish, (self.lure.x, self.lure.y), self.now_s + self.t.fish_ai.flee_cooldown_s, leave)
        else:
            fish.mode = WANDER

    def _break_streak(self) -> None:
        self.streak = 0

    def _start_bite(self, fish: Fish) -> None:
        self.bite_id += 1
        self.stats.bites += 1
        self.bite_start_ms = self.sim_ms
        self.bite_sent_host_ms = self.sim_ms + self.offset_ms  # refined by mark_bite_sent()
        self.bite_window_ms = fish.spec.window_ms * self.diff.window_mult
        fish.mode = ATTACHED
        self._emit(ev.BITE, bite_id=self.bite_id, species=fish.spec.id, value=self.bite_window_ms,
                   detail={"kind": fish.spec.kind})
        self._set_state(BITE)

    def _begin_nibbles(self, fish: Fish) -> None:
        rng = self.rng
        spec = fish.spec
        n = rng.randint(*spec.nibbles)
        if self.frenzy:
            n = max(0, n - self.t.spawn.frenzy_nibble_drop)
        t = self.sim_ms
        self.nibble_times = []
        for _ in range(n):
            t += rng.uniform(*spec.gap_s) * 1000.0
            self.nibble_times.append(t)
        self.bite_at_ms = t + rng.uniform(*spec.pause_s) * 1000.0
        self.nibble_start_ms = self.sim_ms
        self.spook_hold_s = 0.0
        fish.mode = ATTACHED
        self._set_state(NIBBLE)

    def _catch(self) -> None:
        fight = self.fight
        fish = self.owner
        assert fight is not None
        spec = fight.spec
        is_bonus = spec.id == self.bonus_species
        sc = score_catch(spec, fish.size_frac if fish else 0.5, is_bonus, self.streak, self.perfect,
                         self.t.scoring)
        if spec.kind in ("fish", "special"):
            self.streak += 1
            self.stats.best_streak = max(self.stats.best_streak, self.streak)
        elif spec.kind == "trap":
            self._break_streak()
        self.score += sc.points
        catch = Catch(spec.id, spec.name, spec.kind, fish.size_cm if fish else 0.0, sc.points,
                      is_bonus, sc.streak_mult, self.perfect and sc.perfect_bonus > 0, fight.elapsed)
        self.stats.catches.append(catch)
        self._emit(ev.CATCH, bite_id=self.bite_id, species=spec.id, value=sc.points,
                   detail={"size_cm": round(catch.size_cm, 1), "fight_s": round(fight.elapsed, 2),
                           "bonus": is_bonus, "streak_mult": sc.streak_mult, "perfect": catch.perfect,
                           "score": self.score})
        if fish is not None:
            fish.gone = True
        self.lure.owner = None
        self.fight = None
        self.card = Card("catch", spec.name, catch, self.sim_ms + self.t.round.catch_card_s * 1000)
        if spec.kind == "special" or is_bonus:
            self.bonus_next_s = self.now_s  # pick a new bonus fish right away
        self._set_state(CATCH)

    def _escape(self, reason: str) -> None:
        fish = self.owner
        species = self.fight.spec.id if self.fight else (fish.spec.id if fish else "")
        self.stats.escapes[reason] += 1
        self._emit(ev.ESCAPE, reason=reason, bite_id=self.bite_id or None, species=species)
        self._break_streak()
        self._release_owner(flee=True, leave=True)
        self.fight = None
        text = {"snap": "Line snapped!", "slack": "It shook the hook!", "line_out": "It ran out the line!",
                "late": "Too late! Bait stolen", "overtime": "Time's up!"}.get(reason, "It got away")
        self.card = Card("escape", text, until_ms=self.sim_ms + self.t.round.escape_card_s * 1000)
        self._set_state(ESCAPE)

    # ------------------------------------------------------------------ ticking
    def _tick_timer(self, dt: float) -> None:
        if self.time_left_s is None:
            return
        if self.time_left_s > 0:
            prev = self.time_left_s
            self.time_left_s = max(0.0, prev - dt)
            r = self.t.round
            if self.time_left_s <= r.warn_s and math.ceil(prev) != math.ceil(self.time_left_s):
                self._emit(ev.CLOCK_TICK, value=math.ceil(self.time_left_s))
            if not self.frenzy_announced and 0 < self.time_left_s <= r.frenzy_s:
                self.frenzy_announced = True
                self._emit(ev.FRENZY)
            if self.time_left_s == 0:
                self._emit(ev.TIME_UP)
        elif self.state == FIGHT:
            self.overtime_s += dt

    def _tick_population(self, dt: float) -> None:
        swimming = [f for f in self.fishes if not f.gone and not f.is_static]
        if not self.time_up:
            new = self.spawner.update(dt, self.now_s, self.elapsed_s, self.progress, self.frenzy, swimming)
            for f in new:
                self.fishes.append(f)
                self.seen_species.add(f.spec.id)
                if f.spec.kind == "special":
                    self._emit(ev.SPECIAL_APPEARED, species=f.spec.id)
                    self._set_bonus(f.spec.id)
        for f in self.fishes:
            if f.gone or f.mode in (COMMITTED, ATTACHED):
                continue
            if f.mode == WANDER and self.now_s - f.born_s > f.lifetime_s:
                f.leave()
            update_fish(f, dt, self.t.pond, self.t.fish_ai, self.rng)
        self.fishes = [f for f in self.fishes if not f.gone]
        if self.now_s >= self.bonus_next_s:
            self._rotate_bonus()

    def _set_bonus(self, sid: str | None) -> None:
        self.bonus_next_s = self.now_s + self.t.scoring.bonus_rotate_s
        if sid != self.bonus_species:
            self.bonus_species = sid
            self._emit(ev.BONUS_CHANGED, species=sid or "")

    def _rotate_bonus(self) -> None:
        present = [f for f in self.fishes if not f.gone and f.mode != LEAVING]
        special = [f for f in present if f.spec.kind == "special"]
        if special:
            self._set_bonus(special[0].spec.id)
            return
        ids = sorted({f.spec.id for f in present if f.spec.kind == "fish"})
        choices = [i for i in ids if i != self.bonus_species] or ids
        if not choices:
            self.bonus_next_s = self.now_s + self.t.scoring.bonus_rotate_s
            return
        self._set_bonus(self.rng.choice(choices))

    def _tick_state(self, dt: float) -> None:
        s = self.state
        if s == READY:
            if self.time_up:
                self._set_state(OVER)
        elif s == CASTING:
            self._tick_casting(dt)
        elif s in LURE_STATES:
            if s in (DRIFT, APPROACH) and self.time_up:
                self._release_owner(flee=False)
                self._set_state(OVER)
                return
            self._move_lure(dt)
            if self.state == s:
                {DRIFT: self._tick_drift, APPROACH: self._tick_approach,
                 NIBBLE: self._tick_nibble, BITE: self._tick_bite}[s](dt)
        elif s == HOOKED:
            self._stick_owner()
            if self.sim_ms >= self.hooked_until_ms:
                self._start_fight()
        elif s == FIGHT:
            self._tick_fight(dt)
        elif s in (CATCH, ESCAPE):
            if self.card is None or self.sim_ms >= self.card.until_ms:
                self.card = None
                self._reset_lure()
                self._set_state(OVER if self.time_up else READY)
        if self.card is not None and self.card.kind == "early" and self.sim_ms >= self.card.until_ms:
            self.card = None

    def _tick_casting(self, dt: float) -> None:
        lure = self.lure
        lure.flight_t += dt
        p = lure.flight_progress
        lure.x = lure.start[0] + (lure.target[0] - lure.start[0]) * p
        lure.y = lure.start[1] + (lure.target[1] - lure.start[1]) * p
        if p < 1.0:
            return
        lure.in_water = True
        self._emit(ev.LURE_LAND, value=self._dist_to_tip(lure.x, lure.y),
                   detail={"x": round(lure.x), "y": round(lure.y)})
        c = self.t.cast
        scattered = 0
        for f in self.fishes:
            if f.is_static or f.mode not in (WANDER, FLEE):
                continue
            d = f.dist_to(lure.x, lure.y)
            if d < c.scatter_radius:
                self._flee(f, (lure.x, lure.y), self.now_s + c.scatter_cooldown_s, leave=False)
                scattered += 1
            elif d < c.curious_radius:
                f.curious_until = self.now_s + c.curious_s
        if scattered:
            self._emit(ev.SCATTER, value=scattered)
        self._set_state(OVER if self.time_up else DRIFT)

    def _move_lure(self, dt: float) -> None:
        lc = self.t.lure
        lure = self.lure
        tip = self.t.pond.rod_tip
        dx, dy = tip[0] - lure.x, tip[1] - lure.y
        d = math.hypot(dx, dy) or 1.0
        retrieve = self.reel * lc.retrieve_speed
        steer = self.tilt * lc.steer_speed * (lc.steer_reel_floor + (1 - lc.steer_reel_floor) * self.reel)
        if self.state in (NIBBLE, BITE):
            retrieve = steer = 0.0  # a fish is on it: reel only spooks, tilt is ignored
        lure.vx = dx / d * retrieve + steer
        lure.vy = dy / d * retrieve
        p = self.t.pond
        lure.x = max(p.water_left, min(p.water_right, lure.x + lure.vx * dt))
        lure.y = max(p.water_top, min(p.water_bottom, lure.y + lure.vy * dt))
        if self._dist_to_tip(lure.x, lure.y) <= p.dock_radius:
            if self.state in (DRIFT, APPROACH):
                fish = self.owner
                if self.state == APPROACH and fish is not None:
                    self._emit(ev.LOST_INTEREST, species=fish.spec.id, reason="dock")
                    fish.cooldown_until = self.now_s + self.t.fish_ai.flee_cooldown_s
                self._release_owner(flee=False)
                self.stats.empty_retrieves += 1
                self._emit(ev.EMPTY_RETRIEVE)
                self._reset_lure()
                self._set_state(READY)
        self._stick_owner()

    def _stick_owner(self) -> None:
        fish = self.owner
        if fish is not None and fish.mode == ATTACHED:
            fish.x, fish.y = self.lure.x, self.lure.y

    def _tick_drift(self, dt: float) -> None:
        if self.time_up or self.now_s < self.global_flee_until_s:
            return
        lure = self.lure
        for f in self.fishes:  # junk snags on contact
            if f.is_static and self.now_s >= f.cooldown_until and \
                    f.dist_to(lure.x, lure.y) < self.t.junk.snag_radius:
                self.lure.owner = f.id
                self._emit(ev.COMMIT, species=f.spec.id, detail={"snag": True})
                self._start_bite(f)
                return
        ai = self.t.fish_ai
        if self._dist_to_tip(lure.x, lure.y) < ai.dock_shy_radius:
            return  # fish won't take a lure right by the dock
        slow = self.t.lure.slow_band[0] <= self.reel <= self.t.lure.slow_band[1]
        candidates = sorted(
            (f for f in self.fishes if not f.is_static and f.mode == WANDER and f.alpha >= 1.0
             and self.now_s >= f.cooldown_until),
            key=lambda f: f.dist_to(lure.x, lure.y),
        )
        for f in candidates:
            w = self._effective_wariness(f.spec)
            d = f.dist_to(lure.x, lure.y)
            if d > ai.notice_radius * (1 - ai.notice_wariness_shrink * w):
                continue  # out of this fish's range (wariness shrinks it); a bolder one may still notice
            to_lure = math.atan2(lure.y - f.y, lure.x - f.x)
            cone = math.radians(ai.cone_deg - ai.cone_wariness_shrink_deg * w)
            if abs(angle_diff(to_lure, f.heading)) > cone:
                continue
            if lure.speed > ai.scare_speed * (1 - ai.scare_wariness_shrink * w):
                if f.spec.touchy or w >= ai.wary_flee:
                    self._flee(f, (lure.x, lure.y), self.now_s + ai.flee_cooldown_s, leave=True)
                    self._emit(ev.SPOOK, species=f.spec.id, reason="fast_lure")
                continue
            rate = ai.commit_rate * (1 - ai.commit_wariness_shrink * w)
            if slow:
                rate *= self.t.lure.slow_interest_mult
            if self.now_s < f.curious_until:
                rate *= self.t.cast.curious_mult
            if self.rng.random() < 1 - math.exp(-rate * dt):
                f.mode = COMMITTED
                self.lure.owner = f.id
                self._emit(ev.COMMIT, species=f.spec.id)
                self._set_state(APPROACH)
                return

    def _tick_approach(self, dt: float) -> None:
        fish = self.owner
        if fish is None:
            self._set_state(DRIFT)
            return
        ai = self.t.fish_ai
        lure = self.lure
        w = self._effective_wariness(fish.spec)
        if lure.speed > ai.scare_speed * (1 - ai.scare_wariness_shrink * w):
            self._emit(ev.LOST_INTEREST, species=fish.spec.id)
            wary = fish.spec.touchy or w >= ai.wary_flee
            self._release_owner(flee=wary, leave=wary)
            fish.cooldown_until = self.now_s + ai.flee_cooldown_s
            self._set_state(DRIFT)
            return
        dx, dy = lure.x - fish.x, lure.y - fish.y
        d = math.hypot(dx, dy)
        fish.heading = math.atan2(dy, dx)
        fish.speed = fish.spec.cruise * ai.approach_speed_mult
        if d <= ai.arrive_radius + fish.speed * dt:
            fish.x, fish.y = lure.x, lure.y
            self._begin_nibbles(fish)
        else:
            fish.x += dx / d * fish.speed * dt
            fish.y += dy / d * fish.speed * dt

    def _tick_nibble(self, dt: float) -> None:
        fish = self.owner
        if fish is None:
            self._set_state(DRIFT)
            return
        h = self.t.hook
        if self.sim_ms - self.nibble_start_ms >= h.nibble_spook_grace_s * 1000 and self.reel > h.nibble_spook_reel:
            self.spook_hold_s += dt
            if self.spook_hold_s >= h.nibble_spook_hold_s:
                self._emit(ev.SPOOK, species=fish.spec.id, reason="reeling")
                self._release_owner(flee=True, leave=True)
                self._set_state(DRIFT)
                return
        else:
            self.spook_hold_s = 0.0
        while self.nibble_times and self.sim_ms >= self.nibble_times[0]:
            self.nibble_times.pop(0)
            self._emit(ev.NIBBLE, species=fish.spec.id)
        if not self.nibble_times and self.sim_ms >= self.bite_at_ms:
            self._start_bite(fish)

    @property
    def _bite_end_ms(self) -> float:
        """Last sim time a hook-set may be stamped and still count."""
        return self.bite_start_ms + self.bite_window_ms + self.t.hook.grace_ms

    def _tick_bite(self, dt: float) -> None:
        if self.owner is None:
            self._set_state(DRIFT)
            return
        # Wait a little past the window so a gesture stamped in time but delivered
        # late (detector latency, a slow frame) is still judged by its stamp.
        if self.sim_ms > self._bite_end_ms + self.t.hook.delivery_margin_ms:
            self._bite_over()

    def _bite_over(self) -> None:
        fish = self.owner
        if fish is None:
            self._set_state(DRIFT)
            return
        if fish.spec.kind == "trap":
            self.stats.released += 1
            self._emit(ev.BITE_RELEASED, bite_id=self.bite_id, species=fish.spec.id)
            self._release_owner(flee=True)
            self._set_state(DRIFT)
        else:
            self._escape("late")

    def _start_fight(self) -> None:
        fish = self.owner
        spec = fish.spec if fish else self.t.species[0]
        tip = self.t.pond.rod_tip
        dist = self._dist_to_tip(self.lure.x, self.lure.y)
        angle = math.atan2(self.lure.x - tip[0], tip[1] - self.lure.y)
        self.fight = start_fight(spec, dist, angle, self.t.fight, self.rng, self.diff.strength_mult)
        self._emit(ev.FIGHT_RUN, species=spec.id, detail={"dir": self.fight.run_dir, "first": True})
        self._set_state(FIGHT)

    def _tick_fight(self, dt: float) -> None:
        f = self.fight
        if f is None:
            self._set_state(READY)
            return
        outcome = step_fight(f, dt, self.reel, self.tilt, self.t.fight, self.rng,
                             self.t.pond.land_radius, self.diff.snap_strain_s)
        tip = self.t.pond.rod_tip
        p = self.t.pond
        # the fish holds at the bank while the line pays out (dist itself is not clamped)
        self.lure.x = max(p.water_left, min(p.water_right, tip[0] + math.sin(f.angle) * f.dist))
        self.lure.y = max(p.water_top, min(p.water_bottom, tip[1] - math.cos(f.angle) * f.dist))
        self._stick_owner()
        if f.new_run:
            self._emit(ev.FIGHT_RUN, species=f.spec.id, detail={"dir": f.run_dir})
        if outcome == "land":
            self._catch()
        elif outcome is not None:
            self._escape(outcome)
        elif self.time_up and self.overtime_s >= self.t.round.overtime_cap_s:
            self._escape("overtime")

    # ------------------------------------------------------------------ debug & results
    def force_bite(self) -> bool:
        """Practice key B: the nearest fish bites now (tests the buzzer and hook-set)."""
        if self.frozen or self.state not in (DRIFT, APPROACH, NIBBLE) or not self.lure.in_water:
            why = "frozen" if self.frozen else self.state
            self._emit(ev.DEBUG, accepted=False, reason=f"force_bite:{why}")
            return False
        fish = self.owner
        if fish is None:
            free = [f for f in self.fishes if not f.is_static and f.mode in (WANDER, FLEE)]
            if not free:
                free = [self.spawner.make(self.t.species_by_id("minnow"), self.now_s)]
                self.fishes.append(free[0])
            fish = min(free, key=lambda f: f.dist_to(self.lure.x, self.lure.y))
            self.lure.owner = fish.id
        fish.alpha = 1.0
        fish.x, fish.y = self.lure.x, self.lure.y
        self._emit(ev.DEBUG, accepted=True, reason="force_bite", species=fish.spec.id)
        self._start_bite(fish)
        return True

    def force_special(self) -> None:
        """Practice key K: the special fish appears now."""
        f = self.spawner.spawn_special(self.now_s)
        self.fishes.append(f)
        self._emit(ev.SPECIAL_APPEARED, species=f.spec.id, detail={"debug": True})
        self._set_bonus(f.spec.id)

    def summary(self) -> dict:
        s = self.stats
        biggest = max((c for c in s.catches if c.kind in ("fish", "special")),
                      key=lambda c: c.size_cm, default=None)
        return {
            "score": self.score,
            "medal": self.t.medals.medal_for(self.score),
            "catches": len(s.catches),
            "biggest": f"{biggest.name} {biggest.size_cm:.0f} cm" if biggest else "",
            "best_streak": s.best_streak,
            "casts": s.casts,
            "casts_ignored": s.casts_ignored,
            "bites": s.bites,
            "acks": s.acks,
            "released": s.released,
            "hooks": dict(s.hooks),
            "escapes": dict(s.escapes),
        }
