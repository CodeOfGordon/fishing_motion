"""Play many headless rounds with scripted players to tune the game.

    python tools/simulate_rounds.py              # 200 rounds per profile
    python tools/simulate_rounds.py -n 50 --profile skilled

Prints catches, score spread, how much of the score the special fish is worth,
species variety per round, and medal thresholds suggested by the spread.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fishing.config import load_tuning  # noqa: E402
from fishing.sim.bot import PROFILES, play_round  # noqa: E402


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def run(profile_name: str, n: int, difficulty: str) -> dict:
    tuning = load_tuning()
    profile = PROFILES[profile_name]
    scores, catches, casts, variety, seen, special_share, trap = [], [], [], [], [], [], 0
    escapes: Counter = Counter()
    species: Counter = Counter()
    for seed in range(n):
        r = play_round(tuning, profile, seed, difficulty=difficulty)
        scores.append(r.score)
        catches.append(len(r.stats.catches))
        casts.append(r.stats.casts)
        variety.append(len({c.species for c in r.stats.catches if c.kind in ("fish", "special")}))
        seen.append(len(r.seen_species))
        special = sum(c.points for c in r.stats.catches if c.kind == "special")
        if r.score > 0 and special:
            special_share.append(special / r.score)
        trap += sum(1 for c in r.stats.catches if c.kind == "trap")
        escapes.update({k: v for k, v in r.stats.escapes.items() if v})
        species.update(c.species for c in r.stats.catches)
    m = tuning.medals
    medals = Counter(tuning.medals.medal_for(s) or "none" for s in scores)
    return {
        "profile": profile_name, "rounds": n,
        "score_p10_p50_p90": (pct(scores, 0.1), pct(scores, 0.5), pct(scores, 0.9)),
        "catches_mean": round(statistics.mean(catches), 1),
        "casts_mean": round(statistics.mean(casts), 1),
        "species_caught_per_round": round(statistics.mean(variety), 2),
        "species_seen_per_round": round(statistics.mean(seen), 2),
        "special_share_max": round(max(special_share), 2) if special_share else 0.0,
        "special_share_mean": round(statistics.mean(special_share), 2) if special_share else 0.0,
        "trap_catches_per_round": round(trap / n, 2),
        "escapes_per_round": {k: round(v / n, 2) for k, v in escapes.most_common()},
        "catch_mix": {k: round(v / n, 2) for k, v in species.most_common()},
        "medals_now": dict(medals),
        "thresholds_now": (m.bronze, m.silver, m.gold, m.platinum),
        "scores": scores,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-n", type=int, default=200, help="rounds per profile")
    p.add_argument("--profile", choices=sorted(PROFILES), default=None)
    p.add_argument("--difficulty", default="normal")
    args = p.parse_args(argv)
    results = [run(name, args.n, args.difficulty) for name in ([args.profile] if args.profile else ["novice", "skilled"])]
    for r in results:
        print(f"\n== {r['profile']} ({r['rounds']} rounds, {args.difficulty})")
        for k, v in r.items():
            if k not in ("profile", "rounds", "scores"):
                print(f"  {k}: {v}")
    if len(results) == 2:
        nov, sk = results[0]["scores"], results[1]["scores"]
        print("\nSuggested medals (bronze = typical novice, silver = good novice / weak skilled,"
              " gold = typical skilled, platinum = top-10% skilled):")
        print(f"  bronze {round(pct(nov, 0.5), -1):.0f}  silver {round(pct(nov, 0.9), -1):.0f}  "
              f"gold {round(pct(sk, 0.5), -1):.0f}  platinum {round(pct(sk, 0.9), -1):.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
