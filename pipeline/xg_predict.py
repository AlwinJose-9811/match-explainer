"""Apply the trained xG model to one match and build shots.json (FR-X5; MX-03 section 7.6).

Penalties get the training-set penalty conversion rate; shootout shots (period 5) are excluded.
If models/xg_model.joblib is missing the model values stay null (the UI then shows StatsBomb xG only, flagged).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .config import ROOT
from .xg_features import shot_features

MODEL_PATH = ROOT / "models" / "xg_model.joblib"


def load_model(path: Path = MODEL_PATH) -> dict[str, Any] | None:
    return joblib.load(path) if path.exists() else None


def predict_shots(reg: pd.DataFrame, home: str, bundle: dict[str, Any] | None) -> dict[str, Any]:
    """shots.json content for the open-play and extra-time shots of a match (periods 1-4)."""
    shots = reg[reg["type"] == "Shot"].reset_index(drop=True)
    pen = (shots["shot_type"] == "Penalty").to_numpy()
    ok = shots["x"].notna().to_numpy() & ~pen
    xg = np.full(len(shots), np.nan)
    if bundle is not None:
        if ok.any():
            xg[ok] = bundle["pipeline"].predict_proba(shot_features(shots[ok]))[:, 1]
        xg[pen] = bundle["penalty_rate"]
    rows = []
    for r, p in zip(shots.itertuples(index=False), xg):
        rows.append({"id": r.id, "period": int(r.period), "minute": int(r.minute), "second": int(r.second),
                     "clock": f"{int(r.minute)}:{int(r.second):02d}", "team": "home" if r.team == home else "away",
                     "team_name": r.team, "player": r.player, "x": None if pd.isna(r.x) else round(float(r.x), 1),
                     "y": None if pd.isna(r.y) else round(float(r.y), 1),
                     "xg_model": None if np.isnan(p) else round(float(p), 3),
                     "xg_statsbomb": None if pd.isna(r.shot_xg) else round(float(r.shot_xg), 3),
                     "outcome": r.shot_outcome, "body_part": r.shot_body_part, "is_penalty": r.shot_type == "Penalty",
                     "is_goal": r.shot_outcome == "Goal"})
    return {"model_available": bundle is not None, "shots": rows}


def team_totals(shots: dict[str, Any]) -> dict[str, float | None]:
    """Sum of model xG per side; None when the model is unavailable."""
    if not shots["model_available"]:
        return {"home": None, "away": None}
    return {s: round(sum(x["xg_model"] or 0.0 for x in shots["shots"] if x["team"] == s), 3) for s in ("home", "away")}


def attach_xg(summary: dict[str, Any], moments: dict[str, Any], shots: dict[str, Any]) -> None:
    """Fill summary.stats.*.xg_model and moments[*].xg_model from the predictions (in place)."""
    totals = team_totals(shots)
    for side in ("home", "away"):
        summary["stats"][side]["xg_model"] = totals[side]
    by_id = {s["id"]: s["xg_model"] for s in shots["shots"]}
    for m in moments["moments"]:
        if m["event_id"] in by_id:
            m["xg_model"] = by_id[m["event_id"]]
