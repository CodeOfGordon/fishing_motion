import math
import random
from collections import Counter

import pytest

from fishing.sim.spawner import Spawner


def make(tuning, seed=1, practice=False):
    return Spawner(tuning, random.Random(seed), practice, tuning.round.length_s)


@pytest.mark.parametrize("progress", [0.0, 0.5, 1.0])
def test_weighted_choice_matches_weights(tuning, progress):
    sp = make(tuning)
    w = sp.weights(progress, {})
    total = sum(w.values())
    n = 20_000
    got = Counter(sp.choose(progress, {}).id for _ in range(n))
    for sid, weight in w.items():
        assert got[sid] / n == pytest.approx(weight / total, abs=0.02)


def test_weights_lerp_across_the_round(tuning):
    sp = make(tuning)
    pike = tuning.species_by_id("pike")
    assert sp.weights(0.0, {})["pike"] == pike.weight[0]
    assert sp.weights(1.0, {})["pike"] == pike.weight[1]
    assert sp.weights(0.5, {})["pike"] == pytest.approx(sum(pike.weight) / 2)


def test_special_and_junk_never_spawn_by_weight(tuning):
    w = make(tuning).weights(0.7, {})
    assert tuning.special.species not in w
    assert tuning.junk.species not in w


def test_per_species_cap(tuning):
    sp = make(tuning)
    cap = tuning.spawn.per_species_max
    w = sp.weights(0.5, {"minnow": cap})
    assert "minnow" not in w


def test_initial_population(tuning):
    fish = make(tuning).initial(0.0, 0.0)
    kinds = Counter(f.spec.kind for f in fish)
    assert kinds["junk"] == tuning.junk.count
    assert kinds["fish"] + kinds["trap"] == tuning.spawn.initial


def test_spawned_fish_are_in_the_water_and_their_zone(tuning):
    sp = make(tuning)
    p = tuning.pond
    for spec in tuning.species:
        for _ in range(30):
            f = sp.make(spec, 0.0)
            assert p.water_left < f.x < p.water_right and p.water_top < f.y < p.water_bottom
            r = math.hypot(f.x - p.rod_tip[0], f.y - p.rod_tip[1])
            assert f.band[0] - 1 <= r <= f.band[1] + 1


def test_no_respawn_when_pond_is_full(tuning):
    sp = make(tuning)
    full = [sp.make(tuning.species_by_id("perch"), 0.0) for _ in range(tuning.spawn.max)]
    new = []
    for i in range(60 * 30):
        new += sp.update(1 / 60, i / 60, i / 60, 0.2, False, full)
    assert not [f for f in new if f.spec.kind != "special"]


def test_frenzy_spawns_about_twice_as_fast(tuning):
    def count(frenzy):
        sp = make(tuning, seed=5)
        sp.special_at_s = None
        n = 0
        for i in range(60 * 120):
            n += len(sp.update(1 / 60, i / 60, i / 60, 0.5, frenzy, []))
        return n
    assert count(True) == pytest.approx(2 * count(False), rel=0.2)


def test_special_appears_at_most_once_in_its_window(tuning):
    appeared = 0
    lo, hi = tuning.special.window
    length = tuning.round.length_s
    for seed in range(200):
        sp = make(tuning, seed)
        times = []
        for i in range(int(length * 10)):
            t = i / 10
            for f in sp.update(0.1, t, t, t / length, False, []):
                if f.spec.kind == "special":
                    times.append(t)
        assert len(times) <= 1
        if times:
            appeared += 1
            assert lo * length - 0.2 <= times[0] <= hi * length + 0.2
    assert appeared / 200 == pytest.approx(tuning.special.chance, abs=0.08)


def test_no_scheduled_special_in_practice(tuning):
    assert make(tuning, practice=True).special_at_s is None
