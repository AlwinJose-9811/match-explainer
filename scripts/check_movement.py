"""Check the reconstructed movement against the event data and print a quality table.

For every pass/carry/shot with a named track, the track's position at the event time is compared with the
event's own recorded location (the actor's position is the one thing the events pin down exactly).
Usage: python scripts/check_movement.py [match_id ...]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def at(pts: list[list[float]], t: float, slack: float = 0.5) -> tuple[float, float] | None:
    if t < pts[0][0] - slack or t > pts[-1][0] + slack:
        return None
    for a, b in zip(pts, pts[1:]):
        if a[0] <= t <= b[0]:
            f = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
    return (pts[0][1], pts[0][2]) if t < pts[0][0] else (pts[-1][1], pts[-1][2])


def actor_errors(m: dict) -> list[float]:
    """Error of the player's track at each of his actions. A player whose first track ended (he left the camera view for
    a while) can have a second track with the same name, so only tracks that really cover the moment are compared."""
    errs = []
    tracks: dict[str, list] = {}
    for tr in m["movement"]["tracks"]:
        if tr["name"]:
            tracks.setdefault(tr["name"], []).append(tr)
    for s in m["sequence"]:
        found = [p for tr in tracks.get(s["player"], []) if (p := at(tr["pts"], s["t"], slack=0.0))]
        if found:
            errs.append(min(math.hypot(p[0] - s["from"][0], p[1] - s["from"][1]) for p in found))
    return errs


def main() -> int:
    index = json.loads((ROOT / "data" / "processed" / "index.json").read_text(encoding="utf8"))
    ids = [int(a) for a in sys.argv[1:]] or [m["match_id"] for m in index["matches"]]
    allerr = []
    for mid in ids:
        moments = json.loads((ROOT / "data" / "processed" / str(mid) / "moments.json").read_text(encoding="utf8"))["moments"]
        print(f"\nmatch {mid}")
        print(f"{'clock':>7} {'snap':>4} {'trk':>3} {'att':>3} {'def':>3} {'vis':>5} {'gap_s':>5} {'vmax':>5} {'named':>5} {'err_mean':>8} {'err_max':>7}")
        for m in moments:
            mv = m.get("movement")
            if not mv:
                continue
            q, errs = mv["quality"], actor_errors(m)
            allerr += errs
            att = sum(t["side"] == "att" for t in mv["tracks"])
            print(f"{m['clock']:>7} {q['snapshots']:>4} {q['tracks']:>3} {att:>3} {q['tracks'] - att:>3} {q['avg_visible']:>5} {q['max_gap_s']:>5} "
                  f"{q['max_speed']:>5} {sum(1 for t in mv['tracks'] if t['name']):>5} {sum(errs) / len(errs) if errs else float('nan'):>8.2f} {max(errs, default=0):>7.2f}")
    if allerr:
        allerr.sort()
        print(f"\nactor position error vs event data over {len(allerr)} actions: mean {sum(allerr) / len(allerr):.2f} yd, "
              f"median {allerr[len(allerr) // 2]:.2f}, 90th pct {allerr[int(len(allerr) * .9)]:.2f}, max {allerr[-1]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
