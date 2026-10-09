"""Milestone-3 view: the art pass. Same interface as PlainView (fishing/render/plain.py).

Layers, back to front: water (pre-rendered depth gradient + scrolling caustics),
fish shadows, ripples and glints, the bank / dock / lily pads (pre-rendered), reeds,
tackle (line, rod, bobber), droplets and pop-up text; then the HUD and cards, which
don't shake. Effects are driven by GameEvents through on_event().

Pop-ups near the bobber ("!", HOOKED!, PERFECT!) flip below it when the bobber is on the
far bank, so they never sit under the HUD band. Pond-wide news (the Koi, frenzy) goes in
the HUD band instead of over the water.
"""
from __future__ import annotations

import math

import pygame

from fishing.config import Tuning
from fishing.input.motion import MotionState
from fishing.render import hud
from fishing.render import palette as P
from fishing.render.art_hud import ArtHud
from fishing.render.catch_card import Cards
from fishing.render.fish_art import FishArt
from fishing.render.fx import Effects
from fishing.render.hud import ViewInfo
from fishing.render.lure_line import Tackle
from fishing.render.pond import PondArt
from fishing.sim import events as ev
from fishing.sim import round as R
from fishing.sim.events import GameEvent
from fishing.ui.widgets import Fonts

OUTLINE = ((-2, 0), (2, 0), (0, -2), (0, 2), (3, 3))  # the "!": outline offsets + drop shadow


def popup_y(anchor_y: float, height: float, lift: float) -> tuple[float, bool]:
    """Centre y for a pop-up `lift` px above anchor_y, or below it (flipped=True) when above
    would reach into the HUD band."""
    y = anchor_y - lift
    if y - height / 2 < P.POPUP_MIN_TOP:
        return anchor_y + lift, True
    return y, False


class ArtView:
    def __init__(self, tuning: Tuning, fonts: Fonts) -> None:
        self.t = tuning
        self.fonts = fonts
        size = (tuning.window.width, tuning.window.height)
        self.pond = PondArt(tuning.pond, size)
        self.fx = Effects(self.pond.colour_at, screen_w=size[0])
        self.fish = FishArt(tuning, on_turn=lambda x, y: self.fx.ripple(x, y, "turn"))
        self.tackle = Tackle(tuning, self.pond, self.fx)
        self.hud = ArtHud(tuning, fonts)
        self.cards = Cards(fonts)
        self.anim_t = 0.0  # animation clock: stops during the hit-stop
        self._last_draw_t = 0.0
        self.crank = 0.0
        self._bang: list[tuple[pygame.Surface, pygame.Surface]] = []  # the "!" over a real bite, pre-scaled
        self.bite_mark_rect: pygame.Rect | None = None  # where the "!" went last frame (None: not shown)

    # ------------------------------------------------------------------ events
    def on_event(self, e: GameEvent, rnd: R.Round) -> None:
        k = e.kind
        lure = rnd.lure
        x, y = lure.x, lure.y
        fx = self.fx
        if k == ev.LURE_LAND:
            lx, ly = e.detail.get("x", x), e.detail.get("y", y)
            fx.ripple(lx, ly, "land")
            fx.ripple(lx, ly, "nibble", 1.6)
            fx.splash(lx, ly, "land")
        elif k == ev.NIBBLE:
            self.tackle.on_nibble()
            self.fish.nibble()
            fx.ripple(x, y, "nibble")
        elif k == ev.BITE:
            self.tackle.on_bite(e.bite_id)
            if e.detail.get("kind") == "trap":
                fx.ripple(x, y, "tug")
                fx.splash(x, y, "release")
            else:
                fx.ripple(x, y, "bite")
                fx.ripple(x, y, "bite_slow")
                fx.splash(x, y, "bite")
                fx.shake(P.SHAKE_BITE_PX)
        elif k == ev.HOOKED:
            fx.start_flash(self.t.round.hit_stop_s)
            fx.splash(x, y, "hooked")
            self._hooked_popups(x, y, bool(e.detail.get("perfect")))
        elif k == ev.FIGHT_RUN:
            fx.ripple(x, y, "run")
            fx.splash(x, y, "run")
        elif k == ev.CATCH:
            fx.ripple(x, y, "catch")
            fx.splash(x, y, "catch")
            self.hud.on_catch(e.value or 0)  # the points pop by the score; the card shows them big
        elif k == ev.ESCAPE:
            self.tackle.on_escape(e.reason)
            fx.ripple(x, y, "escape")
            if e.reason == "snap":
                fx.shake(P.SHAKE_SNAP_PX)
                fx.splash(x, y, "run")
        elif k == ev.BITE_RELEASED:
            fx.ripple(x, y, "escape")
            fx.splash(x, y, "release")
        elif k == ev.SPOOK:
            fx.ripple(x, y, "nibble", 1.4)
        elif k == ev.SPECIAL_APPEARED:
            try:
                name = self.t.species_by_id(e.species).name
            except KeyError:
                name = "special fish"
            self.hud.on_announce(f"A {name} appeared!")
        elif k == ev.ROUND_START:
            fx.clear()
            self.hud.clear()
        # FRENZY pops the HUD's own label; every other kind (state, cast, commit, ticks,
        # bonus, debug, ...) has no effect

    def _hooked_popups(self, x: float, y: float, perfect: bool) -> None:
        """HOOKED! (and PERFECT! under it) above the bobber, or below it on the far bank."""
        big = self.fonts.get(P.CARD_TITLE_SIZE)
        h = big.render("HOOKED!", True, P.GOLD).get_height()
        hy, _ = popup_y(y, h, P.BITE_MARK_LIFT)
        min_hy = P.POPUP_MIN_TOP + h / 2
        self.fx.floater(big, "HOOKED!", x, hy, P.GOLD, min_y=min_hy)
        if perfect:  # keeps its gap under HOOKED! even once HOOKED! stops rising
            self.fx.floater(self.fonts.get(P.HUD_FONT_SIZE), "PERFECT!", x, hy + P.FLOATER_SUB_DY, P.GOOD,
                            min_y=min_hy + P.FLOATER_SUB_DY)

    # ------------------------------------------------------------------ ticking
    def update(self, frame_s: float, st: MotionState) -> None:
        self.crank += st.reel_rate * 2 * math.pi * P.CRANK_TURNS_PER_S * frame_s
        self.hud.update(frame_s)
        frozen = self.fx.frozen
        self.fx.update(frame_s)
        if frozen:
            return  # hit-stop: the pond holds still for a moment
        self.anim_t += frame_s
        self.pond.update(frame_s)
        self.tackle.update(frame_s)

    # ------------------------------------------------------------------ drawing
    def draw(self, screen: pygame.Surface, rnd: R.Round, st: MotionState, info: ViewInfo) -> None:
        self.pond.prepare()
        self.fish.prepare()
        t = self.anim_t
        dt = max(0.0, t - self._last_draw_t)
        self._last_draw_t = t

        self.pond.draw_water(screen, t)
        if not info.attract:
            self.tackle.layout(rnd, st, t, dt)
        self._draw_fish(screen, rnd, t, dt, info.attract)
        self.fx.draw_ripples(screen)
        self.pond.draw_glints(screen)
        self.pond.draw_shore(screen)
        self.pond.draw_reeds(screen, t)
        if info.attract:
            self.bite_mark_rect = None
            return

        self.tackle.draw(screen, rnd, st, t, self.crank, info.charging)
        self.fx.draw_drops(screen)
        dx, dy = self.fx.shake_offset()
        if dx or dy:
            screen.scroll(dx, dy)
        self.fx.draw_flash(screen)
        self.bite_mark_rect = self._draw_bite_mark(screen, rnd, t, dx, dy)  # text stays crisp through the flash
        self.fx.draw_floaters(screen, dx, dy)

        self.hud.draw(screen, rnd, info, st.reel_rate, st.tilt, self.crank)
        if rnd.card is not None:
            total = (self.t.round.catch_card_s if rnd.card.kind == "catch" else self.t.round.escape_card_s) * 1000
            progress = 1 - (rnd.card.until_ms - rnd.sim_ms) / total
            if rnd.card.kind == "catch":
                self.cards.draw_catch_card(screen, rnd, progress, t)
            else:
                self.cards.draw_escape_card(screen, rnd, progress)
        hud.draw_status(screen, self.fonts, rnd, info)

    def _draw_fish(self, screen: pygame.Surface, rnd: R.Round, t: float, dt: float, attract: bool) -> None:
        # the bait thief drags the bobber sideways: keep it under the bobber
        offset = (0.0, 0.0) if attract else self.tackle.fish_offset
        self.fish.draw(screen, rnd, t, dt, offset)

    def _draw_bite_mark(self, screen: pygame.Surface, rnd: R.Round, t: float, dx: int,
                        dy: int) -> pygame.Rect | None:
        """A big "!" over a real bite (not the bait thief's sideways tug); under the bobber on the far bank."""
        owner = rnd.owner
        if rnd.state != R.BITE or owner is None or owner.spec.kind == "trap":
            return None
        n = P.BITE_MARK_FRAMES
        if not self._bang:
            font = self.fonts.get(P.BITE_MARK_SIZE)
            img, shadow = font.render("!", True, P.BAD), font.render("!", True, P.TEXT_SHADOW)
            for i in range(n):
                scale = 1 + P.BITE_MARK_PULSE * (2 * i / (n - 1) - 1)
                self._bang.append((pygame.transform.smoothscale_by(img, scale),
                                   pygame.transform.smoothscale_by(shadow, scale)))
        pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi * P.BITE_MARK_PULSE_HZ)
        img, shadow = self._bang[min(n - 1, int(pulse * n))]
        biggest = self._bang[-1][0].get_height()  # flip on the largest frame, so the "!" doesn't hop
        y, _ = popup_y(rnd.lure.y, biggest, P.BITE_MARK_LIFT)
        rect = img.get_rect(center=(round(rnd.lure.x + dx), round(y + dy)))
        for ox, oy in OUTLINE:
            screen.blit(shadow, rect.move(ox, oy))
        screen.blit(img, rect)
        return rect
