"""Synthesised sounds match the mixer format (wrong format = wrong speed) and play headless."""
import pygame
import pytest

from fishing.audio import recipes
from fishing.audio.bank import SoundBank
from fishing.audio.synth import Synth
from fishing.settings import Settings


@pytest.fixture(scope="module")
def mixer():
    pygame.mixer.init(44100, -16, 2, 512)
    yield pygame.mixer.get_init()
    pygame.mixer.quit()


def test_buffer_size_matches_channels(mixer):
    rate, _, channels = mixer
    s = Synth(rate, channels)
    sig = s.tone(440, 0.1)
    assert len(s.to_bytes(sig)) == len(sig) * 2 * channels


@pytest.mark.parametrize("name", sorted(recipes.ALL))
def test_each_sound_plays_at_its_intended_length(mixer, name):
    rate, _, channels = mixer
    s = Synth(rate, channels)
    sig = recipes.ALL[name](s)
    snd = pygame.mixer.Sound(buffer=s.to_bytes(sig))
    assert snd.get_length() == pytest.approx(s.duration(sig), rel=0.01)


def test_bank_plays_and_clicks(mixer):
    bank = SoundBank(Settings())
    assert bank.enabled and set(recipes.ALL) <= set(bank.sounds)
    bank.play("bite")
    for _ in range(60):
        bank.reel_clicks(1 / 60, 1.0, True)
    bank.tension(0.9)
    bank.tension(None)
    bank.stop_all()


def test_bite_sound_is_not_in_the_buzzer_band(mixer):
    """The game's bite must sound different from the Uno's piezo (2-4 kHz)."""
    s = Synth(44100, 1)
    sig = recipes.bite(s)
    crossings = sum(1 for a, b in zip(sig, sig[1:]) if a <= 0 < b)
    approx_hz = crossings / s.duration(sig)
    assert approx_hz < 1000
