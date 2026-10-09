"""Unplugging the rod mid-round pauses it; plugging back in resumes after a countdown."""
import csv

import pygame
import pytest

from fishing.app import App, MIXER_ARGS, parse_args
from fishing.input.motion import now_ms
from fishing.input.scripted import Keyframe, ScriptedSource
from fishing.scenes.play import PlayScene


@pytest.fixture
def app(tmp_path):
    pygame.mixer.pre_init(*MIXER_ARGS)
    pygame.init()
    a = App(parse_args(["--windowed"]), data_dir=tmp_path / "data", log_dir=tmp_path / "logs")
    yield a
    a.shutdown()
    pygame.quit()


def test_unplug_pauses_and_replug_resumes(app, tuning):
    t0 = now_ms()
    app.source = ScriptedSource(keyframes=[
        Keyframe(t0, 0.0, 0.0, True),
        Keyframe(t0 + 500, 0.0, 0.0, False),  # cable pulled
        Keyframe(t0 + 1500, 0.0, 0.0, True),  # plugged back in
    ])
    app.source_name = "rod"
    app.connecting = False
    scene = PlayScene(app)
    app.scene = scene
    app.run(max_frames=20)  # ~0.33 s connected
    assert not scene.round.frozen
    app.run(max_frames=40)  # past 0.5 s: disconnected
    assert scene.round.frozen
    frozen_at = scene.round.sim_ms
    app.run(max_frames=30)
    assert scene.round.sim_ms == frozen_at  # nothing moves while unplugged
    app.run(max_frames=int(60 * (1.0 + tuning.round.resume_countdown_s)) + 20)
    assert not scene.round.frozen
    assert scene.round.sim_ms > frozen_at
    with open(app.log.path, newline="") as f:
        kinds = [r["event"] for r in csv.DictReader(f)]
    assert "disconnect" in kinds and "reconnect" in kinds
    assert kinds.index("disconnect") < kinds.index("reconnect")
