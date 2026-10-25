"""Pre-shot features for the xG model (FR-X2; MX-03 section 7.3).

Only information available at the moment of the shot is used. Outcome, end location and StatsBomb's own xG
are forbidden (they stay in the table for labels and benchmarking only); FORBIDDEN + `assert_no_leakage`
enforce that, and a unit test fails if any model feature matches.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

GOAL_X, GOAL_Y, POST_Y = 120.0, 40.0, 4.0  # goal centre and half-width (posts at y = 36 and 44)
NUMERIC = ["x", "y_abs", "dist", "angle", "under_pressure", "first_time", "has_ff", "is_open_goal",
           "gk_dist", "gk_off_centre", "n_def_in_cone", "nearest_def_dist"]
CATEGORICAL = ["body_part", "technique", "play_pattern", "shot_type"]
FEATURES = NUMERIC + CATEGORICAL
# Column names or fragments that must never reach the model.
FORBIDDEN = ("outcome", "end_x", "end_y", "end_location", "shot_xg", "statsbomb_xg", "key_pass", "goal", "xg")


def assert_no_leakage(features: list[str]) -> None:
    """Raise if any feature name contains a forbidden fragment (is_open_goal is allowed: it is geometric)."""
    bad = [f for f in features if f != "is_open_goal" and any(t in f.lower() for t in FORBIDDEN)]
    if bad:
        raise ValueError(f"leaking features: {bad}")


def shot_angle(x: float, y: float) -> float:
    """Angle subtended by the posts: atan2(8*dx, dx^2 + dy^2 - 16), in [0, pi]."""
    dx, dy = GOAL_X - x, y - GOAL_Y
    return float(np.clip(math.atan2(2 * POST_Y * dx, dx * dx + dy * dy - POST_Y * POST_Y), 0, math.pi))


def _in_cone(px: float, py: float, sx: float, sy: float) -> bool:
    """Is (px, py) inside the triangle shooter -> left post -> right post?"""
    a, b, c = (sx, sy), (GOAL_X, GOAL_Y - POST_Y), (GOAL_X, GOAL_Y + POST_Y)

    def side(p, q, r):
        return (p[0] - r[0]) * (q[1] - r[1]) - (q[0] - r[0]) * (p[1] - r[1])

    d1, d2, d3 = side((px, py), a, b), side((px, py), b, c), side((px, py), c, a)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def is_keeper(p: dict[str, Any]) -> bool:
    """360 frames flag keepers with `keeper`; the freeze frame inside shot events names the position instead."""
    return bool(p.get("keeper")) or (p.get("position") or {}).get("name") == "Goalkeeper"


def freeze_features(ff: Any, sx: float, sy: float) -> dict[str, float]:
    """Goalkeeper and defender features from the shot's freeze frame (NaN when there is none)."""
    nan = {"gk_dist": np.nan, "gk_off_centre": np.nan, "nearest_def_dist": np.nan}
    if not isinstance(ff, list) or not ff:
        return {"has_ff": 0, "is_open_goal": 0, "n_def_in_cone": np.nan, **nan}
    keeper = [p["location"] for p in ff if not p.get("teammate") and is_keeper(p)]
    defenders = [p["location"] for p in ff if not p.get("teammate") and not is_keeper(p)]
    in_cone = [d for d in defenders if _in_cone(d[0], d[1], sx, sy)]
    out: dict[str, float] = {"has_ff": 1, "n_def_in_cone": len(in_cone), **nan}
    if keeper:
        out["gk_dist"] = math.hypot(keeper[0][0] - sx, keeper[0][1] - sy)
        out["gk_off_centre"] = abs(keeper[0][1] - GOAL_Y)
    if defenders:
        out["nearest_def_dist"] = min(math.hypot(d[0] - sx, d[1] - sy) for d in defenders)
    out["is_open_goal"] = int(not keeper and not in_cone)
    return out


def shot_features(shots: pd.DataFrame) -> pd.DataFrame:
    """Feature matrix (columns = FEATURES) from the flat shot rows of normalize.events_frame."""
    rows = []
    for r in shots.itertuples(index=False):
        dist = math.hypot(GOAL_X - r.x, GOAL_Y - r.y)
        rows.append({"x": r.x, "y_abs": abs(r.y - GOAL_Y), "dist": dist, "angle": shot_angle(r.x, r.y),
                     "under_pressure": int(bool(r.under_pressure)), "first_time": int(bool(r.shot_first_time)),
                     "body_part": r.shot_body_part or "Other", "technique": r.shot_technique or "Normal",
                     "play_pattern": r.play_pattern or "Other", "shot_type": r.shot_type or "Open Play",
                     **freeze_features(r.shot_ff, r.x, r.y)})
    out = pd.DataFrame(rows, columns=FEATURES)
    assert_no_leakage(list(out.columns))
    return out
