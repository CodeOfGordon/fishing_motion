import pytest

from fishing.config import DEFAULT_PATH, ConfigError, load_tuning


def test_tuning_file_loads(tuning):
    assert tuning.loop.step_hz == 60
    assert tuning.window.width == 1280


def test_unknown_key_is_rejected(tmp_path):
    text = DEFAULT_PATH.read_text().replace("[window]\n", "[window]\ntypo_key = 1\n")
    path = tmp_path / "tuning.toml"
    path.write_text(text)
    with pytest.raises(ConfigError, match="typo_key"):
        load_tuning(path)


def test_missing_key_is_rejected(tmp_path):
    text = DEFAULT_PATH.read_text().replace("stale_ms = 150", "")
    path = tmp_path / "tuning.toml"
    path.write_text(text)
    with pytest.raises(ConfigError, match="stale_ms"):
        load_tuning(path)
