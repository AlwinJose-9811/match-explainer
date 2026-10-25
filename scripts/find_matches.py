"""Look up match ids, scores and 360 availability in the local StatsBomb matches file.

Usage: python scripts/find_matches.py "Argentina" "Saudi Arabia"   (prints every match containing all the given team names)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.config import load_config, raw_dir  # noqa: E402


def main() -> int:
    want = [a.lower() for a in sys.argv[1:]]
    for f in sorted((raw_dir(load_config()) / "matches").glob("*/*.json")):
        for m in json.loads(f.read_text(encoding="utf8")):
            teams = (m["home_team"]["home_team_name"], m["away_team"]["away_team_name"])
            if all(any(w in t.lower() for t in teams) for w in want):
                print(f"{m['match_id']}  {teams[0]} {m['home_score']}-{m['away_score']} {teams[1]}  {m['match_date']}  "
                      f"{(m.get('competition_stage') or {}).get('name')}  360={m.get('match_status_360')}  [{f.parent.name}/{f.stem}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
