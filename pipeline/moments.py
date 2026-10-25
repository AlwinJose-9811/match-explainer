"""Key-moment detection, build-up extraction and facts (FR-K1 to FR-K4; MX-03 sections 6.4, 6.5).

Moment types: goal (any goal incl. penalty goals), own_goal, penalty (missed/saved), red_card, shot (high xG).
Penalties carry no build-up and no snapshot (the UI shows a penalty card).
The ranking uses StatsBomb xG for now; the model's xG is attached after training.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .normalize import regulation
from .snapshots import index_360, snapshot

PERIOD_BASE_S = {1: 0, 2: 2700, 3: 5400, 4: 6300}
MAX_STEPS, MAX_SECONDS = 12, 20.0
SCORES = {"goal": 100, "penalty": 80, "red_card": 70}


def clock_s(period: int, ts: float) -> float:
    """Seconds from kick-off using period bases (45 / 90 / 105 minutes)."""
    return PERIOD_BASE_S.get(period, 0) + ts


def _candidate(r: pd.Series, mtype: str, score: float, home: str) -> dict[str, Any]:
    return {"type": mtype, "event_id": r["id"], "index": int(r["index"]), "period": int(r["period"]),
            "minute": int(r["minute"]), "second": int(r["second"]), "clock": f"{int(r['minute'])}:{int(r['second']):02d}",
            "clock_s": clock_s(int(r["period"]), float(r["ts"])), "score": float(score),
            "team": "home" if r["team"] == home else "away", "team_name": r["team"], "player": r["player"],
            "xg_statsbomb": None if pd.isna(r["shot_xg"]) else round(float(r["shot_xg"]), 3), "xg_model": None,
            "outcome": r["shot_outcome"] if isinstance(r["shot_outcome"], str) else None}


def detect_candidates(reg: pd.DataFrame, home: str, xg_threshold: float) -> list[dict[str, Any]]:
    """Goals, penalties, shots at/above the xG threshold, red cards (incl. second yellow), own goals."""
    out: list[dict[str, Any]] = []
    for _, r in reg[reg["type"] == "Shot"].iterrows():
        goal, pen = r["shot_outcome"] == "Goal", r["shot_type"] == "Penalty"
        xg = float(r["shot_xg"]) if pd.notna(r["shot_xg"]) else 0.0
        if goal:
            c = _candidate(r, "goal", SCORES["goal"], home)
        elif pen:
            c = _candidate(r, "penalty", SCORES["penalty"], home)
        elif xg >= xg_threshold:
            c = _candidate(r, "shot", xg * 100, home)
        else:
            continue
        c.update(is_goal=bool(goal), is_penalty=bool(pen))
        out.append(c)
    for _, r in reg[reg["card"].isin(("Red Card", "Second Yellow"))].iterrows():
        c = _candidate(r, "red_card", SCORES["red_card"], home)
        c.update(is_goal=False, is_penalty=False, card=r["card"])
        out.append(c)
    for _, r in reg[reg["type"] == "Own Goal For"].iterrows():
        near = reg[(reg["type"] == "Own Goal Against") & ((reg["index"] - r["index"]).abs() <= 3)]
        c = _candidate(r, "own_goal", SCORES["goal"], home)
        c.update(is_goal=True, is_penalty=False, player=near["player"].iat[0] if len(near) else None)
        out.append(c)
    return out


def select_moments(cands: list[dict[str, Any]], max_moments: int, min_gap_s: float) -> list[dict[str, Any]]:
    """All goals first, then the best-scoring others at least min_gap_s from every kept moment, capped."""
    kept = [c for c in cands if c["is_goal"]]
    for c in sorted((c for c in cands if not c["is_goal"]), key=lambda c: (-c["score"], c["clock_s"])):
        if len(kept) >= max_moments:
            break
        if all(abs(c["clock_s"] - k["clock_s"]) >= min_gap_s for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c["clock_s"])


def build_sequence(reg: pd.DataFrame, shot: pd.Series) -> tuple[list[dict[str, Any]], bool]:
    """Drawn build-up steps ending with the shot, plus a flag for 'follows an earlier shot' (rebound).

    Same possession and team, before the shot, last 12 actions within 20 s; completed passes and carries only.
    """
    poss = reg[(reg["possession"] == shot["possession"]) & (reg["period"] == shot["period"])
               & (reg["team"] == shot["team"]) & (reg["index"] < shot["index"])]
    earlier = poss[poss["type"] == "Shot"]
    rebound = False
    if len(earlier):
        poss, rebound = poss[poss["index"] > earlier["index"].max()], True
    acts = poss[poss["type"].isin(("Pass", "Carry")) & poss["end_x"].notna() & poss["x"].notna()]
    acts = acts[acts["pass_outcome"].isna() & (shot["ts"] - acts["ts"] <= MAX_SECONDS)].tail(MAX_STEPS)
    t0 = float(acts["ts"].iat[0]) if len(acts) else float(shot["ts"])
    key_id = shot["key_pass_id"] if isinstance(shot["key_pass_id"], str) else None
    last_pass = acts[acts["type"] == "Pass"]["id"].tolist()
    key = key_id if key_id in last_pass else (last_pass[-1] if last_pass else None)
    steps = [{"kind": r["type"].lower(), "event_id": r["id"], "from": [round(r["x"], 1), round(r["y"], 1)],
              "to": [round(r["end_x"], 1), round(r["end_y"], 1)], "player": r["player"],
              "recipient": r["pass_recipient"] if isinstance(r["pass_recipient"], str) else None,
              "t": round(float(r["ts"]) - t0, 2), "key": r["id"] == key, "outcome": "Complete" if r["type"] == "Pass" else None}
             for _, r in acts.iterrows()]
    end = [shot["end_x"], shot["end_y"]] if pd.notna(shot["end_x"]) else [120.0, 40.0]
    steps.append({"kind": "shot", "event_id": shot["id"], "from": [round(shot["x"], 1), round(shot["y"], 1)],
                  "to": [round(end[0], 1), round(end[1], 1)], "player": shot["player"], "recipient": None,
                  "t": round(float(shot["ts"]) - t0, 2), "key": False, "outcome": shot["shot_outcome"]})
    return steps, rebound


def moment_snapshots(shot: pd.Series, steps: list[dict[str, Any]], f360: dict[str, list]) -> dict[str, Any]:
    """Snapshots at the key pass and the shot (360 first; the shot's own freeze frame as fallback)."""
    key_ev = next((s["event_id"] for s in steps if s["key"]), None)
    own = shot["shot_ff"] if isinstance(shot["shot_ff"], list) else None
    shot_snap = snapshot(f360.get(shot["id"]) or own, (shot["x"], shot["y"]))
    return {"key_pass": snapshot(f360.get(key_ev)) if key_ev else None, "shot": shot_snap}


def moment_facts(shot: pd.Series, steps: list[dict[str, Any]], snaps: dict[str, Any], rebound: bool) -> dict[str, Any]:
    drawn = [s for s in steps if s["kind"] != "shot"]
    passes = [s for s in drawn if s["kind"] == "pass"]
    snap = snaps.get("key_pass") or snaps.get("shot") or {}
    line = snap.get("offside_line_x")
    key = next((s for s in steps if s["key"]), None)
    return {"sequence_len": len(passes), "duration_s": steps[-1]["t"], "play_pattern": shot["play_pattern"],
            "body_part": shot["shot_body_part"], "technique": shot["shot_technique"],
            "shot_distance": round(math.hypot(120 - shot["x"], 40 - shot["y"]), 1),
            "under_pressure": bool(shot["under_pressure"]), "first_time": bool(shot["shot_first_time"]),
            "rebound": rebound, "assist_player": key["player"] if key else None,
            "defensive_line_height": None if line is None else round(120 - line, 1),
            "gap_to_line": None if line is None or key is None else round(key["to"][0] - line, 1)}


def build_moments(df: pd.DataFrame, three_sixty: list[dict[str, Any]] | None, home: str,
                  cfg: dict[str, Any]) -> dict[str, Any]:
    """moments.json (explanations are added by the explanation stage)."""
    reg = regulation(df)
    f360 = index_360(three_sixty)
    chosen = select_moments(detect_candidates(reg, home, cfg["moment_xg_threshold"]),
                            cfg["max_moments"], cfg["min_gap_s"])
    moments = []
    for i, c in enumerate(chosen, 1):
        m = {k: v for k, v in c.items() if k not in ("score", "clock_s", "index")}
        m["id"] = f"m{i:02d}"
        m.update(sequence=[], snapshots={"key_pass": None, "shot": None}, facts={}, explanation=None, highlights_url=None)
        if c["type"] in ("goal", "penalty", "shot") and not c["is_penalty"]:
            shot = reg[reg["id"] == c["event_id"]].iloc[0]
            steps, rebound = build_sequence(reg, shot)
            m["sequence"] = steps
            m["snapshots"] = moment_snapshots(shot, steps, f360) if f360 else m["snapshots"]
            m["facts"] = moment_facts(shot, steps, m["snapshots"], rebound)
        elif c["is_penalty"]:
            m["facts"] = {"is_penalty": True, "outcome": c["outcome"]}
        elif c["type"] == "red_card":
            m["facts"] = {"card": c["card"]}
        moments.append(m)
    return {"moments": moments, "has_360": bool(f360)}
