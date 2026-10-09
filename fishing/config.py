"""Load config/tuning.toml into frozen dataclasses, failing loudly on typos."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "tuning.toml"

Pair = tuple[float, float]
ZONES = ("shallow", "mid", "deep")
KINDS = ("fish", "special", "trap", "junk")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LoopConfig:
    step_hz: int
    max_frame_s: float
    max_steps: int
    fps_cap: int
    vsync: bool
    demo_max_dt_s: float


@dataclass(frozen=True)
class WindowConfig:
    width: int
    height: int


@dataclass(frozen=True)
class InputConfig:
    stale_ms: float
    history_ms: float


@dataclass(frozen=True)
class KeyboardConfig:
    cast_charge_s: float
    tilt_ramp_per_s: float
    slow_reel: float
    fast_reel: float
    mouse_full_turns_per_s: float
    mouse_window_ms: float
    mouse_min_radius: float
    max_ramp_dt_s: float


@dataclass(frozen=True)
class MenuConfig:
    tilt_nav: float
    tilt_nav_repeat_s: float


@dataclass(frozen=True)
class RodTestConfig:
    trials: int
    pass_threshold: int
    gap_s: float
    cast_window_s: float
    bite_delay_s: Pair
    hook_window_s: float


@dataclass(frozen=True)
class RoundConfig:
    length_s: float
    frenzy_s: float
    warn_s: float
    overtime_cap_s: float
    catch_card_s: float
    escape_card_s: float
    hooked_s: float
    hit_stop_s: float
    resume_countdown_s: float
    results_delay_s: float


@dataclass(frozen=True)
class PondConfig:
    rod_tip: Pair
    water_left: float
    water_right: float
    water_top: float
    water_bottom: float
    shallow: Pair
    mid: Pair
    deep: Pair
    dock_radius: float
    land_radius: float

    def zone(self, name: str) -> Pair:
        return getattr(self, name)


@dataclass(frozen=True)
class CastConfig:
    min_dist: float
    dist_per_strength: float
    aim_max_deg: float
    aim_lookback_ms: float
    flight_base_s: float
    flight_per_strength_s: float
    arm_delay_s: float
    arm_max_reel: float
    scatter_radius: float
    scatter_cooldown_s: float
    curious_radius: float
    curious_s: float
    curious_mult: float


@dataclass(frozen=True)
class LureConfig:
    retrieve_speed: float
    steer_speed: float
    steer_reel_floor: float
    slow_band: Pair
    slow_interest_mult: float


@dataclass(frozen=True)
class FishAIConfig:
    notice_radius: float
    notice_wariness_shrink: float
    cone_deg: float
    cone_wariness_shrink_deg: float
    scare_speed: float
    scare_wariness_shrink: float
    commit_rate: float
    commit_wariness_shrink: float
    approach_speed_mult: float
    arrive_radius: float
    flee_cooldown_s: float
    global_flee_cooldown_s: float
    flee_speed_mult: float
    flee_s: float
    wander_turn_rate: float
    wander_noise: float
    steer_turn_mult: float
    flee_turn_mult: float
    leave_margin: float
    cruise_jitter: float
    edge_margin: float
    fade_s: float
    wary_flee: float
    edge_turn_mult: float
    dock_shy_radius: float


@dataclass(frozen=True)
class HookConfig:
    nibble_spook_grace_s: float
    nibble_spook_reel: float
    nibble_spook_hold_s: float
    nibble_ignore_hook_reel: float
    grace_ms: float
    delivery_margin_ms: float
    perfect_ms: float
    ack_match_ms: float


@dataclass(frozen=True)
class FightConfig:
    reel_speed: float
    tension_reel: float
    tension_pull: float
    tau_up_s: float
    tau_down_s: float
    pull_stamina_floor: float
    rest_pull: float
    stamina_base: float
    stamina_tension: float
    run_s: Pair
    rest_s: Pair
    first_run_s: float
    no_runs_below_stamina: float
    lateral_rate: float
    lateral_max_deg: float
    side_pressure_min_tilt: float
    side_pressure_pull_cut: float
    side_pressure_drain_mult: float
    strain_recover: float
    slack_tension: float
    slack_s: float
    line_out: float


@dataclass(frozen=True)
class SpawnConfig:
    initial: int
    max: int
    per_species_max: int
    respawn_s: Pair
    lifetime_s: Pair
    frenzy_respawn_mult: float
    frenzy_wariness_drop: float
    frenzy_nibble_drop: int
    practice_progress: float
    spawn_arc_deg: float


@dataclass(frozen=True)
class SpecialConfig:
    species: str
    chance: float
    window: Pair
    stay_s: float


@dataclass(frozen=True)
class JunkConfig:
    species: str
    count: int
    snag_radius: float


@dataclass(frozen=True)
class ScoringConfig:
    size_base: float
    size_span: float
    size_beta: Pair
    bonus_mult: float
    streak_step: float
    streak_cap: int
    perfect_hook_bonus: int
    bonus_rotate_s: float


@dataclass(frozen=True)
class MedalConfig:
    bronze: int
    silver: int
    gold: int
    platinum: int

    def medal_for(self, score: float) -> str | None:
        for name in ("platinum", "gold", "silver", "bronze"):
            if score >= getattr(self, name):
                return name
        return None


@dataclass(frozen=True)
class DifficultyConfig:
    window_mult: float
    wariness_add: float
    strength_mult: float
    snap_strain_s: float


@dataclass(frozen=True)
class Species:
    id: str
    name: str
    kind: str
    size_cm: Pair
    points: int
    weight: Pair
    zones: tuple[str, ...]
    cruise: float
    wariness: float
    strength: float
    stamina_s: float
    run_speed: float
    nibbles: tuple[int, int]
    gap_s: Pair
    pause_s: Pair
    window_ms: float
    touchy: bool


@dataclass(frozen=True)
class Tuning:
    loop: LoopConfig
    window: WindowConfig
    input: InputConfig
    keyboard: KeyboardConfig
    menu: MenuConfig
    rod_test: RodTestConfig
    round: RoundConfig
    pond: PondConfig
    cast: CastConfig
    lure: LureConfig
    fish_ai: FishAIConfig
    hook: HookConfig
    fight: FightConfig
    spawn: SpawnConfig
    special: SpecialConfig
    junk: JunkConfig
    scoring: ScoringConfig
    medals: MedalConfig
    difficulty: dict[str, DifficultyConfig]
    species: tuple[Species, ...]

    def species_by_id(self, sid: str) -> Species:
        for s in self.species:
            if s.id == sid:
                return s
        raise KeyError(sid)


def _tuplify(value: Any) -> Any:
    return tuple(value) if isinstance(value, list) else value


def _build(cls: type, table: Any, where: str) -> Any:
    """Build a dataclass from one TOML table, rejecting missing and unknown keys."""
    if not isinstance(table, dict):
        raise ConfigError(f"{where} is missing")
    expected = {f.name for f in fields(cls)}
    missing = expected - table.keys()
    unknown = table.keys() - expected
    if missing or unknown:
        raise ConfigError(
            f"{where}: missing {sorted(missing) or 'nothing'}, unknown {sorted(unknown) or 'nothing'}"
        )
    return cls(**{k: _tuplify(v) for k, v in table.items()})


def _check(ok: bool, msg: str) -> None:
    if not ok:
        raise ConfigError(msg)


def _validate(t: Tuning) -> None:
    ids = [s.id for s in t.species]
    _check(len(ids) == len(set(ids)), "duplicate species ids")
    for s in t.species:
        w = f"[[species]] {s.id}"
        _check(s.kind in KINDS, f"{w}: kind must be one of {KINDS}")
        _check(all(z in ZONES for z in s.zones) and s.zones, f"{w}: zones must be from {ZONES}")
        _check(s.window_ms > 0, f"{w}: window_ms must be positive")
        _check(min(s.weight) >= 0, f"{w}: weights must be >= 0")
        _check(s.size_cm[0] <= s.size_cm[1], f"{w}: size_cm must be [min, max]")
        _check(0 <= s.nibbles[0] <= s.nibbles[1], f"{w}: nibbles must be [min, max] >= 0")
        _check(s.stamina_s > 0, f"{w}: stamina_s must be positive")
    _check(t.special.species in ids, f"[special] species {t.special.species!r} not defined")
    _check(t.junk.species in ids, f"[junk] species {t.junk.species!r} not defined")
    _check("normal" in t.difficulty, "[difficulty.normal] is required")
    _check(
        any(s.kind in ("fish", "trap") and max(s.weight) > 0 for s in t.species),
        "at least one spawnable species needs a positive weight",
    )


def load_tuning(path: Path | str = DEFAULT_PATH) -> Tuning:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    simple = {
        "loop": LoopConfig, "window": WindowConfig, "input": InputConfig,
        "keyboard": KeyboardConfig, "menu": MenuConfig, "rod_test": RodTestConfig, "round": RoundConfig, "pond": PondConfig,
        "cast": CastConfig, "lure": LureConfig, "fish_ai": FishAIConfig, "hook": HookConfig,
        "fight": FightConfig, "spawn": SpawnConfig, "special": SpecialConfig,
        "junk": JunkConfig, "scoring": ScoringConfig, "medals": MedalConfig,
    }
    known = set(simple) | {"difficulty", "species"}
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"unknown sections: {sorted(unknown)}")
    parts = {name: _build(cls, raw.get(name), f"[{name}]") for name, cls in simple.items()}
    difficulty = {
        name: _build(DifficultyConfig, table, f"[difficulty.{name}]")
        for name, table in raw.get("difficulty", {}).items()
    }
    species = tuple(
        _build(Species, table, f"[[species]] #{i + 1}") for i, table in enumerate(raw.get("species", []))
    )
    tuning = Tuning(**parts, difficulty=difficulty, species=species)
    _validate(tuning)
    return tuning
