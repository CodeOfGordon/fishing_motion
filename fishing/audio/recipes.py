"""Sound recipes, all synthesised (no files, no licences). Presentation-only constants."""
from __future__ import annotations

from typing import Callable

from fishing.audio.synth import Signal, Synth

CLICK_BASE_HZ = 4.0
CLICK_SPAN_HZ = 26.0
TENSION_AUDIBLE = 0.35
TENSION_GAIN = 0.5


def beep(freq: float, dur: float = 0.08, vol: float = 0.4) -> Callable[[Synth], Signal]:
    return lambda s: s.tone(freq, dur, vol, wave="square", duty=0.5)


def cast(s: Synth) -> Signal:
    return s.noise(0.35, 0.35, attack=0.08, release=0.2, lowpass=0.05, lowpass_end=0.4)


def plop(s: Synth) -> Signal:
    return s.mix(s.tone(620, 0.14, 0.5, freq_end=140, release=0.08),
                 s.noise(0.06, 0.15, lowpass=0.3))


def nibble(s: Synth) -> Signal:
    return s.tone(900, 0.03, 0.25, wave="triangle", release=0.02)


def bite(s: Synth) -> Signal:
    # Low and round, deliberately unlike the Uno's 2-4 kHz piezo beep.
    return s.mix(s.tone(220, 0.25, 0.6, freq_end=120, release=0.12),
                 s.noise(0.18, 0.2, lowpass=0.15, release=0.12))


def hook(s: Synth) -> Signal:
    return s.mix(s.noise(0.09, 0.3, lowpass=0.2, lowpass_end=0.9),
                 s.at(s.tone(160, 0.08, 0.5, freq_end=90), 0.07))


def reel_click(s: Synth) -> Signal:
    return s.noise(0.008, 0.35, attack=0.0005, release=0.004, highpass=0.6)


def tension(s: Synth) -> Signal:
    return s.mix(s.tone(110, 1.0, 0.25, wave="saw", attack=0.0, release=0.0),
                 s.tone(165, 1.0, 0.12, wave="saw", attack=0.0, release=0.0))


def snap(s: Synth) -> Signal:
    return s.mix(s.pluck(196, 0.6, 0.6, decay=0.99), s.noise(0.04, 0.4, release=0.03))


def escape(s: Synth) -> Signal:
    return s.seq(s.tone(392, 0.14, 0.35, wave="triangle"), s.tone(262, 0.22, 0.35, wave="triangle"))


def catch(s: Synth) -> Signal:
    notes = (523, 659, 784, 1047)
    return s.seq(*[s.tone(f, 0.09, 0.35, wave="square", duty=0.25, release=0.03) for f in notes])


def catch_special(s: Synth) -> Signal:
    notes = (523, 659, 784, 1047, 784, 1047, 1319)
    return s.seq(*[s.tone(f, 0.1, 0.35, wave="square", duty=0.25, release=0.03) for f in notes])


def chime(s: Synth) -> Signal:
    return s.mix(s.decay(s.tone(1319, 1.2, 0.35, release=0.3), 0.3),
                 s.at(s.decay(s.tone(1760, 1.0, 0.25, release=0.3), 0.25), 0.12))


def tick(s: Synth) -> Signal:
    return s.tone(1200, 0.02, 0.3, wave="square", release=0.01)


def gong(s: Synth) -> Signal:
    return s.decay(s.mix(s.tone(196, 1.5, 0.4), s.tone(294, 1.5, 0.2), s.tone(392, 1.5, 0.1)), 0.4)


def buzzer(s: Synth) -> Signal:
    """What the Uno's piezo sounds like, for keyboard play."""
    return s.tone(2700, 0.12, 0.25, wave="square", attack=0.001, release=0.005)


ALL: dict[str, Callable[[Synth], Signal]] = {
    "cast": cast, "plop": plop, "nibble": nibble, "bite": bite, "hook": hook,
    "reel_click": reel_click, "tension": tension, "snap": snap, "escape": escape,
    "catch": catch, "catch_special": catch_special, "chime": chime, "tick": tick,
    "gong": gong, "buzzer": buzzer,
    "menu_move": beep(660, 0.03, 0.2), "menu_ok": beep(990, 0.06, 0.25), "menu_back": beep(440, 0.06, 0.2),
}
