"""F3 debug overlay: fps, input age and rate, reel_rate, tilt, last gesture, and a 3 s graph."""
from __future__ import annotations

from collections import deque

import pygame

from fishing.render import palette

GRAPH_SAMPLES = 180  # 3 s at 60 fps
GRAPH_SIZE = (360, 80)


class RateMeter:
    """Input samples per second, counted from ``seq`` (so it can read above the frame rate)."""

    def __init__(self, window_ms: float = 1000.0) -> None:
        self.window_ms = window_ms
        self._samples: deque[tuple[float, int]] = deque()  # (host ms, new samples)
        self._last_seq: int | None = None

    def update(self, seq: int, now_ms: float) -> None:
        if self._last_seq is not None:
            if seq > self._last_seq:
                self._samples.append((now_ms, seq - self._last_seq))
            elif seq < self._last_seq:  # a new source started counting again
                self._samples.clear()
        self._last_seq = seq
        while self._samples and now_ms - self._samples[0][0] > self.window_ms:
            self._samples.popleft()

    @property
    def hz(self) -> float:
        return sum(n for _, n in self._samples) * 1000.0 / self.window_ms


class DebugOverlay:
    def __init__(self, visible: bool = False) -> None:
        self.visible = visible
        self._font: pygame.font.Font | None = None
        self.reel: deque[float] = deque(maxlen=GRAPH_SAMPLES)
        self.tilt: deque[float] = deque(maxlen=GRAPH_SAMPLES)

    def toggle(self) -> None:
        self.visible = not self.visible

    def push(self, reel: float, tilt: float) -> None:
        self.reel.append(reel)
        self.tilt.append(tilt)

    def draw(self, surface: pygame.Surface, lines: list[str]) -> None:
        if not self.visible:
            return
        if self._font is None:
            self._font = pygame.font.SysFont(palette.OVERLAY_FONT_NAME, palette.OVERLAY_FONT_SIZE)
        rendered = [self._font.render(line, True, palette.TEXT) for line in lines]
        gw, gh = GRAPH_SIZE
        width = max([r.get_width() for r in rendered] + [gw]) + 16
        height = sum(r.get_height() for r in rendered) + gh + 24
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill(palette.OVERLAY_BG)
        y = 6
        for r in rendered:
            panel.blit(r, (8, y))
            y += r.get_height()
        self._graph(panel, pygame.Rect(8, y + 8, gw, gh))
        surface.blit(panel, (8, 8))

    def _graph(self, panel: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(panel, palette.TEXT_SHADOW, rect)
        mid = rect.centery
        pygame.draw.line(panel, palette.TEXT_DIM, (rect.left, mid), (rect.right, mid), 1)
        n = len(self.reel)
        if n < 2:
            return
        step = rect.width / (GRAPH_SAMPLES - 1)
        x0 = rect.right - (n - 1) * step
        reel_pts = [(x0 + i * step, rect.bottom - v * rect.height) for i, v in enumerate(self.reel)]
        tilt_pts = [(x0 + i * step, mid - v * rect.height / 2) for i, v in enumerate(self.tilt)]
        pygame.draw.lines(panel, palette.GOOD, False, reel_pts, 2)
        pygame.draw.lines(panel, palette.WARN, False, tilt_pts, 2)
        panel.blit(self._font.render("reel", True, palette.GOOD), (rect.left + 4, rect.top + 2))
        panel.blit(self._font.render("tilt", True, palette.WARN), (rect.left + 44, rect.top + 2))
