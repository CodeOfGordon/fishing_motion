import random
import statistics

import pytest

from fishing.sim.fight import LAND, LINE_OUT, SLACK, SNAP, start_fight, step_fight

DT = 1 / 60
REACTION_STEPS = 15  # a human-ish 250 ms delay between seeing tension and reacting


def run(tuning, sid, policy, seed, tilt_help=False, dist=None):
    cfg = tuning.fight
    rng = random.Random(seed)
    f = start_fight(tuning.species_by_id(sid), dist or rng.uniform(250, 550), 0.0, cfg, rng)
    delay = []
    while True:
        delay.append(policy(f))
        reel = delay.pop(0) if len(delay) > REACTION_STEPS else 0.0
        tilt = -f.run_dir if (tilt_help and f.running) else 0.0
        out = step_fight(f, DT, reel, tilt, cfg, rng, tuning.pond.land_radius,
                         tuning.difficulty["normal"].snap_strain_s)
        if out or f.elapsed > 60:
            return out, f.elapsed, f


def always(f):
    return 1.0


def never(f):
    return 0.0


def good(f):
    return 1.0 if f.tension < 0.7 else 0.3


WEAK = ["minnow", "bluegill", "perch", "bait_thief", "old_boot"]
STRONG = ["rainbow_trout", "bass", "catfish", "pike", "lantern_koi"]


@pytest.mark.parametrize("sid", WEAK)
def test_reeling_flat_out_lands_weak_fish(tuning, sid):
    results = [run(tuning, sid, always, s) for s in range(40)]
    assert all(o == LAND for o, _, _ in results)
    assert statistics.median(t for _, t, _ in results) < 7


@pytest.mark.parametrize("sid", STRONG)
def test_reeling_flat_out_snaps_strong_fish_quickly(tuning, sid):
    results = [run(tuning, sid, always, s) for s in range(40)]
    assert all(o == SNAP for o, _, _ in results)
    assert statistics.median(t for _, t, _ in results) < 3


@pytest.mark.parametrize("sid", WEAK + STRONG)
def test_never_reeling_always_slips_the_hook(tuning, sid):
    for s in range(10):
        out, t, _ = run(tuning, sid, never, s)
        assert out == SLACK
        assert t == pytest.approx(tuning.fight.slack_s, abs=0.05)


@pytest.mark.parametrize("sid,lo,hi", [
    ("minnow", 3, 7), ("perch", 4, 9), ("rainbow_trout", 5, 13), ("bass", 6, 14),
    ("catfish", 6, 15), ("pike", 9, 21), ("lantern_koi", 6, 15),
])
def test_good_play_lands_everything_in_a_species_band(tuning, sid, lo, hi):
    results = [run(tuning, sid, good, s) for s in range(60)]
    assert all(o == LAND for o, _, _ in results)
    assert lo <= statistics.median(t for _, t, _ in results) <= hi


@pytest.mark.parametrize("sid", STRONG)
def test_tilt_side_pressure_shortens_fights(tuning, sid):
    plain = statistics.median(run(tuning, sid, good, s)[1] for s in range(40))
    tilted = statistics.median(run(tuning, sid, good, s, tilt_help=True)[1] for s in range(40))
    assert tilted < plain


def test_stamina_only_falls(tuning):
    cfg = tuning.fight
    rng = random.Random(3)
    f = start_fight(tuning.species_by_id("bass"), 400, 0.0, cfg, rng)
    last = f.stamina
    for _ in range(600):
        step_fight(f, DT, 0.5, 0.0, cfg, rng, tuning.pond.land_radius, 10.0)
        assert f.stamina <= last
        last = f.stamina


def test_line_runs_out(tuning):
    cfg = tuning.fight
    rng = random.Random(1)
    f = start_fight(tuning.species_by_id("pike"), cfg.line_out - 5, 0.0, cfg, rng)
    out = None
    for _ in range(120):
        out = step_fight(f, DT, 0.1, 0.0, cfg, rng, tuning.pond.land_radius, 10.0)
        if out:
            break
    assert out == LINE_OUT


def test_strain_must_build_before_a_snap(tuning):
    cfg = tuning.fight
    rng = random.Random(1)
    f = start_fight(tuning.species_by_id("pike"), 500, 0.0, cfg, rng)
    f.tension = 1.2
    snap_s = tuning.difficulty["normal"].snap_strain_s
    steps = 0
    out = None
    while out is None and steps < 600:
        out = step_fight(f, DT, 1.0, 0.0, cfg, rng, tuning.pond.land_radius, snap_s)
        steps += 1
    assert out == SNAP
    assert steps * DT >= snap_s - DT


def test_junk_has_no_runs(tuning):
    cfg = tuning.fight
    rng = random.Random(1)
    f = start_fight(tuning.species_by_id("old_boot"), 300, 0.0, cfg, rng)
    for _ in range(60):
        step_fight(f, DT, 0.5, 0.0, cfg, rng, tuning.pond.land_radius, 10.0)
        assert not f.running and not f.new_run
