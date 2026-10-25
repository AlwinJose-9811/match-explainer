"""Tests for positions, lines and shape (TC-11, 12, 13) on synthetic and real data."""
from __future__ import annotations

import pytest

from pipeline.config import load_config, raw_dir
from pipeline.load import load_match
from pipeline.normalize import events_frame
from pipeline.positions import (build_positions, kmeans_agreement, lines_and_shape, make_windows, role_group)
from pipeline.validate import validate_json

CFG = load_config()
RAW = raw_dir(CFG)
needs_data = pytest.mark.skipif(not (RAW / "competitions.json").exists(), reason="raw data not fetched")


def test_role_groups():
    assert role_group("Goalkeeper") == "GK"
    for p in ("Center Back", "Left Back", "Right Wing Back"):
        assert role_group(p) == "DEF"
    for p in ("Center Defensive Midfield", "Left Midfield", "Center Attacking Midfield"):
        assert role_group(p) == "MID"
    for p in ("Left Wing", "Center Forward", "Right Center Forward"):
        assert role_group(p) == "ATT"
    assert role_group(None) is None


def _p(role, x, y=40.0):
    return {"id": 0, "name": "p", "jersey": 1, "role": role, "x": x, "y": y, "n": 10}


def test_lines_shape_and_labels():
    players = [_p("GK", 5), _p("DEF", 30, 10), _p("DEF", 34, 70), _p("MID", 55), _p("MID", 60), _p("ATT", 80, 40),
               _p("ATT", 84, 20)]
    lines, shape = lines_and_shape(players, [48, 54])
    assert lines == {"def": 32.0, "mid": 57.5, "att": 82.0}
    assert shape["label"] == "low block" and shape["length"] == 50.0 and shape["width"] == 60.0
    assert shape["compact"] == pytest.approx(0.38, abs=0.01)
    assert lines_and_shape([_p("DEF", 55), _p("DEF", 57), _p("ATT", 80), _p("ATT", 82)], [48, 54])[1]["label"] == "high line"


def test_group_with_one_player_has_no_line():
    lines, shape = lines_and_shape([_p("DEF", 30), _p("MID", 50), _p("MID", 55), _p("ATT", 80), _p("ATT", 85)], [48, 54])
    assert lines["def"] is None and shape is None


def test_windows_reach_the_end_of_extra_time():
    wins = make_windows(125, True, 15, 5)
    assert max(w["end"] for w in wins) == 125
    assert {"full", "p1", "p2", "et"} <= {w["id"] for w in wins}
    assert make_windows(96, False, 15, 5)[-1]["end"] == 96 and "et" not in {w["id"] for w in make_windows(96, False, 15, 5)}


def test_kmeans_agreement_perfect_when_roles_are_separated():
    players = [_p("DEF", 25), _p("DEF", 28), _p("DEF", 30), _p("MID", 55), _p("MID", 58), _p("MID", 60),
               _p("ATT", 85), _p("ATT", 88), _p("ATT", 90)]
    assert kmeans_agreement(players, 42) == 1.0


@pytest.fixture(scope="module")
def final():
    data = load_match(RAW, CFG["default_match_id"])
    df = events_frame(data.events)
    t = data.record
    return build_positions(df, data.lineups, t["home_team"]["home_team_name"], t["away_team"]["away_team_name"], CFG)


@needs_data
def test_positions_validate_and_cover_the_match(final):  # TC-13 (slider range)
    validate_json(final, "positions")
    assert final["match_end_minute"] >= 120
    assert max(w["end"] for w in final["windows"]) == final["match_end_minute"]


@needs_data
def test_changing_window_changes_positions(final):  # TC-11
    a = {p["id"]: (p["x"], p["y"]) for p in final["data"]["m0_15"]["home"]["players"]}
    b = {p["id"]: (p["x"], p["y"]) for p in final["data"]["m60_75"]["home"]["players"]}
    common = set(a) & set(b)
    assert common and any(a[i] != b[i] for i in common)


@needs_data
def test_line_order_def_mid_att_in_full_match(final):  # TC-12
    for side in ("home", "away"):
        ln = final["data"]["full"][side]["lines"]
        assert ln["def"] < ln["mid"] < ln["att"], (side, ln)


@needs_data
def test_drawn_players_stay_on_the_pitch_and_away_is_mirrored(final):
    for side in ("home", "away"):
        for p in final["data"]["full"][side]["players"]:
            assert 0 <= p["x"] <= 120 and 0 <= p["y"] <= 80
    # Argentina (home) attacks right, so its attackers sit at high x; France (away) is mirrored so its attackers
    # are drawn at low x.
    h = [p["x"] for p in final["data"]["full"]["home"]["players"] if p["role"] == "ATT"]
    a = [p["x"] for p in final["data"]["full"]["away"]["players"] if p["role"] == "ATT"]
    assert sum(h) / len(h) > 60 > sum(a) / len(a)


@needs_data
def test_block_labels_differ_across_matches_and_windows():  # TC-13 (labels), honest: needs >= 2 distinct labels
    labels = set()
    for m in CFG["matches"]:
        d = load_match(RAW, m["match_id"])
        r = d.record
        pos = build_positions(events_frame(d.events), d.lineups, r["home_team"]["home_team_name"],
                              r["away_team"]["away_team_name"], CFG)
        for sides in pos["data"].values():
            for v in sides.values():
                if v["shape"]:
                    labels.add(v["shape"]["label"])
    assert len(labels) >= 2
