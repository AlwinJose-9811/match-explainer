"""Print the match story and every moment explanation for review.

Usage: python scripts/print_explanations.py [match_id ...]   (default: the default match)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ids = [int(a) for a in sys.argv[1:]] or [json.loads((ROOT / "config" / "default.json").read_text("utf8"))["default_match_id"]]
    for mid in ids:
        d = ROOT / "data" / "processed" / str(mid)
        s = json.loads((d / "summary.json").read_text(encoding="utf8"))
        moments = json.loads((d / "moments.json").read_text(encoding="utf8"))["moments"]
        print(f"=== {mid}\nSTORY: {s['story']['text']}  [{s['story']['label']}]\n")
        for m in moments:
            print(f"[{m['id']} {m['clock']} {m['type']}] {m['explanation']['text']}")
            print(f"    WHY: {m['explanation']['why']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
