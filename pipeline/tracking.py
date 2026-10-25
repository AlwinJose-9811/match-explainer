"""Estimated off-the-ball movement for a build-up, reconstructed from 360 freeze frames.

The data has NO full tracking: each on-ball event carries one anonymous snapshot of the players visible on
the TV picture. This module (1) puts every snapshot into the attacking team's frame, (2) links the same player
across consecutive snapshots (Hungarian matching with a speed gate), (3) smooths each path in time, and
(4) names tracks where an event's actor is known. The result is an estimate: it shows visible players only and
straight-ish paths between snapshots. `quality` reports how much data backed it.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

MAX_SPEED = 9.5    # yards per second a player can plausibly cover over a gap (about 8.7 m/s)
GATE_BASE = 2.0    # yards of slack for measurement noise in a snapshot
LOST_S = 4.0       # a track unseen for longer than this can no longer be matched
SIGMA = 0.6        # seconds, width of the smoothing kernel
LEAD_S = 1.0       # snapshots up to this long before the first pass are used
BIG = 1e6


def to_attacking_frame(x: float, y: float, event_is_attacking_team: bool) -> tuple[float, float]:
    """Events of the other team are recorded in that team's own frame (it attacks toward x = 120): mirror them."""
    return (x, y) if event_is_attacking_team else (120.0 - x, 80.0 - y)


def split_frame(frame: list[dict[str, Any]], event_is_attacking: bool, actor_name: str | None) -> dict[str, list[dict[str, Any]]]:
    """One snapshot -> attackers and defenders in the attacking team's frame (flags are relative to the event's team)."""
    out: dict[str, list[dict[str, Any]]] = {"att": [], "def": []}
    for p in frame:
        x, y = to_attacking_frame(p["location"][0], p["location"][1], event_is_attacking)
        mate = bool(p.get("actor") or p.get("teammate"))
        side = "att" if mate == event_is_attacking else "def"
        out[side].append({"x": x, "y": y, "keeper": bool(p.get("keeper")),
                          "name": actor_name if p.get("actor") else None})
    return out


def _predict(tr: dict[str, Any], dt: float) -> tuple[float, float]:
    """Where a track should be `dt` seconds after its last sighting, from its recent velocity (capped)."""
    t1, x1, y1 = tr["last"]
    earlier = [p for p in tr["pts"] if t1 - p[0] >= 0.4]
    if not earlier:
        return x1, y1
    t0, x0, y0 = earlier[-1]
    vx, vy = (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
    v = math.hypot(vx, vy)
    if v > 8.0:
        vx, vy = vx * 8.0 / v, vy * 8.0 / v
    return x1 + vx * min(dt, 3.0), y1 + vy * min(dt, 3.0)


def _match(tracks: list[dict[str, Any]], pts: list[dict[str, Any]], t: float) -> dict[int, dict[str, Any]]:
    """Assign snapshot players to live tracks by minimum total distance within a speed gate."""
    live = [tr for tr in tracks if 0 <= t - tr["last"][0] <= LOST_S]
    if not live or not pts:
        return {}
    cost = np.full((len(live), len(pts)), BIG)
    for i, tr in enumerate(live):
        dt = t - tr["last"][0]
        gate = GATE_BASE + MAX_SPEED * dt
        px, py = _predict(tr, dt)
        for j, p in enumerate(pts):
            if tr["keeper"] != p["keeper"] or (p["name"] and tr["name"] and p["name"] != tr["name"]):
                continue   # a keeper stays a keeper; a named player can only be his own track
            d = math.hypot(tr["last"][1] - p["x"], tr["last"][2] - p["y"])
            if d <= gate:
                c = 0.5 * d + 0.5 * math.hypot(px - p["x"], py - p["y"])
                cost[i, j] = c * (0.1 if p["name"] and p["name"] == tr["name"] else 1.0)   # known actors stick to their track
    rows, cols = linear_sum_assignment(cost)
    return {int(j): live[int(i)] for i, j in zip(rows, cols) if cost[i, j] < BIG}


def track_side(frames: list[tuple[float, list[dict[str, Any]]]], prefix: str) -> list[dict[str, Any]]:
    """Link one side's players across time-ordered snapshots into tracks of (t, x, y)."""
    tracks: list[dict[str, Any]] = []
    for t, pts in frames:
        got = _match(tracks, pts, t)
        for j, p in enumerate(pts):
            tr = got.get(j)
            if tr is None:
                tr = {"id": f"{prefix}{len(tracks) + 1}", "keeper": p["keeper"], "name": None, "pts": [], "last": None}
                tracks.append(tr)
            tr["pts"].append((t, p["x"], p["y"]))
            tr["last"] = (t, p["x"], p["y"])
            tr["name"] = tr["name"] or p["name"]
    return tracks


def smooth(pts: list[tuple[float, float, float]], sigma: float = SIGMA) -> list[tuple[float, float, float]]:
    """Gaussian smoothing in time (removes snapshot noise, bounds apparent speed); times are kept."""
    if len(pts) < 3:
        return pts
    t, x, y = (np.array(c) for c in zip(*pts))
    out = []
    for i in range(len(pts)):
        w = np.exp(-((t - t[i]) ** 2) / (2 * sigma * sigma))
        out.append((float(t[i]), float((w * x).sum() / w.sum()), float((w * y).sum() / w.sum())))
    return out


def max_speed(pts: list[tuple[float, float, float]], min_dt: float = 0.3) -> float:
    s = [math.hypot(b[1] - a[1], b[2] - a[2]) / (b[0] - a[0]) for a, b in zip(pts, pts[1:]) if b[0] - a[0] >= min_dt]
    return max(s, default=0.0)


def build_movement(frames: list[dict[str, Any]], t0: float, jerseys: dict[str, int] | None = None) -> dict[str, Any] | None:
    """frames: [{t (absolute seconds), att, def}] from split_frame. Returns the `movement` object, or None."""
    frames = sorted(frames, key=lambda f: f["t"])
    if len(frames) < 2:
        return None
    tracks = track_side([(f["t"], f["att"]) for f in frames], "a") + track_side([(f["t"], f["def"]) for f in frames], "d")
    out, speeds = [], []
    for tr in tracks:
        if len(tr["pts"]) < 2:
            continue
        pts = smooth(tr["pts"])
        speeds.append(max_speed(pts))
        out.append({"id": tr["id"], "side": "att" if tr["id"].startswith("a") else "def", "keeper": tr["keeper"],
                    "name": tr["name"], "jersey": (jerseys or {}).get(tr["name"]) if tr["name"] else None,
                    "pts": [[round(t - t0, 2), round(float(np.clip(x, -2, 122)), 1), round(float(np.clip(y, -2, 82)), 1)] for t, x, y in pts]})
    if not out:
        return None
    return {"t_start": round(frames[0]["t"] - t0, 2), "t_end": round(frames[-1]["t"] - t0, 2), "tracks": out,
            "quality": {"snapshots": len(frames), "tracks": len(out),
                        "avg_visible": round(float(np.mean([len(f["att"]) + len(f["def"]) for f in frames])), 1),
                        "max_gap_s": round(max((b["t"] - a["t"] for a, b in zip(frames, frames[1:])), default=0.0), 1),
                        "max_speed": round(max(speeds, default=0.0), 1)}}
