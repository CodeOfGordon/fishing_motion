"""Named sound effects, mixer channels and volumes. Silent if there's no audio device."""
from __future__ import annotations

from typing import Callable

import pygame

from fishing.audio import recipes
from fishing.audio.synth import Synth
from fishing.settings import Settings

CH_REEL, CH_TENSION, CH_AMBIENCE, CH_UI = 0, 1, 2, 3
RESERVED = 4
NUM_CHANNELS = 24
FIGHT_MUSIC_DUCK = 0.5  # music volume multiplier while fighting a fish


class SoundBank:
    def __init__(self, settings: Settings, recipe_set: dict[str, Callable[[Synth], list]] | None = None) -> None:
        self.settings = settings
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.lengths: dict[str, float] = {}
        self.enabled = pygame.mixer.get_init() is not None
        self._click_phase = 0.0
        if not self.enabled:
            return
        rate, _size, channels = pygame.mixer.get_init()
        self.synth = Synth(rate, channels)
        pygame.mixer.set_num_channels(NUM_CHANNELS)
        pygame.mixer.set_reserved(RESERVED)
        for name, make in (recipe_set or recipes.ALL).items():
            sig = make(self.synth)
            self.sounds[name] = pygame.mixer.Sound(buffer=self.synth.to_bytes(sig))
            self.lengths[name] = self.synth.duration(sig)

    @property
    def sfx_gain(self) -> float:
        return self.settings.master_volume * self.settings.sfx_volume

    def play(self, name: str, volume: float = 1.0, channel: int | None = None, loops: int = 0) -> None:
        snd = self.sounds.get(name)
        if not self.enabled or snd is None:
            return
        snd.set_volume(max(0.0, min(1.0, volume * self.sfx_gain)))
        if channel is None:
            snd.play(loops=loops)
        else:
            pygame.mixer.Channel(channel).play(snd, loops=loops)

    def reel_clicks(self, dt: float, reel: float, active: bool) -> None:
        """Ratchet clicks at 4 + 26 * reel per second while reeling."""
        if not self.enabled or not active or reel <= 0.02:
            self._click_phase = 0.0
            return
        self._click_phase += dt * (recipes.CLICK_BASE_HZ + recipes.CLICK_SPAN_HZ * reel)
        if self._click_phase >= 1.0:
            self._click_phase %= 1.0
            self.play("reel_click", 0.5 + 0.5 * reel, channel=CH_REEL)

    def tension(self, level: float | None) -> None:
        """Hold the tension hum at a volume following the line tension (None = off)."""
        if not self.enabled or "tension" not in self.sounds:
            return
        ch = pygame.mixer.Channel(CH_TENSION)
        if level is None or level < recipes.TENSION_AUDIBLE:
            ch.stop()
            return
        if not ch.get_busy():
            ch.play(self.sounds["tension"], loops=-1)
        ch.set_volume(min(1.0, level) * self.sfx_gain * recipes.TENSION_GAIN)

    def stop_all(self) -> None:
        if self.enabled:
            pygame.mixer.stop()
