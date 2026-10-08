import random

import pytest

from fishing.sim.scoring import roll_size, score_catch, streak_mult


def test_base_points_scale_with_size(tuning):
    perch = tuning.species_by_id("perch")
    s = tuning.scoring
    small = score_catch(perch, 0.0, False, 0, False, s).points
    big = score_catch(perch, 1.0, False, 0, False, s).points
    assert small == round(perch.points * s.size_base)
    assert big == round(perch.points * (s.size_base + s.size_span))


def test_bonus_doubles(tuning):
    perch = tuning.species_by_id("perch")
    s = tuning.scoring
    plain = score_catch(perch, 0.5, False, 0, False, s).points
    bonus = score_catch(perch, 0.5, True, 0, False, s).points
    assert bonus == pytest.approx(plain * s.bonus_mult, abs=1)


def test_streak_multiplier_steps_and_caps(tuning):
    s = tuning.scoring
    assert streak_mult(0, s) == 1.0
    assert streak_mult(1, s) == pytest.approx(1 + s.streak_step)
    assert streak_mult(s.streak_cap, s) == streak_mult(s.streak_cap + 10, s)


def test_perfect_hook_adds_flat_bonus(tuning):
    perch = tuning.species_by_id("perch")
    s = tuning.scoring
    a = score_catch(perch, 0.5, False, 0, False, s).points
    b = score_catch(perch, 0.5, False, 0, True, s).points
    assert b - a == s.perfect_hook_bonus


@pytest.mark.parametrize("sid", ["bait_thief", "old_boot"])
def test_trap_and_junk_score_flat(tuning, sid):
    spec = tuning.species_by_id(sid)
    sc = score_catch(spec, 1.0, True, 5, True, tuning.scoring)
    assert sc.points == spec.points


def test_sizes_stay_in_range_and_skew_small(tuning):
    spec = tuning.species_by_id("pike")
    rng = random.Random(1)
    rolls = [roll_size(spec, tuning.scoring, rng) for _ in range(5000)]
    assert all(spec.size_cm[0] <= cm <= spec.size_cm[1] for cm, _ in rolls)
    assert sum(frac for _, frac in rolls) / len(rolls) < 0.5


def test_medals(tuning):
    m = tuning.medals
    assert m.medal_for(m.bronze - 1) is None
    assert m.medal_for(m.bronze) == "bronze"
    assert m.medal_for(m.platinum + 999) == "platinum"
