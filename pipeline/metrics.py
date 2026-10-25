"""Match statistics and the summary.json builder (FR-M1, FR-M2, FR-M4).

Definitions (shown in the UI as method notes):
- possession: per possession id, last event time minus first event time (same period, bookkeeping events
  ignored); a team's share is its summed duration divided by both teams' total.
- on target: shot outcome Goal, Saved or Saved to Post.  Pass complete: no pass outcome recorded.
- yellow counts Yellow Card and Second Yellow; red counts Red Card and Second Yellow.
- Everything covers periods 1-4; the penalty shootout (period 5) is reported separately.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .load import DataError, MatchData
from .normalize import ADMIN_TYPES, regulation, shootout_score

POSSESSION_METHOD = "sum of possession-sequence duration (penalty shootout excluded)"
ON_TARGET = ("Goal", "Saved", "Saved to Post")
HOME_COLOR, AWAY_COLOR = "#2E75B6", "#C55A11"


def possession_share(reg: pd.DataFrame) -> dict[str, float]:
    """Share of ball time per team name, summing to 1."""
    play = reg[~reg["type"].isin(ADMIN_TYPES)]
    # StatsBomb occasionally stamps an event (e.g. a final Ball Receipt*) with a reset clock; drop events
    # whose time runs backwards within a period so they cannot stretch a possession across the half.
    play = play[play["ts"] >= play.groupby("period")["ts"].cummax() - 1.0]
    g = play.groupby(["period", "possession"])
    dur = g["ts"].max() - g["ts"].min()
    owner = g["possession_team"].first()
    totals = dur.groupby(owner).sum()
    whole = float(totals.sum())
    return {str(t): (float(v) / whole if whole else 0.0) for t, v in totals.items()}


def team_stats(reg: pd.DataFrame, team: str) -> dict[str, Any]:
    """Counting stats for one team over periods 1-4."""
    mine = reg[reg["team"] == team]
    shots = mine[mine["type"] == "Shot"]
    passes = mine[mine["type"] == "Pass"]
    completed = int(passes["pass_outcome"].isna().sum())
    return {
        "shots": int(len(shots)),
        "on_target": int(shots["shot_outcome"].isin(ON_TARGET).sum()),
        "passes": int(len(passes)),
        "passes_completed": completed,
        "pass_accuracy": round(completed / len(passes), 4) if len(passes) else 0.0,
        "xg_model": None,
        "xg_statsbomb": round(float(shots["shot_xg"].fillna(0).sum()), 3),
        "fouls": int((mine["type"] == "Foul Committed").sum()),
        "corners": int((passes["pass_type"] == "Corner").sum()),
        "yellow": int(mine["card"].isin(("Yellow Card", "Second Yellow")).sum()),
        "red": int(mine["card"].isin(("Red Card", "Second Yellow")).sum()),
    }


def goals_by_team(reg: pd.DataFrame) -> dict[str, int]:
    """Goals credited to each team: shots with outcome Goal plus 'Own Goal For' events."""
    out: dict[str, int] = {}
    for team, n in reg[(reg["type"] == "Shot") & (reg["shot_outcome"] == "Goal")].groupby("team").size().items():
        out[str(team)] = int(n)
    for team, n in reg[reg["type"] == "Own Goal For"].groupby("team").size().items():
        out[str(team)] = out.get(str(team), 0) + int(n)
    return out


def _note(df: pd.DataFrame, home: str, away: str, so: dict[str, int] | None) -> str | None:
    if so is not None:
        w, l = (home, away) if so.get(home, 0) > so.get(away, 0) else (away, home)
        return f"{w} won {so.get(w, 0)}-{so.get(l, 0)} on penalties after extra time."
    if (df["period"] >= 3).any():
        return "Decided in extra time."
    return None


def build_summary(data: MatchData, df: pd.DataFrame) -> dict[str, Any]:
    """Assemble summary.json (xG model values and story are filled by later stages)."""
    rec = data.record
    home, away = rec["home_team"]["home_team_name"], rec["away_team"]["away_team_name"]
    reg = regulation(df)
    goals = goals_by_team(reg)
    if (goals.get(home, 0), goals.get(away, 0)) != (rec["home_score"], rec["away_score"]):
        raise DataError(rec["match_id"], f"goals in events {goals} differ from matches file "
                                         f"{rec['home_score']}-{rec['away_score']}")
    poss = possession_share(reg)
    ph = round(poss.get(home, 0.0), 4)
    so = shootout_score(df)
    return {
        "match_id": rec["match_id"],
        "competition": rec["competition"]["competition_name"],
        "season": rec["season"]["season_name"],
        "stage": (rec.get("competition_stage") or {}).get("name"),
        "date": rec["match_date"],
        "teams": {"home": {"id": rec["home_team"]["home_team_id"], "name": home, "color": HOME_COLOR},
                  "away": {"id": rec["away_team"]["away_team_id"], "name": away, "color": AWAY_COLOR}},
        "score": {"home": rec["home_score"], "away": rec["away_score"],
                  "shootout": None if so is None else {"home": so.get(home, 0), "away": so.get(away, 0)},
                  "note": _note(df, home, away, so)},
        "possession": {"method": POSSESSION_METHOD, "home": ph, "away": round(1 - ph, 4)},
        "stats": {"home": team_stats(reg, home), "away": team_stats(reg, away)},
        "story": None,
    }
