"""Headless bot rounds: the balance targets the plan set for the tuning."""
import statistics

import pytest

from fishing.sim.bot import NOVICE, SKILLED, play_round

N = 24


@pytest.fixture(scope="module")
def skilled(tuning):
    return [play_round(tuning, SKILLED, seed) for seed in range(N)]


@pytest.fixture(scope="module")
def novice(tuning):
    return [play_round(tuning, NOVICE, seed) for seed in range(N)]


def test_rounds_finish_and_add_up(skilled, novice):
    for r in skilled + novice:
        assert r.finished
        assert sum(c.points for c in r.stats.catches) == r.score


def test_skilled_players_catch_about_eight_to_twelve(skilled):
    assert 7 <= statistics.mean(len(r.stats.catches) for r in skilled) <= 13


def test_skill_matters(skilled, novice):
    assert statistics.median(r.score for r in skilled) > 1.5 * statistics.median(r.score for r in novice)


def test_pond_shows_variety(skilled):
    assert statistics.mean(len(r.seen_species) for r in skilled) >= 6


def test_special_fish_is_a_prize_not_the_whole_round(tuning):
    """About a third of a Gold score: typically under 40% of a round, never over half a Gold."""
    shares, koi_points = [], []
    for seed in range(120):
        r = play_round(tuning, SKILLED, seed)
        koi = [c.points for c in r.stats.catches if c.kind == "special"]
        koi_points += koi
        if koi and r.score > 0:
            shares.append(sum(koi) / r.score)
    assert shares, "the special fish should be catchable"
    assert statistics.mean(shares) < 0.4
    assert max(koi_points) <= 0.5 * tuning.medals.gold
