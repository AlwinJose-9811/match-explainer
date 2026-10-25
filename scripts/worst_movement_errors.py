"""List the largest gaps between the reconstructed actor position and the event's own location (debug helper)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_movement import at  # noqa: E402

rows = []
index = json.loads((ROOT / "data" / "processed" / "index.json").read_text(encoding="utf8"))
for mm in index["matches"]:
    d = json.loads((ROOT / "data" / "processed" / str(mm["match_id"]) / "moments.json").read_text(encoding="utf8"))
    for m in d["moments"]:
        if not m.get("movement"):
            continue
        tracks = {}
        for tr in m["movement"]["tracks"]:
            if tr["name"]:
                tracks.setdefault(tr["name"], []).append(tr)
        for i, s in enumerate(m["sequence"]):
            for tr in tracks.get(s["player"], []):
                p = at(tr["pts"], s["t"])
                if p:
                    rows.append((math.hypot(p[0] - s["from"][0], p[1] - s["from"][1]), mm["match_id"], m["clock"], i + 1, s["kind"], s["player"], tr["id"], len(tr["pts"]), s["from"], [round(p[0], 1), round(p[1], 1)]))
rows.sort(reverse=True)
for r in rows[:8]:
    print(f"{r[0]:6.1f} yd  match {r[1]} {r[2]} step {r[3]} {r[4]:<5} {str(r[5])[:22]:<22} track {r[6]} ({r[7]} pts) event {r[8]} track {r[9]}")
print("tracks sharing a name in one moment:", sum(1 for _ in rows if False))
