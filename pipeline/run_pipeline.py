"""CLI: python -m pipeline.run_pipeline --match-id 3869685 [--no-llm] [--skip-train]

Phase 1 stage: load -> normalise -> match stats -> summary.json + index.json.
(--no-llm and --skip-train are accepted now so tasks.py and the docs stay stable; later stages use them.)
"""
from __future__ import annotations

import argparse
import sys

from .config import load_config, processed_dir, raw_dir
from .explain import explain_match
from .export import sync_web, update_index, write_json, write_summary
from .load import DataError, load_match
from .metrics import build_summary
from .moments import build_moments
from .normalize import events_frame, regulation
from .positions import build_positions
from .xg_predict import attach_xg, load_model, predict_shots
from .validate import validate_json


def run(match_id: int) -> dict:
    cfg = load_config()
    data = load_match(raw_dir(cfg), match_id)
    df = events_frame(data.events)
    summary = build_summary(data, df)
    validate_json(summary, "summary")
    t = summary["teams"]
    positions = build_positions(df, data.lineups, t["home"]["name"], t["away"]["name"], cfg)
    validate_json(positions, "positions")
    moments = build_moments(df, data.three_sixty, t["home"]["name"], cfg)
    bundle = load_model()
    if bundle is None:
        print("WARNING: models/xg_model.joblib missing - model xG left empty (run: python tasks.py train)",
              file=sys.stderr)
    shots = predict_shots(regulation(df), t["home"]["name"], bundle)
    attach_xg(summary, moments, shots)
    explain_match(summary, moments, data.lineups, cfg.get("name_overrides"))
    validate_json(summary, "summary")
    validate_json(shots, "shots")
    validate_json(moments, "moments")
    write_json(processed_dir(match_id) / "shots.json", shots)
    write_summary(match_id, summary)
    write_json(processed_dir(match_id) / "positions.json", positions)
    write_json(processed_dir(match_id) / "moments.json", moments)
    update_index(summary)
    sync_web()
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--match-id", type=int, default=None)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--skip-train", action="store_true")
    args = ap.parse_args(argv)
    match_id = args.match_id or load_config()["default_match_id"]
    try:
        s = run(match_id)
    except DataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    t, sc, st = s["teams"], s["score"], s["stats"]
    print(f"{t['home']['name']} {sc['home']}-{sc['away']} {t['away']['name']}"
          + (f"  (shootout {sc['shootout']['home']}-{sc['shootout']['away']})" if sc["shootout"] else ""))
    print(f"  possession {s['possession']['home']:.1%} / {s['possession']['away']:.1%}")
    for k in ("shots", "on_target", "passes", "pass_accuracy", "xg_model", "xg_statsbomb", "fouls", "corners",
              "yellow", "red"):
        print(f"  {k:<14}{str(st['home'][k]):>8}{str(st['away'][k]):>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
