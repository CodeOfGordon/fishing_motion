"""Menus built from rows: actions, choices, sliders, toggles and a text field.

Navigation: arrow keys / Enter / Esc, the mouse, or the rod (tilt to move,
hook-set to select).
"""
from __future__ import annotations

from typing import Callable

import pygame

from fishing.input.motion import HOOK_SET, MotionEvent, MotionState
from fishing.render import palette

NAV = {"tilt": 0.6, "repeat_s": 0.45}  # set from [menu] in tuning.toml by configure_nav()


def configure_nav(tilt: float, repeat_s: float) -> None:
    NAV["tilt"] = tilt
    NAV["repeat_s"] = repeat_s


class Fonts:
    def __init__(self) -> None:
        self._cache: dict[int, pygame.font.Font] = {}

    def get(self, size: int) -> pygame.font.Font:
        if size not in self._cache:
            self._cache[size] = pygame.font.Font(None, size)
        return self._cache[size]


class Row:
    label = ""
    editing = False

    def text(self) -> str:
        return self.label

    def left(self) -> None:
        pass

    def right(self) -> None:
        pass

    def activate(self) -> None:
        self.right()

    def on_text(self, e: pygame.event.Event) -> bool:
        return False


class ActionRow(Row):
    def __init__(self, label: str, action: Callable[[], None], hint: str = "") -> None:
        self.label = label
        self.action = action
        self.hint = hint

    def activate(self) -> None:
        self.action()

    def right(self) -> None:
        pass


class ChoiceRow(Row):
    def __init__(self, label: str, options: list[tuple[str, object]], get: Callable[[], object],
                 set_: Callable[[object], None]) -> None:
        self.label = label
        self.options = options
        self.get = get
        self.set = set_

    def _index(self) -> int:
        values = [v for _, v in self.options]
        return values.index(self.get()) if self.get() in values else 0

    def text(self) -> str:
        return f"{self.label}:  < {self.options[self._index()][0]} >"

    def left(self) -> None:
        self.set(self.options[(self._index() - 1) % len(self.options)][1])

    def right(self) -> None:
        self.set(self.options[(self._index() + 1) % len(self.options)][1])


class SliderRow(Row):
    def __init__(self, label: str, get: Callable[[], float], set_: Callable[[float], None],
                 lo: float, hi: float, step: float, fmt: str = "{:.2f}") -> None:
        self.label, self.get, self.set = label, get, set_
        self.lo, self.hi, self.step, self.fmt = lo, hi, step, fmt

    def text(self) -> str:
        v = self.get()
        frac = (v - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0
        filled = round(frac * 10)
        return f"{self.label}:  {'■' * filled}{'□' * (10 - filled)}  {self.fmt.format(v)}"

    def _nudge(self, d: float) -> None:
        v = round((self.get() + d) / self.step) * self.step
        self.set(max(self.lo, min(self.hi, v)))

    def left(self) -> None:
        self._nudge(-self.step)

    def right(self) -> None:
        self._nudge(self.step)


class ToggleRow(Row):
    def __init__(self, label: str, get: Callable[[], bool], set_: Callable[[bool], None]) -> None:
        self.label, self.get, self.set = label, get, set_

    def text(self) -> str:
        return f"{self.label}:  {'ON' if self.get() else 'off'}"

    def left(self) -> None:
        self.set(not self.get())

    def right(self) -> None:
        self.set(not self.get())


class TextRow(Row):
    def __init__(self, label: str, get: Callable[[], str], set_: Callable[[str], None],
                 max_len: int = 64, placeholder: str = "") -> None:
        self.label, self.get, self.set = label, get, set_
        self.max_len = max_len
        self.placeholder = placeholder
        self.editing = False
        self.buffer = ""

    def text(self) -> str:
        if self.editing:
            return f"{self.label}:  {self.buffer}_"
        return f"{self.label}:  {self.get() or self.placeholder}"

    def activate(self) -> None:
        if self.editing:
            self.set(self.buffer.strip())
            self.editing = False
            pygame.key.stop_text_input()
        else:
            self.buffer = self.get()
            self.editing = True
            pygame.key.start_text_input()

    def on_text(self, e: pygame.event.Event) -> bool:
        if not self.editing:
            return False
        if e.type == pygame.TEXTINPUT:
            self.buffer = (self.buffer + e.text)[: self.max_len]
            return True
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.buffer = self.buffer[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.activate()
            elif e.key == pygame.K_ESCAPE:
                self.editing = False
                pygame.key.stop_text_input()
            return True
        return False


class Menu:
    def __init__(self, rows: list[Row], on_move: Callable[[], None] | None = None,
                 on_select: Callable[[], None] | None = None) -> None:
        self.rows = rows
        self.index = 0
        self.on_move = on_move or (lambda: None)
        self.on_select = on_select or (lambda: None)
        self._rects: list[pygame.Rect] = []
        self._tilt_hold = 0.0

    @property
    def editing(self) -> bool:
        return any(r.editing for r in self.rows)

    def move(self, d: int) -> None:
        self.index = (self.index + d) % len(self.rows)
        self.on_move()

    def handle_event(self, e: pygame.event.Event) -> bool:
        """Returns True if the menu used the event."""
        editing = next((r for r in self.rows if r.editing), None)
        if editing is not None:
            if e.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
                editing.on_text(e)
                return True
            if e.type == pygame.MOUSEMOTION:
                return False
            if e.type == pygame.MOUSEBUTTONDOWN:
                editing.activate()  # a click commits the edit, then acts as usual
        row = self.rows[self.index]
        if row.on_text(e):
            return True
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_w):
                self.move(-1)
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.move(1)
            elif e.key in (pygame.K_LEFT, pygame.K_a):
                row.left()
                self.on_move()
            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                row.right()
                self.on_move()
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.on_select()
                row.activate()
            else:
                return False
            return True
        if e.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self._rects):
                if r.collidepoint(e.pos) and i != self.index:
                    self.index = i
                    self.on_move()
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self._rects):
                if r.collidepoint(e.pos):
                    self.index = i
                    self.on_select()
                    self.rows[i].activate()
                    return True
        return False

    def handle_motion(self, dt: float, st: MotionState, events: list[MotionEvent], rod: bool) -> None:
        """Rod navigation: tilt moves the selection, a hook-set selects."""
        if not rod or self.editing:
            return
        if abs(st.tilt) > NAV["tilt"]:
            self._tilt_hold -= dt
            if self._tilt_hold <= 0:
                self.move(1 if st.tilt > 0 else -1)
                self._tilt_hold = NAV["repeat_s"]
        else:
            self._tilt_hold = 0.0
        if any(e.kind == HOOK_SET for e in events):
            self.on_select()
            self.rows[self.index].activate()

    def draw(self, surface: pygame.Surface, fonts: Fonts, centre_x: int, top: int,
             size: int = palette.MENU_FONT_SIZE, spacing: int = palette.MENU_SPACING,
             max_rows: int | None = None) -> None:
        """Draw the rows (scrolling to keep the selection visible if max_rows is set)."""
        font = fonts.get(size)
        count = len(self.rows) if max_rows is None else min(max_rows, len(self.rows))
        first = max(0, min(self.index - count // 2, len(self.rows) - count))
        hidden = pygame.Rect(-100, -100, 0, 0)
        self._rects = [hidden] * len(self.rows)
        for slot, i in enumerate(range(first, first + count)):
            row = self.rows[i]
            selected = i == self.index
            colour = palette.MENU_SELECTED if selected else palette.TEXT
            img = font.render(("> " if selected else "  ") + row.text(), True, colour)
            rect = img.get_rect(midtop=(centre_x, top + slot * spacing))
            if selected:
                pygame.draw.rect(surface, palette.MENU_HIGHLIGHT, rect.inflate(24, 8), border_radius=8)
            surface.blit(img, rect)
            self._rects[i] = rect.inflate(40, spacing - rect.height)
        if first > 0:
            surface.blit(font.render("...", True, palette.TEXT_DIM), (centre_x - 10, top - spacing // 2))
        if first + count < len(self.rows):
            surface.blit(font.render("...", True, palette.TEXT_DIM), (centre_x - 10, top + count * spacing - 8))
