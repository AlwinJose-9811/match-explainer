"""Gate G1: assert that every ID, file and score the project depends on is real.

Prints OK or a precise list of errors; exit code 1 on any error.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf8"))


def main() -> int:
    cfg = load(ROOT / "config" / "default.json")
    train = load(ROOT / "config" / "train_competitions.json")
    data = Path(os.environ.get("MX_RAW_DIR", cfg["raw_dir"]))
    errors: list[str] = []
    if not data.exists():
        print(f"ERROR: raw data folder missing: {data}\nRun: python tasks.py fetch")
        return 1

    comps = load(data / "competitions.json")
    have = {(c["competition_id"], c["season_id"]): c for c in comps}
    for k in ("train", "test"):
        for c in train[k]:
            if (c["competition_id"], c["season_id"]) not in have:
                errors.append(f"{k}: competition {c['competition_id']}/{c['season_id']} not in competitions.json")
    if (43, 106) not in have or "World Cup" not in have[(43, 106)]["competition_name"]:
        errors.append("FIFA World Cup 2022 (43/106) not found")

    print(f"{'match_id':>9}  {'score':<7} {'events':>6} {'lineup':>6} {'360':>5}  match")
    for m in cfg["matches"]:
        mid, e = m["match_id"], m["expect"]
        mf = data / "matches" / str(m["competition_id"]) / f"{m['season_id']}.json"
        rows = [x for x in load(mf) if x["match_id"] == mid] if mf.exists() else []
        if not rows:
            errors.append(f"match {mid}: not in {mf.name}")
            continue
        x = rows[0]
        names = (x["home_team"]["home_team_name"], x["away_team"]["away_team_name"])
        score = (x["home_score"], x["away_score"])
        if names != (e["home"], e["away"]) or score != (e["home_score"], e["away_score"]):
            errors.append(f"match {mid}: got {names} {score}, expected {e}")
        present = {k: (data / d / f"{mid}.json").exists() for k, d in
                   (("events", "events"), ("lineups", "lineups"), ("360", "three-sixty"))}
        for k, ok in present.items():
            if not ok:
                errors.append(f"match {mid}: {k} file missing")
        print(f"{mid:>9}  {score[0]}-{score[1]:<5} {'yes' if present['events'] else 'NO':>6} "
              f"{'yes' if present['lineups'] else 'NO':>6} {'yes' if present['360'] else 'NO':>5}  {m['label']}")

    for k in ("train", "test"):
        for c in train[k]:
            mf = data / "matches" / str(c["competition_id"]) / f"{c['season_id']}.json"
            if not mf.exists():
                errors.append(f"{c['name']}: matches file missing")
                continue
            ids = [x["match_id"] for x in load(mf)]
            missing = [i for i in ids if not (data / "events" / f"{i}.json").exists()]
            print(f"{k:>5}: {c['name']}: {len(ids) - len(missing)}/{len(ids)} events files present")
            if missing:
                errors.append(f"{c['name']}: {len(missing)} events files missing (e.g. {missing[:3]})")

    if errors:
        print("\nFAILED:")
        for err in errors:
            print(" -", err)
        return 1
    print("\nOK: all IDs, files and scores verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
