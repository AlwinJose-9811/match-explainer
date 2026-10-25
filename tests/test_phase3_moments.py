"""Tests for key moments, build-up sequences and 360 snapshots (TC-14 to TC-17, TC-21 data part)."""
from __future__ import annotations

import pytest

from pipeline.config import load_config, raw_dir
from pipeline.load import load_match
from pipeline.moments import build_moments, select_moments
from pipeline.normalize import events_frame
from pipeline.snapshots import snapshot
from pipeline.validate import validate_json

CFG = load_config()
RAW = raw_dir(CFG)
needs_data = pytest.mark.skipif(not (RAW / "competitions.json").exists(), reason="raw data not fetched")
IDS = [m["match_id"] for m in CFG["matches"]]
DEMO = CFG["default_match_id"]


def cand(clock_s, score, goal=False):
    return {"clock_s": float(clock_s), "score": float(score), "is_goal": goal, "id": f"{clock_s}"}


def test_cap_gap_and_goals_always_kept():  # TC-15 (unit)
    cands = [cand(100, 100, True), cand(130, 100, True), cand(500, 25), cand(520, 24), cand(900, 22),
             cand(1500, 21), cand(2000, 20), cand(2500, 19)]
    kept = select_moments(cands, max_moments=4, min_gap_s=60)
    assert len(kept) == 4
    assert [k["clock_s"] for k in kept] == sorted(k["clock_s"] for k in kept)
    assert {100.0, 130.0} <= {k["clock_s"] for k in kept}  # two goals 30 s apart both survive the gap rule
    non_goals = [k for k in kept if not k["is_goal"]]
    assert 520 not in {k["clock_s"] for k in non_goals}  # within 60 s of the 500 s moment
    assert len(select_moments([cand(i, 100, True) for i in range(0, 600, 60)], 3, 60)) == 10  # goals exceed the cap


def test_snapshot_roles_and_offside_line():  # TC-21 (unit)
    frame = [{"teammate": True, "actor": True, "keeper": False, "location": [80, 40]},
             {"teammate": True, "actor": False, "keeper": False, "location": [70, 30]},
             {"teammate": True, "actor": False, "keeper": True, "location": [5, 40]},
             {"teammate": False, "actor": False, "keeper": False, "location": [92.3, 38]},
             {"teammate": False, "actor": False, "keeper": False, "location": [88, 45]},
             {"teammate": False, "actor": False, "keeper": True, "location": [118, 40]}]
    s = snapshot(frame)
    assert [p["role"] for p in s["players"]] == ["attacker", "attacker", "own_keeper", "defender", "defender", "keeper"]
    assert s["offside_line_x"] == 92.3
    assert snapshot(frame[:4])["offside_line_x"] is None  # one visible defender is not enough
    assert snapshot(None) is None and snapshot([]) is None


@pytest.fixture(scope="module")
def built():
    out = {}
    for mid in IDS:
        d = load_match(RAW, mid)
        df = events_frame(d.events)
        home = d.record["home_team"]["home_team_name"]
        out[mid] = (d, df, build_moments(df, d.three_sixty, home, CFG))
    return out


@needs_data
def test_demo_has_exactly_six_goal_moments(built):  # TC-14
    goals = [m for m in built[DEMO][2]["moments"] if m["is_goal"]]
    assert len(goals) == 6
    assert [m["clock"] for m in goals] == ["22:24", "35:22", "79:24", "80:59", "107:58", "117:05"]
    assert sum(m["is_penalty"] for m in goals) == 3


@needs_data
@pytest.mark.parametrize("mid", IDS)
def test_goal_moments_equal_the_score_and_schema_is_valid(built, mid):  # TC-14, TC-16
    d, _, mom = built[mid]
    validate_json(mom, "moments")
    r = d.record
    goals = [m for m in mom["moments"] if m["is_goal"]]
    assert len(goals) == r["home_score"] + r["away_score"]
    for side, n in (("home", r["home_score"]), ("away", r["away_score"])):
        assert sum(m["team"] == side for m in goals) == n


@needs_data
@pytest.mark.parametrize("mid", IDS)
def test_moment_count_and_spacing(built, mid):  # TC-15
    moments = built[mid][2]["moments"]
    goals = sum(m["is_goal"] for m in moments)
    assert len(moments) <= max(CFG["max_moments"], goals)
    assert [(m["period"], m["minute"], m["second"]) for m in moments] == sorted(
        (m["period"], m["minute"], m["second"]) for m in moments)
    for o in (m for m in moments if not m["is_goal"]):
        for m in moments:
            if m is not o and m["period"] == o["period"]:
                assert abs((o["minute"] * 60 + o["second"]) - (m["minute"] * 60 + m["second"])) >= CFG["min_gap_s"] - 1


@needs_data
@pytest.mark.parametrize("mid", IDS)
def test_sequences_share_possession_and_end_at_the_shot(built, mid):  # TC-17
    d, df, mom = built[mid]
    by_id = df.set_index("id")
    for m in mom["moments"]:
        if not m["sequence"]:
            assert m["is_penalty"] or m["type"] in ("red_card", "own_goal")
            continue
        seq = m["sequence"]
        assert seq[-1]["kind"] == "shot" and seq[-1]["event_id"] == m["event_id"]
        assert len(seq) <= 13  # at most 12 drawn actions plus the shot
        shot = by_id.loc[m["event_id"]]
        for s in seq:
            e = by_id.loc[s["event_id"]]
            assert e["possession"] == shot["possession"] and e["team"] == shot["team"] and e["period"] == shot["period"]
            assert e["index"] <= shot["index"]
        assert [s["t"] for s in seq] == sorted(s["t"] for s in seq)
        assert sum(s["key"] for s in seq) <= 1


@needs_data
def test_penalties_have_no_sequence_or_snapshot(built):
    for mid in IDS:
        for m in built[mid][2]["moments"]:
            if m["is_penalty"]:
                assert m["sequence"] == [] and m["snapshots"] == {"key_pass": None, "shot": None}


@needs_data
def test_red_card_detected_on_morocco_portugal(built):
    reds = [m for m in built[3869486][2]["moments"] if m["type"] == "red_card"]
    assert len(reds) == 1 and reds[0]["player"] == "Walid Cheddira" and reds[0]["facts"]["card"] == "Second Yellow"


@needs_data
def test_open_play_goals_have_snapshots_and_line_is_max_defender_x(built):  # TC-21
    for mid in IDS:
        for m in built[mid][2]["moments"]:
            if m["is_goal"] and not m["is_penalty"]:
                snap = m["snapshots"]["shot"]
                assert snap and snap["players"], (mid, m["clock"])
                for s in (m["snapshots"]["key_pass"], snap):
                    if s and s["offside_line_x"] is not None:
                        assert s["offside_line_x"] == max(p["x"] for p in s["players"] if p["role"] == "defender")


@needs_data
def test_known_goal_facts_in_the_final(built):
    ms = {m["clock"]: m for m in built[DEMO][2]["moments"]}
    di_maria = ms["35:22"]
    assert di_maria["player"].startswith("Ángel Fabián Di María") and di_maria["facts"]["play_pattern"] == "From Counter"
    assert di_maria["facts"]["sequence_len"] >= 3 and sum(s["key"] for s in di_maria["sequence"]) == 1
    rebound = ms["107:58"]
    assert rebound["facts"]["rebound"] is True
    assert ms["80:59"]["xg_statsbomb"] == pytest.approx(0.10, abs=0.01)
