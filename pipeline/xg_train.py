"""Train and evaluate the xG model: python -m pipeline.xg_train  (FR-X1, FR-X3, FR-X4; MX-03 section 7).

Train on the configured competition-seasons, hold out Euro 2020 as the test set, tune C with match-grouped
k-fold CV, compare against two baselines and StatsBomb's own xG on the same test shots, and write
models/xg_model.joblib, models/xg_metrics.json and models/xg_calibration.png.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import ROOT, load_config, raw_dir
from .normalize import flatten_event
from .xg_features import CATEGORICAL, FEATURES, NUMERIC, assert_no_leakage, shot_features

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MODELS = ROOT / "models"
CACHE = ROOT / "data" / "interim" / "shots_all.joblib"
C_GRID = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0]


def season_shots(raw: Path, comp: int, season: int, name: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """All shot rows of a competition-season plus counts of what was seen."""
    rows, seen = [], {"matches": 0, "shots": 0, "shootout": 0, "penalty": 0, "no_location": 0}
    for rec in json.loads((raw / "matches" / str(comp) / f"{season}.json").read_text(encoding="utf8")):
        f = raw / "events" / f"{rec['match_id']}.json"
        if not f.exists():
            continue
        seen["matches"] += 1
        for e in json.loads(f.read_text(encoding="utf8")):
            if e["type"]["name"] != "Shot":
                continue
            row = flatten_event(e)
            row.update(match_id=rec["match_id"], competition=name)
            rows.append(row)
    df = pd.DataFrame(rows)
    seen["shots"] = len(df)
    return df, seen


def clean_shots(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply the FR-X1 exclusions and report the count per reason."""
    counts = {"raw_shots": len(df)}
    d = df[df["period"] != 5]
    counts["excluded_shootout_period5"] = len(df) - len(d)
    pen = d["shot_type"] == "Penalty"
    counts["excluded_penalties"] = int(pen.sum())
    d = d[~pen]
    noloc = d["x"].isna()
    counts["excluded_missing_location"] = int(noloc.sum())
    d = d[~noloc]
    counts["excluded_own_goals"] = 0  # own goals are separate events, never Shot rows
    counts["kept"] = len(d)
    return d.reset_index(drop=True), counts


def make_pipeline(c: float, cols: list[str] | None = None) -> Pipeline:
    num = [f for f in (cols or FEATURES) if f in NUMERIC]
    cat = [f for f in (cols or FEATURES) if f in CATEGORICAL]
    parts = [("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num)]
    if cat:
        parts.append(("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=30), cat))
    return Pipeline([("prep", ColumnTransformer(parts)), ("lr", LogisticRegression(C=c, max_iter=3000))])


def scores(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {"log_loss": round(float(log_loss(y, p)), 4), "brier": round(float(brier_score_loss(y, p)), 4),
            "roc_auc": round(float(roc_auc_score(y, p)), 4), "total_xg": round(float(p.sum()), 1),
            "goals": int(y.sum()), "shots": int(len(y))}


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error with equal-width probability bins."""
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return round(float(sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).sum()
                           for b in range(bins) if (idx == b).any()) / len(y)), 4)


def plot_calibration(y, p_model, p_sb, path: Path) -> list[dict[str, float]]:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw={"width_ratios": [3, 2]})
    curve = []
    for p, lab, col in ((p_model, "Our model", "#2E75B6"), (p_sb, "StatsBomb xG", "#C55A11")):
        frac, mean = calibration_curve(y, p, n_bins=10, strategy="quantile")
        a1.plot(mean, frac, "o-", c=col, label=lab)
        if lab == "Our model":
            curve = [{"predicted": round(float(m), 3), "actual": round(float(f), 3)} for m, f in zip(mean, frac)]
    a1.plot([0, 1], [0, 1], "--", c="#888", label="perfect")
    a1.set(xlabel="predicted chance of a goal", ylabel="share that were goals", title="Calibration on Euro 2020 (held out)")
    a1.legend()
    a2.hist(p_model, bins=30, color="#2E75B6")
    a2.set(xlabel="predicted xG", ylabel="shots", title="Distribution of predictions")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return curve


def main() -> int:
    cfg, tc = load_config(), json.loads((ROOT / "config" / "train_competitions.json").read_text(encoding="utf8"))
    raw = raw_dir(cfg)
    assert (43, 106) not in {(c["competition_id"], c["season_id"]) for k in ("train", "test") for c in tc[k]}, \
        "FIFA World Cup 2022 must never be in the training or test lists"
    if CACHE.exists():
        data = joblib.load(CACHE)
    else:
        data = {}
        for k in ("train", "test"):
            parts = [season_shots(raw, c["competition_id"], c["season_id"], c["name"]) for c in tc[k]]
            data[k] = {"shots": pd.concat([p[0] for p in parts], ignore_index=True),
                       "seen": {c["name"]: p[1] for c, p in zip(tc[k], parts)}}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(data, CACHE)
    tr_all, te_all = data["train"]["shots"], data["test"]["shots"]
    pens = tr_all[(tr_all["period"] != 5) & (tr_all["shot_type"] == "Penalty")]
    pen_rate = float((pens["shot_outcome"] == "Goal").mean())
    tr, tr_counts = clean_shots(tr_all)
    te, te_counts = clean_shots(te_all)
    print("train:", tr_counts, "\ntest:", te_counts, f"\npenalties in training data: {len(pens)}, rate {pen_rate:.3f}")

    Xtr, Xte = shot_features(tr), shot_features(te)
    assert_no_leakage(list(Xtr.columns))
    ytr, yte = (tr["shot_outcome"] == "Goal").astype(int).to_numpy(), (te["shot_outcome"] == "Goal").astype(int).to_numpy()
    groups = tr["match_id"].to_numpy()

    cv = {}
    for c in C_GRID:
        oof = np.zeros(len(ytr))
        for a, b in GroupKFold(n_splits=5).split(Xtr, ytr, groups):
            oof[b] = make_pipeline(c).fit(Xtr.iloc[a], ytr[a]).predict_proba(Xtr.iloc[b])[:, 1]
        cv[c] = round(float(log_loss(ytr, np.clip(oof, 1e-6, 1 - 1e-6))), 4)
    best_c = min(cv, key=cv.get)
    print("grouped CV log loss by C:", cv, "-> C =", best_c)

    model = make_pipeline(best_c).fit(Xtr, ytr)
    base_lr = make_pipeline(1.0, ["dist", "angle"]).fit(Xtr[["dist", "angle"]], ytr)
    p_model = model.predict_proba(Xte)[:, 1]
    p_base = base_lr.predict_proba(Xte[["dist", "angle"]])[:, 1]
    p_const = np.full(len(yte), ytr.mean())
    sb = te["shot_xg"].astype(float).to_numpy()
    ok = ~np.isnan(sb)
    curve = plot_calibration(yte[ok], p_model[ok], sb[ok], MODELS / "xg_calibration.png")

    has = Xte["has_ff"].to_numpy() == 1
    by_ff = {k: scores(yte[m], p_model[m]) for k, m in (("with_freeze_frame", has), ("without_freeze_frame", ~has)) if m.sum() > 50 and yte[m].sum() > 0}
    imp = permutation_importance(model, Xte, yte, scoring="neg_log_loss", n_repeats=5, random_state=cfg["seed"])
    importance = sorted(({"feature": f, "log_loss_increase": round(float(v), 4)} for f, v in zip(FEATURES, imp.importances_mean)),
                        key=lambda d: -d["log_loss_increase"])
    metrics: dict[str, Any] = {
        "date": dt.date.today().isoformat(), "seed": cfg["seed"], "best_C": best_c, "cv_log_loss_by_C": {str(k): v for k, v in cv.items()},
        "libraries": {"python": sys.version.split()[0], "scikit-learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "train": {"competitions": [c["name"] for c in tc["train"]], "matches": sum(s["matches"] for s in data["train"]["seen"].values()),
                  **tr_counts, "goal_rate": round(float(ytr.mean()), 4)},
        "test": {"competitions": [c["name"] for c in tc["test"]], "matches": sum(s["matches"] for s in data["test"]["seen"].values()),
                 **te_counts, "goal_rate": round(float(yte.mean()), 4)},
        "split": "train and test are different competitions; tuning uses 5-fold CV grouped by match",
        "features": FEATURES, "forbidden_features": ["shot outcome", "shot end location", "StatsBomb xG", "key pass id"],
        "metrics_test": {"baseline_constant": scores(yte, p_const), "baseline_distance_angle": scores(yte, p_base),
                         "our_model": {**scores(yte, p_model), "ece": ece(yte, p_model)},
                         "statsbomb_xg": {**scores(yte[ok], sb[ok]), "ece": ece(yte[ok], sb[ok])}},
        "by_freeze_frame": by_ff, "calibration_curve": curve, "permutation_importance": importance,
        "penalty": {"rate": round(pen_rate, 4), "count": int(len(pens)), "goals": int((pens["shot_outcome"] == "Goal").sum())},
    }
    m = metrics["metrics_test"]
    metrics["beats_distance_angle_baseline"] = m["our_model"]["log_loss"] < m["baseline_distance_angle"]["log_loss"]
    MODELS.mkdir(exist_ok=True)
    joblib.dump({"pipeline": model, "features": FEATURES, "penalty_rate": pen_rate}, MODELS / "xg_model.joblib")
    (MODELS / "xg_metrics.json").write_text(json.dumps(metrics, indent=1, ensure_ascii=False) + "\n", encoding="utf8")
    for k, v in m.items():
        print(f"{k:<26}", v)
    print("beats distance-angle baseline:", metrics["beats_distance_angle_baseline"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
