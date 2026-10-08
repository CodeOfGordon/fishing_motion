"""One CSV per app launch: every cast, bite, hook-set attempt, catch and escape.

Rows are flushed as they're written, so a crash never loses the evidence for
the pass criteria (8/10 casts, 8/10 hook-sets, the buzzer answers every bite).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from fishing.sim.events import GameEvent

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
COLUMNS = [
    "wall_iso", "t_ms", "round_id", "mode", "input", "state", "event", "accepted", "reason",
    "bite_id", "species", "strength", "value", "detail",
]
SKIP_KINDS = frozenset()  # every event kind is logged


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


class SessionLog:
    def __init__(
        self, directory: Path = LOG_DIR, now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.now = now
        directory.mkdir(parents=True, exist_ok=True)
        stamp = now().strftime("%Y-%m-%d_%H%M%S")
        path = directory / f"session_{stamp}.csv"
        n = 1
        while path.exists():
            n += 1
            path = directory / f"session_{stamp}_{n}.csv"
        self.path = path
        self._file = open(path, "w", newline="", buffering=1)
        self._csv = csv.writer(self._file)
        self._csv.writerow(COLUMNS)
        self._file.flush()
        self.round_id = 0
        self.mode = ""
        self.input = ""

    def write_row(self, **fields: Any) -> None:
        detail = fields.get("detail")
        fields["detail"] = json.dumps(detail, sort_keys=True, default=str) if detail else ""
        fields.setdefault("wall_iso", self.now().isoformat(timespec="milliseconds"))
        fields.setdefault("round_id", self.round_id or "")
        fields.setdefault("mode", self.mode)
        fields.setdefault("input", self.input)
        self._csv.writerow([_fmt(fields.get(c)) for c in COLUMNS])
        self._file.flush()

    def event(self, e: GameEvent) -> None:
        if e.kind in SKIP_KINDS:
            return
        self.write_row(
            t_ms=e.t_ms, state=e.state, event=e.kind, accepted=e.accepted, reason=e.reason,
            bite_id=e.bite_id, species=e.species, strength=e.strength, value=e.value,
            detail=e.detail,
        )

    def note(self, event: str, t_ms: float, **fields: Any) -> None:
        """A row that isn't a round event (session start, source change, Rod Test...)."""
        self.write_row(event=event, t_ms=t_ms, **fields)

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
