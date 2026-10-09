"""Drive the real app headless: title -> play -> cast -> pause -> title, and draw every scene."""
import csv

import pygame
import pytest

from fishing.app import App, MIXER_ARGS, parse_args
from fishing.scenes.highscores import HighScoresScene
from fishing.scenes.play import PlayScene
from fishing.scenes.results import ResultsScene
from fishing.scenes.rod_test import RodTestScene
from fishing.scenes.settings_menu import SettingsScene
from fishing.scenes.title import TitleScene
from tests.sim_driver import bot_round


@pytest.fixture
def app(tmp_path):
    pygame.mixer.pre_init(*MIXER_ARGS)
    pygame.init()
    a = App(parse_args(["--windowed", "--seed", "3"]), data_dir=tmp_path / "data", log_dir=tmp_path / "logs")
    yield a
    a.shutdown()
    pygame.quit()


def key(k, up=False):
    pygame.event.post(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=k, mod=0,
                                         unicode="", scancode=0))


def rows(app):
    with open(app.log.path, newline="") as f:
        return list(csv.DictReader(f))


def test_title_to_play_cast_pause_and_back(app):
    assert isinstance(app.scene, TitleScene)
    app.run(max_frames=5)
    key(pygame.K_RETURN)  # "Play"
    app.run(max_frames=5)
    assert isinstance(app.scene, PlayScene)
    app.run(max_frames=45)  # let the cast arm
    key(pygame.K_SPACE)
    app.run(max_frames=30)
    key(pygame.K_SPACE, up=True)
    app.run(max_frames=90)
    casts = [r for r in rows(app) if r["event"] == "cast"]
    assert casts and casts[0]["accepted"] == "1"
    key(pygame.K_ESCAPE)
    app.run(max_frames=2)
    assert app.scene.paused
    key(pygame.K_DOWN)
    key(pygame.K_DOWN)
    key(pygame.K_RETURN)  # "Quit to title"
    app.run(max_frames=3)
    assert isinstance(app.scene, TitleScene)


def test_space_in_a_menu_does_not_leak_a_cast(app):
    key(pygame.K_SPACE)  # selects "Play"
    app.run(max_frames=3)
    key(pygame.K_SPACE, up=True)
    app.run(max_frames=60)
    assert isinstance(app.scene, PlayScene)
    assert not [r for r in rows(app) if r["event"] == "cast"]


def test_every_scene_draws(app, tuning):
    rnd = bot_round(tuning, seed=2).r
    for scene in (TitleScene(app), PlayScene(app, practice=True), SettingsScene(app), RodTestScene(app),
                  HighScoresScene(app), ResultsScene(app, rnd)):
        app.scene = scene
        app.run(max_frames=3)


def test_practice_debug_bite_sends_bite_once(app):
    app.scene = PlayScene(app, practice=True)
    sent = []
    app.source.on_send = sent.append
    app.run(max_frames=40)
    key(pygame.K_SPACE)
    app.run(max_frames=20)
    key(pygame.K_SPACE, up=True)
    app.run(max_frames=80)  # lure lands
    key(pygame.K_b)
    app.run(max_frames=5)
    assert sent == ["BITE"]
    bites = [r for r in rows(app) if r["event"] == "bite"]
    assert len(bites) == 1 and '"send": "ok"' in bites[0]["detail"]


def test_rod_choice_with_stub_falls_back_to_keyboard(app):
    app.settings.input_source = "rod"
    app.switch_source()
    assert app.source_name == "keyboard"
    assert "Rod source not available" in app.source_error
    assert any(r["event"] == "source_error" for r in rows(app))
