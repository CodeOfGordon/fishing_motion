"""Domain events the round emits. Logging, audio, effects and the buzzer consume them."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ROUND_START = "round_start"
ROUND_END = "round_end"
STATE = "state"
CAST = "cast"
LURE_LAND = "lure_land"
EMPTY_RETRIEVE = "empty_retrieve"
COMMIT = "commit"
LOST_INTEREST = "lost_interest"
NIBBLE = "nibble"
SPOOK = "spook"
BITE = "bite"
BITE_ACK = "bite_ack"
BITE_RELEASED = "bite_released"
HOOK_ATTEMPT = "hook_attempt"
HOOKED = "hooked"
FIGHT_RUN = "fight_run"
CATCH = "catch"
ESCAPE = "escape"
SCATTER = "scatter"
SPECIAL_APPEARED = "special_appeared"
BONUS_CHANGED = "bonus_changed"
CLOCK_TICK = "clock_tick"
FRENZY = "frenzy"
TIME_UP = "time_up"
DISCONNECT = "disconnect"
RECONNECT = "reconnect"
DEBUG = "debug"


@dataclass(frozen=True)
class GameEvent:
    kind: str
    t_ms: float  # host time (fishing.input.motion.now_ms clock)
    state: str  # round state when it happened
    accepted: bool | None = None
    reason: str = ""
    bite_id: int | None = None
    species: str = ""
    strength: float | None = None
    value: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)
