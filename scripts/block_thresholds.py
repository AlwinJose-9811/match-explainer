"""Recompute the low/mid/high defensive-line thresholds (terciles) from every processed match's positions.json.

Usage: python scripts/block_thresholds.py   (read-only: prints the distribution and the suggested thresholds)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    index = json.loads((ROOT / "data" / "processed" / "index.json").read_text(encoding="utf8"))
    vals = []
    for m in index["matches"]:
        pos = json.loads((ROOT / "data" / "processed" / str(m["match_id"]) / "positions.json").read_text(encoding="utf8"))
        for wid, sides in pos["data"].items():
            for v in sides.values():
                if v["lines"]["def"] is not None and wid not in ("full",):
                    vals.append(v["lines"]["def"])
    a = np.array(vals)
    q = np.percentile(a, [33.3, 66.7])
    print(f"{len(index['matches'])} matches, {len(a)} windows; defensive line min {a.min():.1f} median {np.median(a):.1f} max {a.max():.1f}")
    print(f"terciles: {q[0]:.1f} and {q[1]:.1f}  ->  suggested block_thresholds [{round(q[0])}, {round(q[1])}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
