"""Write the processed bundle and keep data/processed/index.json up to date."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ROOT, load_config, processed_dir


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf8")


def write_summary(match_id: int, summary: dict[str, Any]) -> Path:
    path = processed_dir(match_id) / "summary.json"
    write_json(path, summary)
    return path


def update_index(summary: dict[str, Any]) -> Path:
    """Upsert this match into index.json; order follows config/default.json, unknown ids last."""
    cfg = load_config()
    path = ROOT / "data" / "processed" / "index.json"
    index = json.loads(path.read_text(encoding="utf8")) if path.exists() else {"matches": []}
    labels = {m["match_id"]: m["label"] for m in cfg["matches"]}
    t = summary["teams"]
    entry = {"match_id": summary["match_id"],
             "label": labels.get(summary["match_id"], f"{t['home']['name']} v {t['away']['name']}"),
             "date": summary["date"], "home": t["home"]["name"], "away": t["away"]["name"],
             "score": f"{summary['score']['home']}-{summary['score']['away']}",
             "path": f"{summary['match_id']}/"}
    rest = [m for m in index["matches"] if m["match_id"] != entry["match_id"]] + [entry]
    order = [m["match_id"] for m in cfg["matches"]]
    rest.sort(key=lambda m: order.index(m["match_id"]) if m["match_id"] in order else len(order))
    index = {"default": cfg["default_match_id"], "matches": rest}
    write_json(path, index)
    return path
