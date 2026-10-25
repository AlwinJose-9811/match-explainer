"""Integration tests on the real StatsBomb data (TC-04, 06, 07, 08); skipped if the data is absent."""
from __future__ import annotations

import json

import pytest

from pipeline.config import load_config, raw_dir
from pipeline.load import load_match
from pipeline.metrics import build_summary
from pipeline.normalize import events_frame
from pipeline.validate import validate_json

CFG = load_config()
RAW = raw_dir(CFG)
pytestmark = pytest.mark.skipif(not (RAW / "competitions.json").exists(), reason="raw data not fetched")
MATCHES = [m["match_id"] for m in CFG["matches"]]
DEMO = CFG["default_match_id"]


@pytest.fixture(scope="module")
def demo():
    data = load_match(RAW, DEMO)
    df = events_frame(data.events)
    return data, df, build_summary(data, df)


def test_score_equals_matches_file_and_shootout_separate(demo):  # TC-06
    data, _, s = demo
    assert (s["score"]["home"], s["score"]["away"]) == (data.record["home_score"], data.record["away_score"]) == (3, 3)
    assert s["score"]["shootout"] == {"home": 4, "away": 2}


def test_goals_start_in_attacking_half(demo):  # TC-04
    _, df, _ = demo
    goals = df[(df["type"] == "Shot") & (df["shot_outcome"] == "Goal") & (df["period"] != 5)]
    assert len(goals) == 6
    assert (goals["x"] >= 80).all()


def test_possession_is_100_percent_with_method(demo):  # TC-08
    s = demo[2]["possession"]
    assert s["home"] + s["away"] == pytest.approx(1.0)
    assert s["method"]


def test_no_possession_is_implausibly_long(demo):
    _, df, _ = demo
    from pipeline.normalize import ADMIN_TYPES, regulation
    play = regulation(df)
    play = play[~play["type"].isin(ADMIN_TYPES)]
    play = play[play["ts"] >= play.groupby("period")["ts"].cummax() - 1.0]
    g = play.groupby(["period", "possession"])["ts"]
    assert (g.max() - g.min()).max() < 300


def test_stats_match_independent_recount(demo):  # TC-07
    data, _, s = demo
    for side, team in (("home", s["teams"]["home"]["name"]), ("away", s["teams"]["away"]["name"])):
        raw = [e for e in data.events if e["team"]["name"] == team and e["period"] != 5]
        shots = [e for e in raw if e["type"]["name"] == "Shot"]
        passes = [e for e in raw if e["type"]["name"] == "Pass"]
        cards = [(e.get("foul_committed") or e.get("bad_behaviour") or {}).get("card", {}).get("name") for e in raw]
        st = s["stats"][side]
        assert st["shots"] == len(shots)
        assert st["on_target"] == sum(e["shot"]["outcome"]["name"] in ("Goal", "Saved", "Saved to Post") for e in shots)
        assert st["passes"] == len(passes)
        assert st["passes_completed"] == sum("outcome" not in e["pass"] for e in passes)
        assert st["yellow"] == sum(c in ("Yellow Card", "Second Yellow") for c in cards)
        assert st["red"] == sum(c in ("Red Card", "Second Yellow") for c in cards)
        assert st["fouls"] == sum(e["type"]["name"] == "Foul Committed" for e in raw)
        assert st["corners"] == sum(e.get("pass", {}).get("type", {}).get("name") == "Corner" for e in passes)


def test_summary_validates_against_schema(demo):
    validate_json(demo[2], "summary")


@pytest.mark.parametrize("match_id", MATCHES)
def test_every_picker_match_builds_with_correct_score(match_id):
    data = load_match(RAW, match_id)
    s = build_summary(data, events_frame(data.events))
    validate_json(s, "summary")
    want = next(m for m in CFG["matches"] if m["match_id"] == match_id)["expect"]
    assert (s["score"]["home"], s["score"]["away"]) == (want["home_score"], want["away_score"])
    assert s["possession"]["home"] + s["possession"]["away"] == pytest.approx(1.0)
