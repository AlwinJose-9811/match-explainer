"""Average positions, lines and shape per time window (FR-P2 to FR-P5, MX-03 sections 6.2, 6.3).

Caveat shown in the UI: positions are averages of where players touched the ball (event data),
so they lean towards where the team had the ball, not where players stood.
Lines are computed in each team's own frame (attacking toward x = 120); the away team's drawn
coordinates are then mirrored (x' = 120 - x, y' = 80 - y).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from .normalize import PITCH_X, PITCH_Y, mirror_point, regulation

ON_BALL = ("Pass", "Carry", "Shot", "Ball Receipt*", "Dribble", "Duel", "Interception", "Clearance")
MIN_SAMPLES = 5  # on-ball events a player needs in a window to get an average position
MIN_GROUP = 2    # players a role group needs in a window before its line is reported
GROUPS = ("def", "mid", "att")


def role_group(position: str | None) -> str | None:
    """Map a StatsBomb position name to GK / DEF / MID / ATT."""
    if not position:
        return None
    if position == "Goalkeeper":
        return "GK"
    if "Back" in position:  # Center Back, Left Back, Right Wing Back ...
        return "DEF"
    if "Midfield" in position:
        return "MID"
    if "Wing" in position or "Forward" in position or "Striker" in position:
        return "ATT"
    return None


def player_directory(lineups: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """player_id -> display name and shirt number from the lineups file."""
    out: dict[int, dict[str, Any]] = {}
    for team in lineups:
        for p in team["lineup"]:
            out[p["player_id"]] = {"name": p.get("player_nickname") or p["player_name"],
                                   "jersey": p.get("jersey_number")}
    return out


def make_windows(end_minute: int, has_extra_time: bool, length: int, step: int) -> list[dict[str, Any]]:
    """Named windows plus sliding windows of `length` minutes every `step` minutes up to the end."""
    wins: list[dict[str, Any]] = [
        {"id": "full", "label": "Full match", "start": 0, "end": end_minute, "kind": "full"},
        {"id": "p1", "label": "First half", "start": 0, "end": 45, "kind": "period"},
        {"id": "p2", "label": "Second half", "start": 45, "end": 90, "kind": "period"}]
    if has_extra_time:
        wins.append({"id": "et", "label": "Extra time", "start": 90, "end": end_minute, "kind": "period"})
    starts = list(range(0, max(end_minute - length, 0) + 1, step))
    if starts[-1] + length < end_minute:
        starts.append(end_minute - length)
    wins += [{"id": f"m{s}_{s + length}", "label": f"{s}-{s + length} min", "start": s,
              "end": s + length, "kind": "slide"} for s in starts]
    return wins


def _window_events(df: pd.DataFrame, w: dict[str, Any]) -> pd.DataFrame:
    if w["id"] == "p1":
        return df[df["period"] == 1]
    if w["id"] == "p2":
        return df[df["period"] == 2]
    if w["id"] == "et":
        return df[df["period"] >= 3]
    if w["kind"] == "full":
        return df
    return df[(df["minute"] >= w["start"]) & (df["minute"] < w["end"])]


def team_players(ev: pd.DataFrame, directory: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Average position, role and sample count per player (own frame); drops players under MIN_SAMPLES."""
    rows = []
    for pid, g in ev.groupby("player_id"):
        if len(g) < MIN_SAMPLES:
            continue
        d = directory.get(int(pid), {})
        pos = g["position"].dropna()
        rows.append({"id": int(pid), "name": d.get("name") or g["player"].iat[0], "jersey": d.get("jersey"),
                     "role": role_group(pos.mode().iat[0]) if len(pos) else None,
                     "x": float(g["x"].mean()), "y": float(g["y"].mean()), "n": int(len(g))})
    return rows


def lines_and_shape(players: list[dict[str, Any]], thresholds: list[float]) -> tuple[dict, dict | None]:
    """Line height per group, then length / width / compactness / block label (own frame)."""
    lines = {}
    for grp in GROUPS:
        xs = [p["x"] for p in players if p["role"] == grp.upper()]
        lines[grp] = round(float(np.mean(xs)), 1) if len(xs) >= MIN_GROUP else None
    outfield = [p for p in players if p["role"] in ("DEF", "MID", "ATT")]
    if lines["def"] is None or lines["att"] is None or not outfield:
        return lines, None
    length = lines["att"] - lines["def"]
    low, high = thresholds
    label = "low block" if lines["def"] < low else ("mid block" if lines["def"] <= high else "high line")
    return lines, {"length": round(length, 1),
                   "width": round(max(p["y"] for p in outfield) - min(p["y"] for p in outfield), 1),
                   "compact": round(float(np.clip(1 - length / PITCH_Y, 0, 1)), 2), "label": label}


def kmeans_agreement(players: list[dict[str, Any]], seed: int) -> float | None:
    """Share of outfield players whose 1-D k-means (k=3) cluster rank matches their role group."""
    outfield = [p for p in players if p["role"] in ("DEF", "MID", "ATT")]
    if len(outfield) < 6:
        return None
    xs = np.array([[p["x"]] for p in outfield])
    km = KMeans(n_clusters=3, n_init=10, random_state=seed).fit(xs)
    rank = {c: r for r, c in enumerate(np.argsort(km.cluster_centers_[:, 0]))}
    want = {"DEF": 0, "MID": 1, "ATT": 2}
    return round(float(np.mean([rank[l] == want[p["role"]] for l, p in zip(km.labels_, outfield)])), 2)


def _draw_frame(players: list[dict[str, Any]], mirrored: bool) -> list[dict[str, Any]]:
    out = []
    for p in players:
        x, y = mirror_point(p["x"], p["y"]) if mirrored else (p["x"], p["y"])
        out.append({**p, "x": round(x, 1), "y": round(y, 1)})
    return out


def build_positions(df: pd.DataFrame, lineups: list[dict[str, Any]], home: str, away: str,
                    cfg: dict[str, Any]) -> dict[str, Any]:
    """positions.json: windows plus, per window and side, players / lines / shape."""
    reg = regulation(df)
    end = int(reg["minute"].max()) + 1
    wins = make_windows(end, bool((reg["period"] >= 3).any()), cfg["window_minutes"], cfg.get("window_step", 5))
    directory = player_directory(lineups)
    on_ball = reg[reg["type"].isin(ON_BALL) & reg["x"].notna() & reg["player_id"].notna()]
    data: dict[str, Any] = {}
    agreement: dict[str, float | None] = {}
    for w in wins:
        sub = _window_events(on_ball, w)
        data[w["id"]] = {}
        for side, team in (("home", home), ("away", away)):
            players = team_players(sub[sub["team"] == team], directory)
            lines, shape = lines_and_shape(players, cfg["block_thresholds"])
            data[w["id"]][side] = {"players": _draw_frame(players, side == "away"), "lines": lines, "shape": shape}
            if w["id"] == "full":
                agreement[side] = kmeans_agreement(players, cfg["seed"])
    return {"frame": "away team mirrored (x' = 120 - x, y' = 80 - y); lines are in each team's own frame",
            "match_end_minute": end, "window_minutes": cfg["window_minutes"], "windows": wins, "data": data,
            "diagnostics": {"kmeans_agreement_full": agreement}}
