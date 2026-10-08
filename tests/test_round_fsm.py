import math

import pytest

from fishing.sim import events as ev
from fishing.sim import round as R
from tests.sim_driver import DT, STEP_MS, Driver, bot_round


@pytest.fixture
def d(tuning):
    return Driver(tuning)


# ---------------------------------------------------------------- casting
def test_cast_lands_at_distance_set_by_strength(d, tuning):
    d.clear_pond()
    d.cast(0.5)
    assert d.r.state == R.DRIFT
    c = tuning.cast
    land = d.kinds(ev.LURE_LAND)[0]
    assert land.value == pytest.approx(c.min_dist + c.dist_per_strength * 0.5, abs=1)
    cast = [e for e in d.kinds(ev.CAST) if e.accepted][0]
    assert cast.strength == 0.5


def test_full_cast_is_clamped_to_the_water(d, tuning):
    d.clear_pond()
    d.tilt = 1.0
    d.step(30)
    d.cast(1.0)
    p = tuning.pond
    assert p.water_left <= d.r.lure.x <= p.water_right
    assert p.water_top <= d.r.lure.y <= p.water_bottom


def test_aim_uses_tilt_from_before_the_flick(d, tuning):
    d.clear_pond()
    d.tilt = 0.5
    d.wait_armed()
    d.step(20)
    d.tilt = -1.0  # the flick itself rotates the rod
    d.step(1, [d.ev("cast", 0.5)])
    cast = [e for e in d.kinds(ev.CAST) if e.accepted][0]
    assert cast.detail["aim_deg"] == pytest.approx(0.5 * tuning.cast.aim_max_deg, abs=0.5)


def test_cast_too_soon_after_ready_is_ignored(d):
    d.step(2)
    d.step(1, [d.ev("cast", 0.8)])
    assert d.r.state == R.READY
    ignored = [e for e in d.kinds(ev.CAST) if e.accepted is False]
    assert ignored and ignored[0].reason == "not_armed:too_soon"
    assert d.r.stats.casts_ignored == 1


def test_cast_while_reeling_is_ignored(d):
    d.wait_armed()
    d.reel = 0.6
    d.step(3)
    d.step(1, [d.ev("cast", 0.8)])
    assert d.r.state == R.READY
    assert d.kinds(ev.CAST)[-1].reason == "not_armed:reeling"


def test_cast_outside_ready_is_logged_and_ignored(d):
    d.clear_pond()
    d.cast(0.4)
    d.step(1, [d.ev("cast", 0.9)])
    assert d.r.state == R.DRIFT
    assert d.kinds(ev.CAST)[-1].accepted is False
    assert d.kinds(ev.CAST)[-1].reason.startswith("state:")


def test_empty_retrieve_returns_to_ready(d):
    d.clear_pond()
    d.cast(0.3)
    d.reel = 1.0
    d.run_until(lambda: d.r.state == R.READY)
    assert d.kinds(ev.EMPTY_RETRIEVE)
    assert d.r.stats.empty_retrieves == 1


def test_tilt_steers_the_lure(d):
    d.clear_pond()
    d.cast(0.6)
    x0 = d.r.lure.x
    d.tilt = 1.0
    d.reel = 0.3
    d.step(30)
    assert d.r.lure.x > x0 + 20


# ---------------------------------------------------------------- fish & nibbles
def test_fish_commits_to_a_slow_lure_in_front_of_it(d, tuning):
    d.clear_pond()
    d.cast(0.5)
    spec = tuning.species_by_id("minnow")
    fish = d.r.spawner.make(spec, d.r.now_s)
    fish.alpha = 1.0
    fish.x, fish.y = d.r.lure.x, d.r.lure.y - 40
    fish.heading = math.pi / 2  # facing down the screen, toward the lure
    d.r.fishes.append(fish)
    d.reel = 0.2
    d.run_until(lambda: d.r.state in (R.APPROACH, R.NIBBLE, R.BITE), 2000)
    assert d.r.lure.owner == fish.id


def test_reeling_hard_during_nibbles_spooks_the_fish(d, tuning):
    d.nibbling("catfish")
    d.step(int(tuning.hook.nibble_spook_grace_s / DT) + 1)
    d.reel = 0.9
    d.run_until(lambda: d.r.state != R.NIBBLE, 200)
    assert d.r.state == R.DRIFT
    assert any(e.reason == "reeling" for e in d.kinds(ev.SPOOK))


def test_nibbles_then_bite(d):
    d.nibbling("perch")  # 2 nibbles
    d.run_until(lambda: d.r.state == R.BITE, 400)
    assert len(d.kinds(ev.NIBBLE)) == 2
    assert len(d.kinds(ev.BITE)) == 1


# ---------------------------------------------------------------- hook-set judging
def test_hook_during_nibble_is_early(d):
    d.nibbling("perch")
    d.r.streak = 3
    d.step(5)
    d.step(1, [d.ev("hook_set")])
    assert d.r.state == R.DRIFT
    assert d.kinds(ev.HOOK_ATTEMPT)[-1].reason == "early"
    assert any(e.reason == "early" for e in d.kinds(ev.ESCAPE))
    assert d.r.streak == 0
    assert d.r.lure.owner is None


def test_hook_while_reeling_in_nibble_is_ignored_not_early(d, tuning):
    d.nibbling("catfish")
    d.reel = tuning.hook.nibble_ignore_hook_reel + 0.1
    d.step(3)
    d.step(1, [d.ev("hook_set")])
    assert d.r.state == R.NIBBLE
    assert d.kinds(ev.HOOK_ATTEMPT)[-1].reason == "ignored"


def test_cast_gesture_during_nibble_is_not_early(d):
    d.nibbling("perch")
    d.step(5)
    d.step(1, [d.ev("cast", 0.9)])
    assert d.r.state == R.NIBBLE


def test_hook_in_window_is_hooked_with_reaction_time(d):
    d.biting("perch")
    d.step(18)  # ~300 ms after the bite
    d.step(1, [d.ev("hook_set")])
    assert d.r.state == R.HOOKED
    attempt = d.kinds(ev.HOOK_ATTEMPT)[-1]
    assert attempt.reason == "hooked"
    assert attempt.value == pytest.approx(18 * STEP_MS, abs=STEP_MS + 0.1)


def test_cast_gesture_counts_in_bite_window_when_forgiving(d):
    d.biting("perch")
    d.step(5)
    d.step(1, [d.ev("cast", 0.9)])
    assert d.r.state == R.HOOKED
    assert d.kinds(ev.HOOK_ATTEMPT)[-1].detail["raw"] == "cast"


def test_cast_gesture_in_bite_window_ignored_when_strict(tuning):
    d = Driver(tuning, forgiving_hook=False)
    d.biting("perch")
    d.step(5)
    d.step(1, [d.ev("cast", 0.9)])
    assert d.r.state == R.BITE


def test_window_expiry_is_late_and_steals_the_bait(d, tuning):
    d.biting("perch")
    d.r.streak = 2
    window = d.r.bite_window_ms + tuning.hook.grace_ms + tuning.hook.delivery_margin_ms
    d.step(int(window / STEP_MS) + 2)
    assert d.r.state == R.ESCAPE
    assert d.kinds(ev.ESCAPE)[-1].reason == "late"
    assert d.r.streak == 0
    d.run_until(lambda: d.r.state == R.READY, 400)


def test_grace_edge_judged_on_event_time(tuning):
    from fishing.input.motion import MotionEvent

    for offset_ms, expect in ((-5, "hooked"), (+5, "late")):
        d = Driver(tuning)
        d.biting("bass")
        end = d.bite_host_ms() + d.r.bite_window_ms + tuning.hook.grace_ms
        d.run_until(lambda: d.host >= end + 10)  # inside the delivery margin
        assert d.r.state == R.BITE
        d.step(1, [MotionEvent("hook_set", end + offset_ms, 1.0)])
        assert d.kinds(ev.HOOK_ATTEMPT)[-1].reason == expect
        assert d.r.state == (R.HOOKED if expect == "hooked" else R.ESCAPE)


def test_late_arriving_jerk_from_the_last_nibble_is_early(d):
    d.nibbling("minnow")  # 0 nibbles: the bite comes after a short pause
    d.run_until(lambda: d.r.state == R.BITE, 200)
    bite_host = d.bite_host_ms()
    d.step(4)  # detector latency: the event arrives ~70 ms after it happened
    from fishing.input.motion import MotionEvent
    d.step(1, [MotionEvent("hook_set", bite_host - 20, 1.0)])
    assert d.kinds(ev.HOOK_ATTEMPT)[-1].reason == "early"
    assert d.r.state == R.DRIFT


def test_two_gestures_in_one_frame_are_both_judged(d):
    d.biting("perch")
    d.step(6)
    d.step(1, [d.ev("hook_set", ago_ms=8), d.ev("hook_set")])
    results = [e.reason for e in d.kinds(ev.HOOK_ATTEMPT)]
    assert results[-2:] == ["hooked", "ignored"]
    assert d.kinds(ev.HOOK_ATTEMPT)[-1].detail["why"] == "already_hooked"


def test_hook_with_no_fish_is_no_bite(d):
    d.clear_pond()
    d.cast(0.5)
    d.step(1, [d.ev("hook_set")])
    assert d.kinds(ev.HOOK_ATTEMPT)[-1].reason == "no_bite"
    assert d.r.state == R.DRIFT


# ---------------------------------------------------------------- bites and the buzzer
def test_exactly_one_bite_event_per_bite_id(tuning):
    for seed in range(4):
        d = bot_round(tuning, seed)
        ids = [e.bite_id for e in d.kinds(ev.BITE)]
        assert ids == list(range(1, len(ids) + 1))
        assert d.r.stats.bites == len(ids)


def test_trap_fish_lets_go_without_penalty(d, tuning):
    d.biting("bait_thief")
    d.r.streak = 2
    h = tuning.hook
    d.step(int((d.r.bite_window_ms + h.grace_ms + h.delivery_margin_ms) / STEP_MS) + 2)
    assert d.r.state == R.DRIFT
    assert d.kinds(ev.BITE_RELEASED)
    assert d.r.streak == 2
    assert not d.kinds(ev.ESCAPE)


def test_hooking_the_trap_costs_points_and_streak(d):
    d.hooked("bait_thief")
    d.r.streak = 3
    d.fight_well()
    assert d.r.state == R.CATCH
    assert d.r.score == -30
    assert d.r.streak == 0


def test_bite_ack_is_counted_against_the_last_bite(d):
    d.biting("perch")
    d.step(3)
    d.step(1, [d.ev("bite_ack")])
    ack = d.kinds(ev.BITE_ACK)[-1]
    assert ack.accepted and ack.bite_id == 1
    assert d.r.stats.acks == 1


# ---------------------------------------------------------------- fight and catch
def test_good_fight_lands_the_fish_and_scores(d):
    d.hooked("perch")
    d.fight_well()
    assert d.r.state == R.CATCH
    catch = d.kinds(ev.CATCH)[-1]
    assert catch.species == "perch" and catch.value > 0
    assert d.r.score == catch.value
    assert d.r.streak == 1
    d.run_until(lambda: d.r.state == R.READY, 400)


def test_reeling_flat_out_snaps_a_strong_fish(d):
    d.hooked("pike")
    d.reel = 1.0
    d.run_until(lambda: d.r.state != R.HOOKED and d.r.state != R.FIGHT, 2000)
    assert d.kinds(ev.ESCAPE)[-1].reason == "snap"


def test_not_reeling_shakes_the_hook(d):
    d.hooked("perch")
    d.reel = 0.0
    d.run_until(lambda: d.r.state == R.ESCAPE, 2000)
    assert d.kinds(ev.ESCAPE)[-1].reason == "slack"


# ---------------------------------------------------------------- the clock
def test_timer_ends_round_in_ready(d, tuning):
    d.r.time_left_s = 0.05
    d.step(10)
    assert d.r.state == R.OVER
    assert d.kinds(ev.ROUND_END)


def test_timer_ends_round_while_drifting(d):
    d.clear_pond()
    d.cast(0.5)
    d.r.time_left_s = 0.02
    d.step(3)
    assert d.r.state == R.OVER


def test_nibble_plays_out_after_time_up(d):
    d.nibbling("perch")
    d.r.time_left_s = 0.02
    d.run_until(lambda: d.r.state != R.NIBBLE, 400)
    assert d.r.state == R.BITE  # the bite still happens (and still buzzes)


def test_fight_continues_into_overtime_then_is_capped(d, tuning):
    d.hooked("catfish")
    d.r.time_left_s = 0.02
    d.reel = 0.35  # never lands, never snaps, never slack
    d.run_until(lambda: d.r.state not in (R.HOOKED, R.FIGHT), 10_000)
    assert d.r.overtime_s >= tuning.round.overtime_cap_s - 0.1 or d.r.state in (R.CATCH, R.ESCAPE)


def test_practice_has_no_clock(tuning):
    d = Driver(tuning, practice=True)
    d.step(600)
    assert d.r.time_left_s is None
    assert not d.r.time_up


def test_clock_ticks_in_the_last_seconds(d, tuning):
    d.r.time_left_s = tuning.round.warn_s + 0.5
    d.step(int(3 / DT))
    assert [e.value for e in d.kinds(ev.CLOCK_TICK)][:3] == [10, 9, 8]


# ---------------------------------------------------------------- disconnects
def test_disconnect_freezes_the_round(d):
    d.nibbling("perch")
    sim_before = d.r.sim_ms
    d.stale = True
    d.step(120, [d.ev("hook_set")])
    assert d.r.sim_ms == sim_before
    assert d.r.state == R.NIBBLE  # BITE is never entered while disconnected
    assert d.kinds(ev.DISCONNECT)
    assert d.kinds(ev.HOOK_ATTEMPT)[-1].detail["why"] == "disconnected"


def test_reconnect_resumes_after_countdown(d, tuning):
    d.clear_pond()
    d.stale = True
    d.step(10)
    d.stale = False
    frames = int(tuning.round.resume_countdown_s / DT)
    d.step(frames - 2)
    assert d.r.frozen
    d.step(4)
    assert not d.r.frozen
    assert d.kinds(ev.RECONNECT)


# ---------------------------------------------------------------- whole rounds
def test_bot_rounds_finish_with_sane_stats(tuning):
    for seed in range(6):
        d = bot_round(tuning, seed)
        r = d.r
        assert r.finished
        assert r.stats.casts >= 4
        assert len(r.stats.catches) >= 2
        assert sum(c.points for c in r.stats.catches) == r.score
        assert len(d.kinds(ev.ROUND_END)) == 1
