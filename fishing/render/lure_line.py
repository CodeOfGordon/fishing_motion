"""Tackle: the rod (bends with tension, tip follows tilt), the line (a sagging Bezier
that goes white -> amber -> red), the bobber, the cast arc and the aim arrow."""
from __future__ import annotations

import math

import pygame

from fishing.config import Tuning
from fishing.input.motion import MotionState
from fishing.render import palette as P
from fishing.render.fx import Effects
from fishing.render.pond import PondArt, mix, smooth
from fishing.sim import round as R

TAU = 2 * math.pi
HANDLE_FRAC = 0.22  # the dark handle covers this much of the rod from the butt
SNAP_WAVES = 9  # wiggle of the broken line: radians along its length...
SNAP_WHIP_RAD_S = 30  # ...and how fast it whips


def bezier(a, c, b, n: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(n + 1):
        u = i / n
        v = 1 - u
        pts.append((v * v * a[0] + 2 * v * u * c[0] + u * u * b[0], v * v * a[1] + 2 * v * u * c[1] + u * u * b[1]))
    return pts


def line_style(tension: float, t: float) -> tuple[tuple[int, ...], int]:
    """(colour, width): white -> amber -> red with tension. Near a snap it flickers between
    red and a hot pink-red, drawn wider; it never flashes white, the slack colour."""
    T = max(0.0, tension)
    if T <= P.LINE_AMBER_AT:
        col = mix(P.LINE, P.LINE_TAUT, smooth((T - P.LINE_WHITE_UNTIL) / (P.LINE_AMBER_AT - P.LINE_WHITE_UNTIL)))
    else:
        col = mix(P.LINE_TAUT, P.LINE_DANGER, (T - P.LINE_AMBER_AT) / (1 - P.LINE_AMBER_AT))
    width = P.LINE_WIDTH
    if T >= P.LINE_FLICKER_AT:
        width += 1
        if int(t * P.LINE_FLICKER_HZ * 2) % 2:
            col, width = P.LINE_DANGER_HOT, P.LINE_WIDTH + P.LINE_HOT_EXTRA_W
    return col, width


def draw_line_pts(screen: pygame.Surface, pts, colour, width: int) -> None:
    """A line with a dark under-stroke, so it reads over the bright shallows too."""
    pygame.draw.lines(screen, P.LINE_UNDER, False, pts, width + P.LINE_UNDER_EXTRA_W)
    pygame.draw.lines(screen, colour, False, pts, width)


class Bobber:
    """Where and how the bobber is drawn this frame."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.scale = 1.0
        self.sink = 0.0  # 0 floating .. 1 fully under
        self.height = 0.0  # fake height above the water (cast flight, dangling)
        self.visible = False
        self.ring = True  # waterline ring

    @property
    def pos(self) -> tuple[float, float]:
        return self.x, self.y - self.height


class Tackle:
    def __init__(self, tuning: Tuning, pond: PondArt, fx: Effects) -> None:
        self.t = tuning
        self.pond = pond
        self.fx = fx
        self.bobber = Bobber()
        self.nibble_age = math.inf
        self.snap_age = math.inf
        self.trap_dir = 1
        self.escape_reason = ""
        self.emit: dict[str, float] = {}
        self.tension = 0.0  # visual tension this frame: rises at once, eases down
        self.tip = (0.0, 0.0)
        self.base = (0.0, 0.0)
        self.fish_offset = (0.0, 0.0)  # shift for the hooked fish (the bait thief drags sideways)

    # ------------------------------------------------------------------ events
    def on_nibble(self) -> None:
        self.nibble_age = 0.0

    def on_escape(self, reason: str) -> None:
        self.escape_reason = reason
        if reason == "snap":
            self.snap_age = 0.0

    def on_bite(self, bite_id: int | None) -> None:
        self.trap_dir = 1 if (bite_id or 0) % 2 else -1

    def update(self, dt: float) -> None:
        self.nibble_age += dt
        self.snap_age += dt

    # ------------------------------------------------------------------ layout
    def _visual_tension(self, rnd: R.Round, st: MotionState) -> float:
        s = rnd.state
        if s == R.FIGHT and rnd.fight is not None:
            return rnd.fight.tension
        if s == R.HOOKED:
            return P.LINE_HOOKED_TENSION
        if s == R.BITE:
            # only a real bite pulls the line taut and orange; the bait thief's tug leaves it slack
            return P.LINE_TRAP_TENSION if self._is_trap_bite(rnd) else P.LINE_BITE_TENSION
        if s in (R.DRIFT, R.APPROACH, R.NIBBLE):
            return P.LINE_IDLE_TENSION + P.LINE_REEL_TENSION * st.reel_rate
        if s == R.CASTING:
            return P.LINE_AMBER_AT * 0.5
        return 0.0

    def _is_trap_bite(self, rnd: R.Round) -> bool:
        owner = rnd.owner
        return rnd.state == R.BITE and owner is not None and owner.spec.kind == "trap"

    def layout(self, rnd: R.Round, st: MotionState, t: float, dt: float) -> None:
        """Work out the rod, the bobber and the line end for this frame (and run the emitters)."""
        p = self.t.pond
        tip0 = p.rod_tip
        lure = rnd.lure
        s = rnd.state
        target = self._visual_tension(rnd, st)
        if s in (R.READY, R.OVER) or target >= self.tension:
            self.tension = target  # rises are instant: the red warning never lags
        else:  # falls ease, so the hooked -> fight hand-over doesn't flash a slack line
            self.tension += (target - self.tension) * (1 - math.exp(-dt / P.LINE_EASE_DOWN_S))
        in_state = max(0.0, (rnd.sim_ms - rnd.state_since_ms) / 1000.0)

        self.base = (tip0[0] + P.ROD_BASE_DX, P.ROD_BASE_Y)
        tip = [tip0[0] + st.tilt * P.ROD_TILT_PX, p.water_bottom - P.ROD_TIP_OVER_WATER]
        if s not in (R.READY, R.OVER, R.CASTING):  # bend toward the lure
            dx, dy = lure.x - tip[0], lure.y - tip[1]
            d = math.hypot(dx, dy) or 1.0
            pull = min(1.0, self.tension) * P.ROD_BEND_PX * 0.5
            tip[0] += dx / d * pull
            tip[1] += dy / d * pull
        self.tip = (tip[0], tip[1])

        b = self.bobber
        b.visible, b.ring, b.scale, b.sink, b.height = True, True, 1.0, 0.0, 0.0
        self.fish_offset = (0.0, 0.0)
        bob = P.BOBBER_BOB_PX * math.sin(t * TAU * P.BOBBER_BOB_HZ)
        if s == R.OVER or (s == R.ESCAPE and self.escape_reason == "snap"):
            b.visible = False
            b.x, b.y = lure.x, lure.y
        elif s == R.READY:
            b.x, b.y = self.tip[0], self.tip[1] + P.BOBBER_HANG_PX
            b.x += math.sin(t * TAU * P.BOBBER_BOB_HZ) * P.BOBBER_SWING_PX
            b.ring = False
        elif s == R.CASTING:
            pr = lure.flight_progress
            tx, ty = lure.target
            b.x = self.tip[0] + (tx - self.tip[0]) * pr
            b.y = self.tip[1] + (ty - self.tip[1]) * pr
            c = self.t.cast
            reach = math.hypot(tx - tip0[0], ty - tip0[1]) / (c.min_dist + c.dist_per_strength)
            b.height = math.sin(math.pi * pr) * P.CAST_ARC_PX * (P.CAST_ARC_MIN + (1 - P.CAST_ARC_MIN) * min(1.0, reach))
            b.scale = 1 + P.CAST_GROW * math.sin(math.pi * pr)
            b.ring = False
        else:
            b.x, b.y = lure.x, lure.y + bob
            owner = rnd.owner
            if s == R.NIBBLE and self.nibble_age < P.NIBBLE_TWITCH_S and owner is not None:
                k = math.sin(math.pi * self.nibble_age / P.NIBBLE_TWITCH_S)
                b.x -= math.cos(owner.heading) * P.NIBBLE_TWITCH_PX * k
                b.y -= math.sin(owner.heading) * P.NIBBLE_TWITCH_PX * k
                b.scale = 1 - P.NIBBLE_DIP * k
            elif s == R.BITE and self._is_trap_bite(rnd):
                dx, dy = lure.x - self.tip[0], lure.y - self.tip[1]
                d = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / d * self.trap_dir, dx / d * self.trap_dir
                drag = P.TRAP_DRAG_PX * smooth(in_state / P.TRAP_DRAG_S)
                jit = P.TRAP_JITTER_PX * math.sin(t * TAU * P.TRAP_JITTER_HZ[0])
                ox, oy = nx * (drag + jit), ny * (drag + jit) + jit * 0.4
                b.x += ox
                b.y += oy
                self.fish_offset = (ox, oy)
                self._every("wake", P.TRAP_WAKE_S, dt, lambda: self.fx.ripple(b.x, b.y, "wake"))
            elif s in (R.BITE, R.HOOKED, R.FIGHT):
                sink = smooth(in_state / P.BITE_SINK_S) if s == R.BITE else 1.0
                b.scale = 1 - (1 - P.BITE_SUNK_SCALE) * sink
                b.sink = P.BITE_SUNK_FADE * sink
                b.ring = False
                b.y -= bob
                if s == R.BITE:
                    b.x += math.sin(t * TAU * P.BITE_MARK_PULSE_HZ * 2) * sink
                    self._every("tug", P.BITE_TUG_S, dt, lambda: self.fx.ripple(b.x, b.y, "tug"))
                elif s == R.FIGHT and rnd.fight is not None and rnd.fight.running:
                    self._every("thrash", P.FIGHT_THRASH_S, dt, lambda: self.fx.ripple(b.x, b.y, "thrash"))
            elif s in (R.DRIFT, R.APPROACH) and lure.speed > P.DRIFT_WAKE_SPEED:
                self._every("drift", P.DRIFT_WAKE_S, dt, lambda: self.fx.ripple(b.x, b.y + 2, "wake"))

    def _every(self, key: str, period: float, dt: float, fn) -> None:
        acc = self.emit.get(key, period) + dt
        if acc >= period:
            acc = 0.0
            fn()
        self.emit[key] = acc

    # ------------------------------------------------------------------ drawing
    def draw(self, screen: pygame.Surface, rnd: R.Round, st: MotionState, t: float, crank: float,
             charging: float | None) -> None:
        s = rnd.state
        if s == R.READY:
            self._draw_aim(screen, st.tilt, charging)
        b = self.bobber
        if s == R.CASTING:  # the lure's shadow on the water
            col = mix(P.CAST_SHADOW, self.pond.colour_at(b.x, b.y), 0.35)
            r = P.BOBBER_R * 0.9
            pygame.draw.ellipse(screen, col, pygame.Rect(b.x - r, b.y - r * 0.6, 2 * r, 1.2 * r))
        if b.visible:
            self._draw_line(screen, self.tip, b.pos, self.tension, t)
        elif s == R.ESCAPE:
            self._draw_snapped(screen, t)
        self._draw_rod(screen, crank)
        if b.visible:
            self._draw_bobber(screen)

    def _draw_line(self, screen, a, b, tension: float, t: float) -> None:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1:
            return
        nx, ny = -dy / length, dx / length
        if nx < 0:
            nx, ny = -nx, -ny
        sag = length * P.LINE_SAG * (1 - min(1.0, max(0.0, tension)))
        sag *= 1 + P.LINE_SAG_SWAY * math.sin(t * TAU * P.LINE_SAG_SWAY_HZ)
        c = ((a[0] + b[0]) / 2 + nx * sag, (a[1] + b[1]) / 2 + ny * sag)
        pts = bezier(a, c, b, P.LINE_SEGMENTS)
        col, width = line_style(tension, t)
        draw_line_pts(screen, pts, col, width)

    def _draw_snapped(self, screen, t: float) -> None:
        """The broken end whips, then hangs from the rod tip."""
        k = max(0.0, 1 - self.snap_age / P.LINE_SNAP_S) if self.snap_age < math.inf else 0.0
        a = self.tip
        b = self.bobber
        dx, dy = b.x - a[0], b.y - a[1]  # the broken end trails out toward where the fish was
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        pts = [a]
        n = 10
        for i in range(1, n + 1):
            u = i / n
            wig = math.sin(u * SNAP_WAVES + t * SNAP_WHIP_RAD_S) * P.LINE_SNAP_WIGGLE_PX * (0.3 + k) * u
            reach = u * P.LINE_SNAP_STUB_PX * (1 - 0.4 * k)
            pts.append((a[0] + ux * reach - uy * wig, a[1] + uy * reach + ux * wig + u * u * P.LINE_SNAP_WIGGLE_PX))
        draw_line_pts(screen, pts, P.LINE, P.LINE_WIDTH)

    def _draw_rod(self, screen, crank: float) -> None:
        base, tip = self.base, self.tip
        dx, dy = tip[0] - base[0], tip[1] - base[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        b = self.bobber
        side = 1.0
        if b.visible:  # bend toward the line
            side = 1.0 if (b.x - tip[0]) * nx + (b.y - tip[1]) * ny > 0 else -1.0
        bend = min(1.0, self.tension) * P.ROD_BEND_PX * side
        c = ((base[0] + tip[0]) / 2 + nx * bend, (base[1] + tip[1]) / 2 + ny * bend)
        pts = bezier(base, c, tip, P.ROD_SEGMENTS)
        w0, w1 = P.ROD_WIDTH
        n = len(pts) - 1
        for i in range(n):
            w = round(w0 + (w1 - w0) * i / n)
            pygame.draw.line(screen, P.ROD_DARK, pts[i], pts[i + 1], w + 2)
        for i in range(n):
            w = round(w0 + (w1 - w0) * i / n)
            col = P.ROD_HANDLE if i / n < HANDLE_FRAC else P.ROD
            pygame.draw.line(screen, col, pts[i], pts[i + 1], w)
        rx, ry = pts[round(P.ROD_REEL_AT * n)]
        pygame.draw.circle(screen, P.ROD_REEL_DARK, (round(rx), round(ry)), P.ROD_REEL_R + 1)
        pygame.draw.circle(screen, P.ROD_REEL, (round(rx), round(ry)), P.ROD_REEL_R - 1)
        hx, hy = rx + math.cos(crank) * P.ROD_REEL_R, ry + math.sin(crank) * P.ROD_REEL_R
        pygame.draw.line(screen, P.ROD_REEL_DARK, (rx, ry), (hx, hy), 3)
        pygame.draw.circle(screen, P.LURE_WHITE, (round(hx), round(hy)), 3)
        pygame.draw.circle(screen, P.ROD_DARK, (round(tip[0]), round(tip[1])), 2)

    def _draw_bobber(self, screen) -> None:
        b = self.bobber
        x, y = b.pos
        r = max(2.0, P.BOBBER_R * b.scale)
        water = self.pond.colour_at(b.x, b.y)
        ix, iy = round(x), round(y)
        afloat = b.sink < P.BOBBER_AFLOAT_SINK
        if b.ring and afloat:
            pygame.draw.circle(screen, mix(P.BOBBER_RING, water, 0.35), (ix, iy + 1), round(r + P.BOBBER_RING_GROW), 1)
        if afloat and b.height <= 0:
            pygame.draw.circle(screen, mix(P.BOBBER_SHADOW, water, 0.4), (ix + 2, iy + 2), round(r))
        white = mix(P.LURE_WHITE, water, b.sink)
        red = mix(P.LURE, water, b.sink)
        pygame.draw.aacircle(screen, white, (ix, iy), r)
        pygame.draw.aacircle(screen, red, (ix, iy), r, 0, True, True, False, False)
        pygame.draw.circle(screen, mix(P.ROD_DARK, water, b.sink), (ix, iy), max(1, round(r * 0.25)))
        if afloat:
            pygame.draw.circle(screen, mix(P.LURE_WHITE, red, 0.3), (round(x - r * 0.4), round(y - r * 0.45)),
                               max(1, round(r * 0.22)))

    def _draw_aim(self, screen, tilt: float, charging: float | None) -> None:
        c = self.t.cast
        p = self.t.pond
        tip0 = p.rod_tip
        aim = math.radians(tilt * c.aim_max_deg)
        dx, dy = math.sin(aim), -math.cos(aim)
        far = self._clamp(tip0, dx, dy, c.min_dist + c.dist_per_strength)
        near = min(c.min_dist, far)
        # the aim range fan: a dotted arc at the shortest cast
        span = math.radians(c.aim_max_deg)
        steps = max(2, round(2 * span * c.min_dist / P.AIM_DOT_PX))
        for i in range(steps + 1):
            a = -span + 2 * span * i / steps
            px, py = tip0[0] + math.sin(a) * c.min_dist, tip0[1] - math.cos(a) * c.min_dist
            pygame.draw.circle(screen, P.AIM_DIM, (round(px), round(py)), 1)
        # dots along the possible landing range
        d = near
        while d < far - P.AIM_HEAD_PX:
            px, py = tip0[0] + dx * d, tip0[1] + dy * d
            pygame.draw.circle(screen, P.AIM_COLOUR, (round(px), round(py)), P.AIM_DOT_R)
            pygame.draw.circle(screen, P.TEXT_SHADOW, (round(px), round(py)), P.AIM_DOT_R, 1)
            d += P.AIM_DOT_PX
        hx, hy = tip0[0] + dx * far, tip0[1] + dy * far
        bx, by = hx - dx * P.AIM_HEAD_PX, hy - dy * P.AIM_HEAD_PX
        head = [(hx, hy), (bx - dy * P.AIM_HEAD_PX * 0.6, by + dx * P.AIM_HEAD_PX * 0.6),
                (bx + dy * P.AIM_HEAD_PX * 0.6, by - dx * P.AIM_HEAD_PX * 0.6)]
        pygame.draw.polygon(screen, P.AIM_COLOUR, head)
        pygame.draw.polygon(screen, P.TEXT_SHADOW, head, 2)
        if charging is not None:  # keyboard: where this cast would land
            dist = self._clamp(tip0, dx, dy, c.min_dist + c.dist_per_strength * max(0.0, min(1.0, charging)))
            tx, ty = tip0[0] + dx * dist, tip0[1] + dy * dist
            pygame.draw.circle(screen, P.TEXT_SHADOW, (round(tx), round(ty)), P.AIM_TARGET_R + 1, 3)
            pygame.draw.circle(screen, P.WARN, (round(tx), round(ty)), P.AIM_TARGET_R, 2)
            pygame.draw.circle(screen, P.WARN, (round(tx), round(ty)), 2)

    def _clamp(self, tip, dx: float, dy: float, dist: float) -> float:
        """Distance along the aim ray that stays on the water (as the round clamps casts)."""
        p = self.t.pond
        limit = dist
        if dx > 1e-9:
            limit = min(limit, (p.water_right - tip[0]) / dx)
        elif dx < -1e-9:
            limit = min(limit, (p.water_left - tip[0]) / dx)
        if dy < -1e-9:
            limit = min(limit, (p.water_top - tip[1]) / dy)
        return limit
