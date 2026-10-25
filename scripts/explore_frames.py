"""Explore how many 360 frames and visible players a build-up has (used to design the movement reconstruction)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.config import load_config, raw_dir  # noqa: E402
from pipeline.load import load_match  # noqa: E402
from pipeline.normalize import events_frame, regulation  # noqa: E402

cfg = load_config()
mid = int(sys.argv[1]) if len(sys.argv) > 1 else 3869685
moments = json.loads((Path(__file__).resolve().parents[1] / "data" / "processed" / str(mid) / "moments.json").read_text("utf8"))["moments"]
d = load_match(raw_dir(cfg), mid)
reg = regulation(events_frame(d.events))
f360 = {r["event_uuid"]: r["freeze_frame"] for r in d.three_sixty}
for m in moments:
    if not m["sequence"]:
        continue
    shot = reg[reg["id"] == m["event_id"]].iloc[0]
    first = reg[reg["id"] == m["sequence"][0]["event_id"]].iloc[0]
    win = reg[(reg["period"] == shot["period"]) & (reg["ts"] >= first["ts"] - 1.0) & (reg["ts"] <= shot["ts"])]
    rows = [(r.ts - first["ts"], r.type, r.team == shot["team"], len(f360[r.id])) for r in win.itertuples() if r.id in f360]
    gaps = [b[0] - a[0] for a, b in zip(rows, rows[1:])]
    print(f"{m['clock']:>7} {m['type']:<5} events {len(win):>3} with360 {len(rows):>3} "
          f"visible avg {sum(r[3] for r in rows) / max(len(rows), 1):4.1f} max gap {max(gaps) if gaps else 0:4.1f}s "
          f"types {sorted({r[1] for r in rows})[:6]}")
