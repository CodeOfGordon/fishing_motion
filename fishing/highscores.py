"""Top-10 high scores, saved to data/highscores.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from fishing.settings import DATA_DIR, atomic_write_json
from fishing.sim.round import Round

HIGHSCORES_PATH = DATA_DIR / "highscores.json"
MAX_ENTRIES = 10
MAX_NAME = 10


@dataclass
class Entry:
    name: str
    score: int
    medal: str
    best_fish: str
    date: str
    input: str
    difficulty: str


class HighScores:
    def __init__(self, path: Path = HIGHSCORES_PATH) -> None:
        self.path = path
        self.entries: list[Entry] = self._load()

    def _load(self) -> list[Entry]:
        try:
            raw = json.loads(self.path.read_text())
            entries = [Entry(**{k: e[k] for k in Entry.__dataclass_fields__}) for e in raw]
        except (OSError, ValueError, TypeError, KeyError):
            return []
        entries.sort(key=lambda e: e.score, reverse=True)
        return entries[:MAX_ENTRIES]

    def qualifies(self, score: int) -> bool:
        return len(self.entries) < MAX_ENTRIES or score > self.entries[-1].score

    def add(self, rnd: Round, name: str, input_name: str, difficulty: str) -> int | None:
        """Insert this round's score; return its 1-based rank, or None if it didn't place."""
        if not self.qualifies(rnd.score):
            return None
        summary = rnd.summary()
        entry = Entry(
            name=(name.strip() or "ANGLER")[:MAX_NAME], score=rnd.score, medal=summary["medal"] or "",
            best_fish=summary["biggest"], date=date.today().isoformat(), input=input_name,
            difficulty=difficulty,
        )
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.score, reverse=True)
        self.entries = self.entries[:MAX_ENTRIES]
        atomic_write_json(self.path, [asdict(e) for e in self.entries])
        return self.entries.index(entry) + 1 if entry in self.entries else None
