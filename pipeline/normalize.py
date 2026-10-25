"""Flatten raw StatsBomb events into a clean table; coordinate helpers (FR-D3, FR-D4).

Pitch frame: 120 x 80, every team's events are oriented so it attacks toward x = 120.
Period 5 is the penalty shootout and never counts as play.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

PITCH_X, PITCH_Y = 120.0, 80.0
SHOOTOUT_PERIOD = 5
# Event types that are bookkeeping rather than play; ignored when measuring possession time.
ADMIN_TYPES = frozenset({"Starting XI", "Half Start", "Half End", "Substitution", "Tactical Shift",
                         "Referee Ball-Drop", "Injury Stoppage", "Player Off", "Player On",
                         "Camera On", "Camera off", "Camera On "})


def parse_ts(ts: str) -> float:
    """'00:12:34.567' -> seconds since the start of the period."""
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def mirror_point(x: float, y: float) -> tuple[float, float]:
    """Mirror a point to the opponent's drawing orientation: x' = 120 - x, y' = 80 - y."""
    return PITCH_X - x, PITCH_Y - y


def mirror_frame(df: pd.DataFrame, pairs: tuple[tuple[str, str], ...] = (("x", "y"), ("end_x", "end_y"))) -> pd.DataFrame:
    """Return a copy of df with the given (x, y) column pairs mirrored."""
    out = df.copy()
    for xc, yc in pairs:
        out[xc] = PITCH_X - out[xc]
        out[yc] = PITCH_Y - out[yc]
    return out


def _at(v: list[float] | None, i: int) -> float | None:
    return v[i] if v and len(v) > i else None


def _name(d: dict[str, Any] | None) -> str | None:
    return d.get("name") if d else None


def flatten_event(e: dict[str, Any]) -> dict[str, Any]:
    """One raw event -> one flat row with the columns the pipeline uses."""
    p, c, s = e.get("pass") or {}, e.get("carry") or {}, e.get("shot") or {}
    card = _name((e.get("foul_committed") or {}).get("card")) or _name((e.get("bad_behaviour") or {}).get("card"))
    end = p.get("end_location") or c.get("end_location") or s.get("end_location")
    loc = e.get("location")
    return {
        "id": e["id"], "index": e["index"], "period": e["period"], "ts": parse_ts(e["timestamp"]),
        "minute": e["minute"], "second": e["second"], "type": e["type"]["name"], "duration": e.get("duration"),
        "team": e["team"]["name"], "team_id": e["team"]["id"],
        "player": _name(e.get("player")), "player_id": (e.get("player") or {}).get("id"),
        "position": _name(e.get("position")),
        "possession": e["possession"], "possession_team": _name(e.get("possession_team")),
        "play_pattern": _name(e.get("play_pattern")),
        "x": _at(loc, 0), "y": _at(loc, 1), "end_x": _at(end, 0), "end_y": _at(end, 1),
        "under_pressure": bool(e.get("under_pressure")),
        "pass_outcome": _name(p.get("outcome")), "pass_type": _name(p.get("type")),
        "pass_recipient": _name(p.get("recipient")),
        "shot_outcome": _name(s.get("outcome")), "shot_type": _name(s.get("type")),
        "shot_xg": s.get("statsbomb_xg"), "shot_body_part": _name(s.get("body_part")),
        "shot_technique": _name(s.get("technique")), "shot_first_time": bool(s.get("first_time")),
        "shot_ff": s.get("freeze_frame"), "key_pass_id": s.get("key_pass_id"),
        "card": card,
    }


def events_frame(events: list[dict[str, Any]]) -> pd.DataFrame:
    """All events as a DataFrame ordered by StatsBomb index."""
    return pd.DataFrame([flatten_event(e) for e in events]).sort_values("index").reset_index(drop=True)


def regulation(df: pd.DataFrame) -> pd.DataFrame:
    """Open play only: periods 1-4 (normal time and extra time); the shootout is excluded."""
    return df[df["period"] != SHOOTOUT_PERIOD]


def shootout_score(df: pd.DataFrame) -> dict[str, int] | None:
    """Goals per team in period 5, or None if the match had no shootout."""
    so = df[(df["period"] == SHOOTOUT_PERIOD) & (df["type"] == "Shot")]
    if so.empty:
        return None
    return {t: int((g["shot_outcome"] == "Goal").sum()) for t, g in so.groupby("team")}
