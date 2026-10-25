"""Tests for xG features, training outputs and prediction (TC-23 to TC-28)."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from pipeline.config import ROOT, load_config, raw_dir
from pipeline.load import load_match
from pipeline.normalize import events_frame, regulation
from pipeline.validate import validate_json
from pipeline.xg_features import (FEATURES, FORBIDDEN, _in_cone, assert_no_leakage, freeze_features, shot_angle,
                                  shot_features)
from pipeline.xg_predict import attach_xg, load_model, predict_shots, team_totals
from pipeline.xg_train import clean_shots

CFG = load_config()
RAW = raw_dir(CFG)
METRICS = ROOT / "models" / "xg_metrics.json"
needs_data = pytest.mark.skipif(not (RAW / "competitions.json").exists(), reason="raw data not fetched")
needs_model = pytest.mark.skipif(not METRICS.exists(), reason="model not trained")


def test_feature_list_has_no_forbidden_names():  # TC-24
    assert_no_leakage(FEATURES)
    for f in FEATURES:
        if f != "is_open_goal":
            assert not any(t in f.lower() for t in FORBIDDEN), f
    with pytest.raises(ValueError):
        assert_no_leakage(FEATURES + ["statsbomb_xg"])
    with pytest.raises(ValueError):
        assert_no_leakage(["x", "shot_outcome"])


def test_angle_and_cone_geometry():
    assert shot_angle(108, 40) == pytest.approx(2 * math.atan(4 / 12), abs=1e-6)  # centre of goal, 12 out
    assert shot_angle(60, 40) < shot_angle(100, 40)
    assert shot_angle(119, 20) < 0.1  # almost on the goal line, wide: tiny angle
    assert 0 <= shot_angle(119.5, 40) <= math.pi
    assert _in_cone(112, 40, 100, 40) and not _in_cone(112, 60, 100, 40) and not _in_cone(95, 40, 100, 40)


def test_freeze_frame_features():
    ff = [{"teammate": False, "keeper": True, "location": [118, 41]},
          {"teammate": False, "keeper": False, "location": [112, 40]},
          {"teammate": False, "keeper": False, "location": [108, 60]},
          {"teammate": True, "keeper": False, "location": [105, 38]}]
    f = freeze_features(ff, 100, 40)
    assert f["has_ff"] == 1 and f["n_def_in_cone"] == 1 and f["is_open_goal"] == 0
    assert f["gk_dist"] == pytest.approx(math.hypot(18, 1)) and f["gk_off_centre"] == 1
    assert f["nearest_def_dist"] == pytest.approx(12.0)  # the defender at (112, 40); the keeper is not a defender
    # shot-event freeze frames mark the keeper by position name, not by a `keeper` flag
    ev_ff = [{"teammate": False, "position": {"name": "Goalkeeper"}, "location": [118, 41]},
             {"teammate": False, "position": {"name": "Center Back"}, "location": [112, 40]}]
    g = freeze_features(ev_ff, 100, 40)
    assert g["gk_dist"] == pytest.approx(math.hypot(18, 1)) and g["n_def_in_cone"] == 1 and g["is_open_goal"] == 0
    none = freeze_features(None, 100, 40)
    assert none["has_ff"] == 0 and np.isnan(none["gk_dist"])
    assert freeze_features([{"teammate": False, "keeper": False, "location": [90, 10]}], 100, 40)["is_open_goal"] == 1


def _shot_row(**kw):
    base = dict(period=1, shot_type="Open Play", x=100.0, y=40.0, shot_outcome="Goal", match_id=1)
    return {**base, **kw}


def test_training_exclusions_are_counted():  # TC-23
    df = pd.DataFrame([_shot_row(), _shot_row(shot_type="Penalty"), _shot_row(period=5), _shot_row(x=np.nan),
                       _shot_row(shot_type="Free Kick")])
    kept, counts = clean_shots(df)
    assert len(kept) == 2
    assert counts["excluded_penalties"] == 1 and counts["excluded_shootout_period5"] == 1
    assert counts["excluded_missing_location"] == 1 and counts["kept"] == 2 and counts["raw_shots"] == 5


@needs_model
def test_metrics_file_is_complete():  # TC-25, TC-26
    m = json.loads(METRICS.read_text(encoding="utf8"))
    t = m["metrics_test"]
    for k in ("baseline_constant", "baseline_distance_angle", "our_model", "statsbomb_xg"):
        assert {"log_loss", "brier", "roc_auc"} <= set(t[k])
    assert m["calibration_curve"] and m["features"] == FEATURES and m["seed"] == CFG["seed"]
    assert (ROOT / "models" / "xg_calibration.png").exists() and (ROOT / "models" / "xg_model.joblib").exists()
    assert "FIFA World Cup" not in " ".join(m["train"]["competitions"] + m["test"]["competitions"])
    assert not set(m["train"]["competitions"]) & set(m["test"]["competitions"])


@needs_model
def test_full_model_beats_distance_angle_baseline():  # TC-27
    t = json.loads(METRICS.read_text(encoding="utf8"))["metrics_test"]
    assert t["our_model"]["log_loss"] < t["baseline_distance_angle"]["log_loss"] < t["baseline_constant"]["log_loss"]


@needs_model
@needs_data
def test_predictions_in_range_penalties_fixed_totals_add_up():  # TC-28
    bundle = load_model()
    data = load_match(RAW, CFG["default_match_id"])
    df = events_frame(data.events)
    shots = predict_shots(regulation(df), data.record["home_team"]["home_team_name"], bundle)
    validate_json(shots, "shots")
    xs = [s["xg_model"] for s in shots["shots"]]
    assert all(x is not None and 0 <= x <= 1 for x in xs)
    pens = [s for s in shots["shots"] if s["is_penalty"]]
    assert len(pens) == 3 and all(s["xg_model"] == round(bundle["penalty_rate"], 3) for s in pens)
    totals = team_totals(shots)
    for side in ("home", "away"):
        assert totals[side] == pytest.approx(sum(s["xg_model"] for s in shots["shots"] if s["team"] == side), abs=1e-6)
    assert len(shots["shots"]) == 30 and not any(s["period"] == 5 for s in shots["shots"])


@needs_model
@needs_data
def test_attach_xg_fills_summary_and_moments():
    from pipeline.metrics import build_summary
    from pipeline.moments import build_moments
    data = load_match(RAW, CFG["default_match_id"])
    df = events_frame(data.events)
    summary, home = build_summary(data, df), data.record["home_team"]["home_team_name"]
    moments = build_moments(df, data.three_sixty, home, CFG)
    shots = predict_shots(regulation(df), home, load_model())
    attach_xg(summary, moments, shots)
    assert summary["stats"]["home"]["xg_model"] > 0 and summary["stats"]["away"]["xg_model"] > 0
    assert all(m["xg_model"] is not None for m in moments["moments"] if m["type"] in ("goal", "shot", "penalty"))
    validate_json(summary, "summary")


def test_missing_model_leaves_model_xg_empty():
    df = pd.DataFrame([{"id": "a", "period": 1, "minute": 3, "second": 4, "team": "A", "player": "p", "x": 100.0,
                        "y": 40.0, "shot_xg": 0.2, "shot_outcome": "Saved", "shot_body_part": "Right Foot",
                        "shot_type": "Open Play", "type": "Shot"}])
    s = predict_shots(df, "A", None)
    assert s["model_available"] is False and s["shots"][0]["xg_model"] is None
    assert team_totals(s) == {"home": None, "away": None}
