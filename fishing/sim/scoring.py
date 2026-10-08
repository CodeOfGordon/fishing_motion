"""Points for a catch: size, bonus species, streak and perfect hook. Pure logic."""
from __future__ import annotations

import random
from dataclasses import dataclass

from fishing.config import ScoringConfig, Species


@dataclass(frozen=True)
class CatchScore:
    points: int
    base: float
    bonus_mult: float
    streak_mult: float
    perfect_bonus: int


def roll_size(spec: Species, cfg: ScoringConfig, rng: random.Random) -> tuple[float, float]:
    """Return (size_cm, size_frac); big ones are rarer."""
    frac = rng.betavariate(*cfg.size_beta)
    lo, hi = spec.size_cm
    return lo + (hi - lo) * frac, frac


def streak_mult(streak: int, cfg: ScoringConfig) -> float:
    return 1.0 + cfg.streak_step * min(streak, cfg.streak_cap)


def score_catch(
    spec: Species, size_frac: float, is_bonus: bool, streak: int, perfect: bool, cfg: ScoringConfig
) -> CatchScore:
    """``streak`` is the count of consecutive catches before this one."""
    if spec.kind in ("trap", "junk"):
        return CatchScore(spec.points, float(spec.points), 1.0, 1.0, 0)
    base = spec.points * (cfg.size_base + cfg.size_span * size_frac)
    bonus = cfg.bonus_mult if is_bonus else 1.0
    smult = streak_mult(streak, cfg)
    perfect_bonus = cfg.perfect_hook_bonus if perfect else 0
    return CatchScore(round(base * bonus * smult) + perfect_bonus, base, bonus, smult, perfect_bonus)
