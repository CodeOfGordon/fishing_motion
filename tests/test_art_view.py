"""The art view (M3) draws every round state and handles every GameEvent, headless."""
import time

import pygame
import pytest

from fishing.input.motion import MotionState
from fishing.render import palette as P
from fishing.render.art import ArtView
from fishing.render.hud import ViewInfo
from fishing.render.lure_line import line_style
from fishing.sim import events as ev
from fishing.sim import round as R
from fishing.sim.events import GameEvent
from fishing.sim.fish import COMMITTED
from fishing.ui.widgets import Fonts
from tests.sim_driver import DT, STEP_MS, Driver

ALL_STATES = {R.READY, R.CASTING, R.DRIFT, R.APPROACH, R.NIBBLE, R.BITE, R.HOOKED, R.FIGHT, R.CATCH,
              R.ESCAPE, R.OVER}
EVENT_KINDS = sorted(v for k, v in vars(ev).items() if k.isupper() and isinstance(v, str))


@pytest.fixture
def screen(tuning):
    pygame.init()
    surf = pygame.display.set_mode((tuning.window.width, tuning.window.height))
    yield surf
    pygame.quit()


@pytest.fixture
def view(tuning, screen):
    return ArtView(tuning, Fonts())


class ViewDriver(Driver):
    """A Driver that routes every event to the view, ticks it and draws each step."""

    def __init__(self, tuning, view, screen, seed=1, **kw):
        super().__init__(tuning, seed=seed, **kw)
        self.view, self.screen = view, screen
        self.drawn: set[str] = set()

    def step(self, n=1, events=()):
        out = []
        for i in range(n):
            o = super().step(1, events if i == 0 else ())
            for e in o:
                self.view.on_event(e, self.r)
            st = MotionState(self.host, self.reel, self.tilt)
            self.view.update(DT, st)
            info = ViewInfo("keyboard", 0.5 if self.r.state == R.READY else None, False, False, False, False,
                            self.host)
            self.view.draw(self.screen, self.r, st, info)
            self.drawn.add(self.r.state)
            out += o
        return out


def info(host=0.0, attract=False):
    return ViewInfo("keyboard", None, False, False, False, False, host, attract=attract)


def test_draws_every_state(tuning, view, screen):
    d = ViewDriver(tuning, view, screen)
    d.cast(0.6)  # READY, CASTING, DRIFT
    fish = d.r.spawner.make(tuning.species_by_id("perch"), d.r.now_s)
    fish.alpha, fish.mode = 1.0, COMMITTED
    fish.x, fish.y = d.r.lure.x + 60, d.r.lure.y
    d.r.fishes.append(fish)
    d.r.lure.owner = fish.id
    d.r._set_state(R.APPROACH)
    d.step(3)
    d.nibbling("perch")  # perch nibble twice before biting
    d.step(10)
    assert d.r.state == R.NIBBLE
    d.hooked("bass")  # BITE, HOOKED
    d.fight_well()  # FIGHT, CATCH
    d.step(5)
    d.hooked("pike")
    d.run_until(lambda: d.r.state == R.FIGHT)
    d.reel = 1.0
    d.run_until(lambda: d.r.state != R.FIGHT)  # reeling flat out into a pike snaps the line
    assert d.r.state == R.ESCAPE
    d.reel = 0.0
    d.r.time_left_s = 0.05
    d.run_until(lambda: d.r.state == R.OVER)
    d.step(3)
    assert d.drawn == ALL_STATES


@pytest.mark.parametrize("species", ["bait_thief", "old_boot", "lantern_koi", "minnow"])
def test_draws_special_bites_and_fights(tuning, view, screen, species):
    d = ViewDriver(tuning, view, screen, seed=3)
    d.biting(species)
    d.step(30)
    assert d.r.state in (R.BITE, R.DRIFT, R.ESCAPE)


def test_title_attract_draws_the_pond_only(tuning, view, screen):
    rnd = R.Round(tuning, practice=True, seed=12345)
    host = 0.0
    for _ in range(30):
        st = MotionState(host, 0.0, 0.0)
        rnd.step(DT, st, [], host)
        view.update(DT, st)
        view.draw(screen, rnd, st, info(host, attract=True))
        host += DT * 1000
    # the HUD's score sits top-left; in attract mode that corner is plain bank
    assert screen.get_at((24, 20))[:3] != P.TEXT


def test_handles_every_event_kind(tuning, view, screen):
    d = Driver(tuning, seed=2)
    d.hooked("perch")
    rnd = d.r
    st = MotionState(d.host, 0.3, -0.2)
    variants = [{}, {"reason": "snap"}, {"reason": "early"}, {"reason": "late"}, {"reason": "slack"},
                {"detail": {"kind": "trap"}}, {"detail": {"perfect": True}}, {"detail": {"x": 500, "y": 300}},
                {"value": 42.0}, {"value": -30.0}, {"bite_id": 3}]
    for kind in EVENT_KINDS:
        for extra in variants:
            view.on_event(GameEvent(kind, d.host, rnd.state, **extra), rnd)
        view.update(DT, st)
        view.draw(screen, rnd, st, info(d.host))
    assert len(view.fx.drops) <= P.DROP_MAX
    assert len(view.fx.ripples) <= P.RIPPLE_MAX
    assert len(view.fx.floaters) <= P.FLOATER_MAX


def test_effects_stay_bounded(tuning, view, screen):
    d = Driver(tuning, seed=4)
    d.biting("perch")
    for _ in range(200):
        for kind in (ev.BITE, ev.CATCH, ev.LURE_LAND, ev.FIGHT_RUN, ev.HOOKED):
            view.on_event(GameEvent(kind, d.host, d.r.state, value=10.0), d.r)
    assert len(view.fx.drops) <= P.DROP_MAX
    assert len(view.fx.ripples) <= P.RIPPLE_MAX
    assert len(view.fx.floaters) <= P.FLOATER_MAX
    for _ in range(240):  # everything fades away
        view.update(DT, MotionState(d.host, 0.0, 0.0))
    assert not view.fx.drops and not view.fx.ripples and not view.fx.floaters


def test_hook_flash_holds_the_animation_briefly(tuning, view, screen):
    d = Driver(tuning, seed=5)
    d.biting("perch")
    st = MotionState(d.host, 0.0, 0.0)
    view.update(DT, st)
    before = view.anim_t
    view.on_event(GameEvent(ev.HOOKED, d.host, R.BITE, detail={"perfect": False}), d.r)
    view.update(DT, st)
    assert view.anim_t == before  # hit-stop
    assert view.fx.flash > 0
    for _ in range(int(tuning.round.hit_stop_s / DT) + 2):
        view.update(DT, st)
    assert view.anim_t > before


def test_draws_on_a_plain_surface_without_a_display(tuning):
    pygame.init()
    try:
        v = ArtView(tuning, Fonts())
        surf = pygame.Surface((tuning.window.width, tuning.window.height))
        d = Driver(tuning, seed=6)
        d.biting("bass")
        st = MotionState(d.host, 0.0, 0.0)
        v.update(DT, st)
        v.draw(surf, d.r, st, info(d.host))
    finally:
        pygame.quit()


def test_draw_and_update_are_fast(tuning, view, screen):
    """8+ fish, an active fight and particles: well inside a 60 fps frame (measured ~2 ms on an M1 Pro)."""
    d = ViewDriver(tuning, view, screen, seed=7)
    d.hooked("catfish")
    d.run_until(lambda: d.r.state == R.FIGHT)
    for sid in ("perch", "bass", "rainbow_trout", "bluegill", "lantern_koi", "bait_thief", "pike", "minnow"):
        f = d.r.spawner.make(tuning.species_by_id(sid), d.r.now_s)
        f.alpha = 1.0
        d.r.fishes.append(f)
    times = []
    for i in range(120):
        fight = d.r.fight
        if fight is None:
            break
        d.reel = 1.0 if fight.tension < 0.7 else 0.3
        d.r.step(DT, MotionState(d.host, d.reel, d.tilt), [], d.host)
        d.host += DT * 1000
        if i % 15 == 0:
            view.on_event(GameEvent(ev.BITE, d.host, R.FIGHT), d.r)
        st = MotionState(d.host, d.reel, d.tilt)
        t0 = time.perf_counter()
        view.update(DT, st)
        view.draw(screen, d.r, st, info(d.host))
        times.append(time.perf_counter() - t0)
    times = times[10:]  # skip sprite-cache warm-up
    assert times and sum(times) / len(times) < 1 / 60


# ---------------------------------------------------------------------------- review fixes


def far_bank_bite(d, species="catfish"):
    """A full-power straight cast lands on the far bank (clamped to the water's top edge); then a real bite."""
    d.clear_pond()
    d.wait_armed()
    d.step(1, [d.ev("cast", 1.0)])
    d.run_until(lambda: d.r.state != R.CASTING)
    fish = d.r.spawner.make(d.t.species_by_id(species), d.r.now_s)
    fish.alpha = 1.0
    fish.x, fish.y = d.r.lure.x, d.r.lure.y
    d.r.fishes.append(fish)
    d.r.lure.owner = fish.id
    d.r._begin_nibbles(fish)
    d.r.nibble_times = []
    d.r.bite_at_ms = d.r.sim_ms
    d.run_until(lambda: d.r.state == R.BITE)


def test_bite_mark_stays_out_of_the_hud_band(tuning, view, screen):
    d = ViewDriver(tuning, view, screen, seed=8)
    far_bank_bite(d)
    assert d.r.lure.y <= tuning.pond.water_top + 1  # the bobber really is on the far bank
    d.step(30)  # through the pulse and the shake
    rect = view.bite_mark_rect
    assert rect is not None and rect.top >= P.POPUP_MIN_TOP
    assert rect.top > d.r.lure.y  # flipped under the bobber
    d2 = ViewDriver(tuning, view, screen, seed=8)
    d2.biting("bass")  # a mid-pond bite keeps the "!" above the bobber
    d2.step(5)
    assert view.bite_mark_rect.bottom < d2.r.lure.y


def test_hooked_popups_stay_out_of_the_hud_band(tuning, view, screen):
    d = ViewDriver(tuning, view, screen, seed=9)
    far_bank_bite(d)
    d.step(3)
    d.step(1, [d.ev("hook_set")])
    assert d.r.state == R.HOOKED
    assert view.fx.floaters
    for _ in range(int(P.FLOATER_LIFE_S / DT)):
        for surf, _shadow, x, y, *_ in view.fx.floaters:
            rect = surf.get_rect(center=(round(x), round(y)))
            assert rect.top >= P.POPUP_MIN_TOP
            assert P.POPUP_SIDE_PX <= rect.left and rect.right <= tuning.window.width - P.POPUP_SIDE_PX
        d.step(1)


def test_only_a_real_bite_pulls_the_line_taut(tuning, view, screen):
    colours = {}
    for species in ("bass", "bait_thief"):
        v = ArtView(tuning, Fonts())
        d = ViewDriver(tuning, v, screen, seed=10)
        d.biting(species)
        d.step(20)
        assert d.r.state == R.BITE
        colours[species] = line_style(v.tackle.tension, 0.0)[0]
    assert colours["bass"] != colours["bait_thief"]
    assert colours["bait_thief"] == line_style(0.0, 0.0)[0]  # the trap's line stays slack white


def test_line_eases_into_the_fight_instead_of_flashing_slack(tuning, view, screen):
    d = ViewDriver(tuning, view, screen, seed=11)
    d.hooked("perch")
    d.run_until(lambda: d.r.state == R.FIGHT)
    assert d.r.fight.tension < P.LINE_WHITE_UNTIL  # the sim starts the fight slack...
    assert view.tackle.tension > P.LINE_WHITE_UNTIL  # ...but the line is still visibly tight
    d.step(int(4 * P.LINE_EASE_DOWN_S / DT))
    assert view.tackle.tension == pytest.approx(d.r.fight.tension, abs=0.05)  # then it follows the sim
    d.reel = 1.0
    for _ in range(30):  # rises are instant: the line never shows less tension than the sim
        d.step(1)
        if d.r.state != R.FIGHT:
            break
        assert view.tackle.tension >= d.r.fight.tension - 1e-9


def test_danger_flicker_never_shows_the_slack_colour():
    slack = line_style(0.0, 0.0)[0]
    seen = set()
    for i in range(200):
        colour, width = line_style(0.95, i / 200)
        seen.add(colour)
        assert colour not in (slack, P.LURE_WHITE)
        assert width > P.LINE_WIDTH
    assert P.LINE_DANGER_HOT in seen and len(seen) == 2  # it does flicker


def test_fish_shadows_darken_with_depth(tuning, view):
    tip = tuning.pond.rod_tip
    near = view.fish.depth_alpha(tip[0], tip[1] - tuning.pond.shallow[0])
    deep = view.fish.depth_alpha(tip[0], tip[1] - tuning.pond.deep[0])
    corner = view.fish.depth_alpha(tuning.pond.water_left, tuning.pond.water_top)
    assert near == pytest.approx(P.FISH_SHADOW_SHALLOW_K)
    assert deep == pytest.approx(1.0) and corner == pytest.approx(1.0)


def test_catch_points_show_once_by_the_score(tuning, view, screen):
    d = ViewDriver(tuning, view, screen, seed=12)
    d.hooked("bass")
    view.fx.floaters.clear()
    d.fight_well()
    assert d.r.state == R.CATCH
    assert not view.fx.floaters  # no "+N" over the card: the card shows the points
    assert view.hud.score_pop is not None and view.hud.score_pop[0] == f"{d.r.card.catch.points:+d}"
    view.on_event(GameEvent(ev.ROUND_START, d.host, R.READY), d.r)
    assert view.hud.score_pop_age == float("inf")


def test_catch_card_is_built_once_and_fades_in_whole(tuning, view, screen):
    d = ViewDriver(tuning, view, screen, seed=13)
    d.hooked("rainbow_trout")
    d.fight_well()
    assert d.r.state == R.CATCH
    first = view.cards._surf
    assert first is not None and first.get_alpha() < 255  # still sliding in: panel and text fade together
    d.step(int(tuning.round.catch_card_s * P.CARD_SLIDE_IN / DT) + 2)
    assert view.cards._surf is first and first.get_alpha() == 255


def test_pond_wide_news_goes_in_the_hud_band(tuning, view, screen):
    d = ViewDriver(tuning, view, screen, seed=14)
    d.cast(0.4)
    view.fx.floaters.clear()
    for e in (GameEvent(ev.FRENZY, d.host, d.r.state),
              GameEvent(ev.SPECIAL_APPEARED, d.host, d.r.state, species=tuning.special.species)):
        view.on_event(e, d.r)
    assert not view.fx.floaters
    assert "appeared" in view.hud.announce and view.hud.announce_age == 0.0
    d.r.time_left_s = tuning.round.frenzy_s - 0.01
    d.step(3)  # draws the clock, FRENZY! pop and announcement without error
    d.step(int((P.ANNOUNCE_S + 0.1) / DT))
    assert view.hud.announce_age > P.ANNOUNCE_S


def test_cast_power_bar_clears_the_dock_and_rod(tuning, view):
    x, y, w, h = P.CAST_POWER_RECT
    bar = pygame.Rect(x, tuning.window.height - y, w, h)
    dock = view.pond.dock_rect()
    assert not bar.colliderect(dock.inflate(2 * P.HUD_PILL_PAD, 0))
    assert bar.right <= tuning.window.width


def test_sharp_turns_leave_a_ripple(tuning, view, screen):
    d = Driver(tuning, seed=15)
    d.clear_pond()
    fish = d.r.spawner.make(tuning.species_by_id("perch"), d.r.now_s)
    fish.alpha, fish.x, fish.y, fish.heading = 1.0, 400.0, 300.0, 0.0
    d.r.fishes.append(fish)
    st = MotionState(d.host, 0.0, 0.0)
    view.update(DT, st)
    view.draw(screen, d.r, st, info(d.host))
    before = len(view.fx.ripples)
    fish.heading = 0.01  # a gentle drift: nothing
    view.update(DT, st)
    view.draw(screen, d.r, st, info(d.host + STEP_MS))
    assert len(view.fx.ripples) == before
    fish.heading = 1.2  # a sharp turn
    view.update(DT, st)
    view.draw(screen, d.r, st, info(d.host + 2 * STEP_MS))
    assert len(view.fx.ripples) == before + 1
    fish.heading = 2.4  # another straight away: rate-limited
    view.update(DT, st)
    view.draw(screen, d.r, st, info(d.host + 3 * STEP_MS))
    assert len(view.fx.ripples) <= before + 1
