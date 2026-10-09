"""Regression tests for problems found in code review."""
import csv
import json
import math

import pygame
import pytest

from fishing.app import App, MIXER_ARGS, parse_args
from fishing.highscores import HighScores
from fishing.input.motion import MotionEvent, MotionState, now_ms
from fishing.loop import FixedStep, deliver, step_hosts
from fishing.render.debug_overlay import RateMeter
from fishing.scenes.play import PlayScene
from fishing.scenes.rod_test import CASTS, HOOKS, RodTestScene
from fishing.session_log import SessionLog
from fishing.sim import events as ev
from fishing.sim import round as R
from fishing.sim.events import GameEvent
from fishing.sim.fish import LEAVING, WANDER
from tests.sim_driver import DT, Driver

STEP_MS = DT * 1000


# ---------------------------------------------------------------- timing across long frames
def play_frames(d: Driver, frames_ms: list[float], events_by_frame: dict[int, list[MotionEvent]]):
    """Step the round exactly like PlayScene: FixedStep + deliver + step_hosts."""
    stepper = FixedStep(DT, d.t.loop.max_frame_s, d.t.loop.max_steps)
    inbox: list[MotionEvent] = []
    for i, fms in enumerate(frames_ms):
        d.host += fms
        inbox += events_by_frame.get(i, [])
        steps = stepper.advance(fms / 1000)
        if steps:
            hosts = iter(step_hosts(d.host, fms / 1000, steps))
            st = MotionState(d.host, d.reel, d.tilt)
            inbox = deliver(steps, inbox, lambda evs: d.log.extend(d.r.step(DT, st, evs, next(hosts))))


@pytest.mark.parametrize("hitch_ms", [16.7, 120, 280, 400])
def test_on_time_jerk_is_hooked_even_across_a_long_frame(tuning, hitch_ms):
    """A jerk made during a long frame is judged at its real time, not at the frame's end."""
    d = Driver(tuning)
    d.biting("perch")
    bite_host = d.bite_host_ms()
    before = STEP_MS + 50  # two ordinary frames after the bite (no time dropped)
    react = before + hitch_ms / 2  # the jerk happens in the middle of the long frame
    jerk = MotionEvent("hook_set", bite_host + react, 1.0)
    play_frames(d, [STEP_MS, 50, hitch_ms], {2: [jerk]})
    attempt = d.kinds(ev.HOOK_ATTEMPT)[-1]
    assert attempt.reason == "hooked"
    assert attempt.value == pytest.approx(react, abs=STEP_MS + 1)


def test_step_hosts_cover_the_frame():
    assert step_hosts(1000.0, 0.03, 2) == [970.0, 985.0]


# ---------------------------------------------------------------- acks
def test_ack_right_after_send_is_matched(tuning):
    d = Driver(tuning)
    d.biting("perch")
    sent = d.host
    d.r.mark_bite_sent(d.r.bite_id, sent)
    d.step(1, [MotionEvent("bite_ack", sent + 5, 0.0)])
    ack = d.kinds(ev.BITE_ACK)[-1]
    assert ack.accepted and ack.value == pytest.approx(5)
    assert d.r.stats.acks == 1 and d.r.last_ack_ms == pytest.approx(5)


def test_duplicate_ack_counts_once(tuning):
    d = Driver(tuning)
    d.biting("perch")
    d.r.mark_bite_sent(d.r.bite_id, d.host)
    d.step(1, [d.ev("bite_ack"), d.ev("bite_ack")])
    assert [a.reason for a in d.kinds(ev.BITE_ACK)] == ["", "duplicate"]
    assert d.r.stats.acks == 1


def test_ack_counts_while_frozen(tuning):
    d = Driver(tuning)
    d.biting("perch")
    d.r.mark_bite_sent(d.r.bite_id, d.host)
    d.stale = True
    d.step(5)
    d.step(1, [MotionEvent("bite_ack", d.host - 50, 0.0)])
    assert d.r.stats.acks == 1


def test_events_after_the_round_ends_are_logged(tuning):
    d = Driver(tuning)
    d.r.time_left_s = 0.02
    d.step(5)
    assert d.r.finished
    d.step(1, [d.ev("cast", 0.5), d.ev("hook_set")])
    reasons = [(e.kind, e.detail.get("why")) for e in d.log[-2:]]
    assert reasons == [(ev.CAST, "state:OVER"), (ev.HOOK_ATTEMPT, "state:OVER")]


# ---------------------------------------------------------------- nibbles, bites, fish
def test_lure_holds_still_while_a_fish_nibbles(tuning):
    d = Driver(tuning)
    d.nibbling("catfish")
    x, y = d.r.lure.x, d.r.lure.y
    d.reel, d.tilt = 0.25, 1.0
    d.step(30)
    assert d.r.state == R.NIBBLE
    assert (d.r.lure.x, d.r.lure.y) == (x, y)


def test_debug_bite_refused_while_frozen(tuning):
    d = Driver(tuning, practice=True)
    d.clear_pond()
    d.cast(0.5)
    d.stale = True
    d.step(3)
    d.r.out = []
    assert d.r.force_bite() is False
    assert not [e for e in d.r.out if e.kind == ev.BITE]


def test_early_hook_without_a_bite_has_no_bite_id(tuning):
    d = Driver(tuning)
    d.hooked("minnow")
    d.fight_well()
    d.run_until(lambda: d.r.state == R.READY, 400)
    d.nibbling("perch")
    d.step(5)
    d.step(1, [d.ev("hook_set")])
    attempt = d.kinds(ev.HOOK_ATTEMPT)[-1]
    assert attempt.reason == "early" and attempt.bite_id is None


def test_a_wary_fish_out_of_range_does_not_hide_a_bold_one(tuning):
    d = Driver(tuning, seed=3)
    d.clear_pond()
    d.cast(0.6)
    lure = d.r.lure
    ai = tuning.fish_ai
    trout = d.r.spawner.make(tuning.species_by_id("rainbow_trout"), d.r.now_s)
    minnow = d.r.spawner.make(tuning.species_by_id("minnow"), d.r.now_s)
    w_trout = tuning.species_by_id("rainbow_trout").wariness
    r_trout = ai.notice_radius * (1 - ai.notice_wariness_shrink * w_trout)
    for f, dist in ((trout, r_trout + 3), (minnow, r_trout + 20)):
        f.alpha = 1.0
        f.x, f.y = lure.x, lure.y - dist
        f.heading = math.pi / 2  # facing the lure
        d.r.fishes.append(f)
    for _ in range(1200):  # fish held in place: only the commit rule is under test
        d.r._tick_drift(DT)
        if d.r.lure.owner is not None:
            break
    assert d.r.lure.owner == minnow.id


def test_running_fish_stays_on_the_water(tuning):
    d = Driver(tuning)
    d.clear_pond()
    d.cast(1.0)
    fish = d.r.spawner.make(tuning.species_by_id("pike"), d.r.now_s)
    fish.alpha, fish.x, fish.y = 1.0, d.r.lure.x, d.r.lure.y
    d.r.fishes.append(fish)
    d.r.lure.owner = fish.id
    d.r._begin_nibbles(fish)
    d.r.nibble_times, d.r.bite_at_ms = [], d.r.sim_ms
    d.run_until(lambda: d.r.state == R.BITE)
    d.step(1, [d.ev("hook_set")])
    d.reel = 0.1
    p = tuning.pond
    for _ in range(3000):
        d.step()
        assert p.water_top <= d.r.lure.y <= p.water_bottom
        assert p.water_left <= d.r.lure.x <= p.water_right
        if d.r.state not in (R.HOOKED, R.FIGHT):
            break


def test_trap_release_is_counted(tuning):
    d = Driver(tuning)
    d.biting("bait_thief")
    h = tuning.hook
    d.step(int((d.r.bite_window_ms + h.grace_ms + h.delivery_margin_ms) / STEP_MS) + 2)
    assert d.r.stats.released == 1 and d.r.summary()["released"] == 1


def test_spooked_fish_leaves_and_splash_sets_global_cooldown(tuning):
    d = Driver(tuning)
    d.nibbling("perch")
    fish = d.r.owner
    d.step(5)
    d.step(1, [d.ev("hook_set")])  # early: the fish bolts and leaves
    d.step(int(tuning.fish_ai.flee_s / DT) + 2)
    assert fish.mode == LEAVING
    d2 = Driver(tuning)
    d2.wait_armed()
    near = d2.r.spawner.make(tuning.species_by_id("minnow"), d2.r.now_s)
    near.alpha = 1.0
    d2.r.fishes = [near]
    d2.step(1, [d2.ev("cast", 0.5)])
    d2.run_until(lambda: d2.r.lure.flight_progress > 0.97)
    target = d2.r.lure.target
    near.x, near.y = target[0] + 10, target[1]  # right where the lure is about to splash down
    d2.run_until(lambda: d2.r.state == R.DRIFT)
    assert d2.kinds(ev.SCATTER)
    assert d2.r.global_flee_until_s > d2.r.now_s


def test_reeling_to_the_dock_during_approach_loses_the_fish(tuning):
    d = Driver(tuning)
    d.clear_pond()
    d.cast(0.0)
    fish = d.r.spawner.make(tuning.species_by_id("catfish"), d.r.now_s)
    fish.alpha, fish.x, fish.y = 1.0, d.r.lure.x, d.r.lure.y - 200
    fish.mode = "committed"
    d.r.fishes.append(fish)
    d.r.lure.owner = fish.id
    d.r._set_state(R.APPROACH)
    d.reel = 1.0
    d.run_until(lambda: d.r.state == R.READY, 600)
    assert any(e.reason == "dock" for e in d.kinds(ev.LOST_INTEREST))
    assert fish.cooldown_until > d.r.now_s


@pytest.mark.parametrize("state", ["CASTING", "APPROACH", "BITE", "HOOKED", "CATCH", "ESCAPE"])
def test_round_always_ends_when_time_runs_out(tuning, state):
    d = Driver(tuning)
    if state == "CASTING":
        d.wait_armed()
        d.step(1, [d.ev("cast", 0.5)])
    elif state == "APPROACH":
        d.clear_pond()
        d.cast(0.5)
        fish = d.r.spawner.make(tuning.species_by_id("catfish"), d.r.now_s)
        fish.alpha, fish.x, fish.y, fish.mode = 1.0, d.r.lure.x, d.r.lure.y - 100, "committed"
        d.r.fishes.append(fish)
        d.r.lure.owner = fish.id
        d.r._set_state(R.APPROACH)
    elif state == "BITE":
        d.biting("perch")
    elif state == "HOOKED":
        d.hooked("perch")
    elif state == "CATCH":
        d.hooked("minnow")
        d.fight_well()
    elif state == "ESCAPE":
        d.hooked("perch")
        d.reel = 0.0
        d.run_until(lambda: d.r.state == R.ESCAPE, 2000)
    assert d.r.state == getattr(R, state)
    d.r.time_left_s = 0.01
    d.reel = 0.5 if state == "HOOKED" else 0.0
    d.run_until(lambda: d.r.finished, 60 * 60)
    assert len(d.kinds(ev.ROUND_END)) == 1


def test_scripted_round_logs_every_kind_the_pass_criteria_need(tuning, tmp_path):
    d = Driver(tuning)
    d.nibbling("perch")
    d.run_until(lambda: d.kinds(ev.NIBBLE), 200)
    d.step(1, [d.ev("hook_set")])  # early escape after a real nibble
    d.run_until(lambda: d.r.state == R.DRIFT)
    d.reel = 1.0
    d.run_until(lambda: d.r.state == R.READY, 2000)  # empty retrieve
    d.reel = 0.0
    d.nibbling("catfish")
    d.step(int(tuning.hook.nibble_spook_grace_s / DT) + 1)
    d.reel = 0.9
    d.run_until(lambda: d.r.state != R.NIBBLE, 200)  # spook
    d.reel = 0.0
    d.biting("perch")
    d.r.mark_bite_sent(d.r.bite_id, d.host)
    d.step(1, [d.ev("bite_ack")])
    log = SessionLog(tmp_path)
    for e in d.log:
        log.event(e)
    log.close()
    with open(log.path, newline="") as f:
        kinds = {r["event"] for r in csv.DictReader(f)}
    for k in (ev.ESCAPE, ev.NIBBLE, ev.SPOOK, ev.EMPTY_RETRIEVE, ev.BITE_ACK, ev.HOOK_ATTEMPT, ev.BITE):
        assert k in kinds


# ---------------------------------------------------------------- logging and persistence
def test_strength_keeps_three_decimals(tmp_path):
    log = SessionLog(tmp_path)
    log.event(GameEvent(ev.CAST, 1.0, "READY", accepted=True, strength=0.537))
    log.close()
    with open(log.path, newline="") as f:
        assert next(csv.DictReader(f))["strength"] == "0.537"


def test_high_scores_ignore_bad_entries(tmp_path):
    path = tmp_path / "hs.json"
    good = {"name": "A", "score": 100, "medal": "", "best_fish": "", "date": "", "input": "", "difficulty": ""}
    path.write_text(json.dumps([good, {**good, "score": "250"}, {**good, "score": None}, "junk"]))
    assert [e.score for e in HighScores(path).entries] == [100]


def test_rate_meter_counts_samples_not_frames():
    m = RateMeter()
    t, seq = 0.0, 0
    for _ in range(120):  # 62.5 Hz stream read at 60 fps
        t += 1000 / 60
        seq = int(t / 16)
        m.update(seq, t)
    assert m.hz == pytest.approx(62.5, abs=2)
    for _ in range(90):  # the stream stops
        t += 1000 / 60
        m.update(seq, t)
    assert m.hz == 0.0


# ---------------------------------------------------------------- app level
@pytest.fixture
def app(tmp_path):
    pygame.mixer.pre_init(*MIXER_ARGS)
    pygame.init()
    a = App(parse_args(["--windowed"]), data_dir=tmp_path / "data", log_dir=tmp_path / "logs")
    yield a
    a.shutdown()
    pygame.quit()


def rows(app):
    with open(app.log.path, newline="") as f:
        return list(csv.DictReader(f))


def test_resume_click_is_not_a_gesture(app):
    app.scene = PlayScene(app)
    app.run(max_frames=5)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
    app.run(max_frames=2)
    rect = app.scene.pause_menu._rects[0]
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    app.run(max_frames=10)
    assert not app.scene.paused
    assert not [r for r in rows(app) if r["event"] == "hook_attempt"]


def test_practice_exit_writes_round_end(app):
    app.scene = PlayScene(app, practice=True)
    app.run(max_frames=5)
    app.scene._quit()
    app.run(max_frames=2)
    ends = [r for r in rows(app) if r["event"] == "round_end"]
    assert len(ends) == 1 and ends[0]["mode"] == "practice" and ends[0]["reason"] == "quit"


def test_poll_error_falls_back_without_touching_settings(app):
    class Broken:
        def poll(self):
            raise OSError("cable gone")

        def drain_events(self):
            return []

        def send(self, msg):
            pass

        def close(self):
            pass

    app.settings.input_source = "rod"
    app.source, app.source_name = Broken(), "rod"
    app.run(max_frames=2)
    assert app.source_name == "keyboard"
    assert app.settings.input_source == "rod"
    assert "cable gone" in app.source_error


class FakeRod:
    """A MotionSource the test feeds by hand."""

    def __init__(self):
        self.sent, self.queue, self.connected, self.seq = [], [], True, 0

    def poll(self):
        self.seq += 1
        return MotionState(now_ms(), 0.0, 0.0, self.connected, self.seq)

    def drain_events(self):
        out, self.queue = self.queue, []
        return out

    def send(self, msg):
        self.sent.append((msg, now_ms()))

    def close(self):
        pass


def test_rod_test_counts_an_ack_that_arrives_after_the_hook_set(app):
    rod = FakeRod()
    app.source, app.source_name, app.connecting = rod, "rod", False
    scene = RodTestScene(app)
    app.scene = scene
    scene._start()
    scene.phase, scene.trial = HOOKS, 0
    scene._next_hook_prompt(now_ms() - 5000)  # prompt is due now
    app.run(max_frames=2)
    assert rod.sent
    sent = scene.sent_ms
    rod.queue = [MotionEvent("hook_set", sent + 180, 1.0), MotionEvent("bite_ack", sent + 250, 0.0)]
    app.run(max_frames=2)
    assert scene.hook_hits == [pytest.approx(180)]
    assert scene.acks[0] == pytest.approx(250)


def test_rod_test_pauses_while_disconnected_and_logs_wrong_gestures(app):
    rod = FakeRod()
    app.source, app.source_name, app.connecting = rod, "rod", False
    scene = RodTestScene(app)
    app.scene = scene
    scene._start()
    app.run(max_frames=2)
    rod.queue = [MotionEvent("hook_set", now_ms(), 1.0)]  # wrong kind during the cast part
    app.run(max_frames=2)
    rod.connected = False
    prompt_before = scene.prompt_at
    app.run(max_frames=30)
    assert scene.phase == CASTS and scene.cast_hits == []
    assert scene.prompt_at > prompt_before  # the trial waits for the rod
    events = [r["event"] for r in rows(app)]
    assert "rodtest_gesture" in events and "rodtest_disconnect" in events
