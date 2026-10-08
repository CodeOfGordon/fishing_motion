"""Settings, high scores, the session CSV and the source factory."""
import csv
import json
from datetime import datetime

import pytest

from fishing.highscores import MAX_ENTRIES, HighScores
from fishing.input.factory import make_source
from fishing.settings import Settings, load_settings, save_settings
from fishing.session_log import COLUMNS, SessionLog
from fishing.sim import events as ev
from fishing.sim.events import GameEvent
from tests.sim_driver import bot_round


# ---------------------------------------------------------------- settings
def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings(serial_port="/dev/cu.usbmodem1101", tilt_deadzone=0.2, tilt_invert=True)
    save_settings(s, path)
    assert load_settings(path) == s


def test_bad_settings_file_gives_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    assert load_settings(path) == Settings()


def test_wrong_types_and_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"baud": "fast", "tilt_invert": 1, "volume_typo": 3, "reel_deadzone": 0.2}))
    s = load_settings(path)
    assert s.baud == Settings().baud
    assert s.tilt_invert is False
    assert s.reel_deadzone == 0.2


def test_save_is_atomic(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(), path)
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


# ---------------------------------------------------------------- high scores
def test_high_scores_keep_top_ten_and_persist(tmp_path, tuning):
    path = tmp_path / "hs.json"
    hs = HighScores(path)
    ranks = []
    for seed in range(12):
        rnd = bot_round(tuning, seed).r
        if hs.qualifies(rnd.score):
            ranks.append(hs.add(rnd, f"P{seed}", "keyboard", "normal"))
    assert len(hs.entries) == MAX_ENTRIES
    scores = [e.score for e in hs.entries]
    assert scores == sorted(scores, reverse=True)
    reloaded = HighScores(path)
    assert [e.score for e in reloaded.entries] == scores
    assert all(r is not None for r in ranks)


def test_corrupt_high_scores_file_starts_fresh(tmp_path):
    path = tmp_path / "hs.json"
    path.write_text("[{\"oops\": 1}]")
    assert HighScores(path).entries == []


def test_long_names_are_trimmed(tmp_path, tuning):
    hs = HighScores(tmp_path / "hs.json")
    rnd = bot_round(tuning, 1).r
    hs.add(rnd, "A" * 40, "rod", "hard")
    assert len(hs.entries[0].name) == 10


# ---------------------------------------------------------------- session log
def test_session_log_columns_and_flush(tmp_path):
    log = SessionLog(tmp_path, now=lambda: datetime(2026, 10, 8, 12, 0, 0))
    log.mode, log.input, log.round_id = "play", "keyboard", 1
    log.event(GameEvent(ev.BITE, 1234.5, "BITE", bite_id=3, species="perch", value=700.0,
                        detail={"send": "ok"}))
    with open(log.path, newline="") as f:  # readable before close: rows are flushed
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == COLUMNS
    assert rows[0]["event"] == "bite" and rows[0]["bite_id"] == "3" and rows[0]["round_id"] == "1"
    assert json.loads(rows[0]["detail"]) == {"send": "ok"}
    log.close()


def test_two_logs_in_the_same_second_do_not_collide(tmp_path):
    fixed = lambda: datetime(2026, 10, 8, 12, 0, 0)  # noqa: E731
    a, b = SessionLog(tmp_path, now=fixed), SessionLog(tmp_path, now=fixed)
    assert a.path != b.path
    a.close()
    b.close()


def test_a_whole_round_logs_every_pass_criteria_event(tmp_path, tuning):
    d = bot_round(tuning, seed=3)
    log = SessionLog(tmp_path)
    for e in d.log:
        log.event(e)
    log.close()
    with open(log.path, newline="") as f:
        kinds = {r["event"] for r in csv.DictReader(f)}
    for needed in (ev.CAST, ev.BITE, ev.HOOK_ATTEMPT, ev.CATCH, ev.ROUND_START, ev.ROUND_END):
        assert needed in kinds


# ---------------------------------------------------------------- factory
def test_factory_keyboard(tuning):
    src, name, err = make_source(Settings(input_source="keyboard"), tuning)
    assert name == "keyboard" and err is None


def test_factory_rod_stub_falls_back(tuning):
    src, name, err = make_source(Settings(input_source="rod", serial_port="/dev/null"), tuning)
    assert name == "keyboard"
    assert err and "not available" in err
