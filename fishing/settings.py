"""User settings (data/settings.json): input source, shaping, audio, gameplay options."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_PATH = DATA_DIR / "settings.json"


@dataclass
class Settings:
    input_source: str = "keyboard"  # "keyboard" | "rod"
    serial_port: str = ""
    baud: int = 115200
    tilt_sensitivity: float = 1.0
    tilt_deadzone: float = 0.10
    tilt_smoothing_ms: float = 250.0
    tilt_invert: bool = False
    tilt_offset: float = 0.0
    reel_sensitivity: float = 1.0
    reel_deadzone: float = 0.05
    forgiving_hook: bool = True
    difficulty: str = "normal"
    master_volume: float = 0.8
    music_volume: float = 0.6
    sfx_volume: float = 0.9
    game_bite_sound: bool = True
    simulate_buzzer: bool = True
    show_fps: bool = False


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read settings, keeping defaults for anything missing, mistyped or unknown."""
    defaults = Settings()
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return defaults
    if not isinstance(raw, dict):
        return defaults
    values: dict[str, Any] = {}
    for f in fields(Settings):
        if f.name not in raw:
            continue
        default = getattr(defaults, f.name)
        value = raw[f.name]
        if isinstance(default, bool):
            ok = isinstance(value, bool)
        elif isinstance(default, (int, float)):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            value = type(default)(value) if ok else value
        else:
            ok = isinstance(value, type(default))
        if ok:
            values[f.name] = value
    return Settings(**values)


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    atomic_write_json(path, asdict(settings))
