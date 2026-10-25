"""Unit tests for loader, normaliser and metrics on synthetic events (TC-02, 03, 05, 08)."""
from __future__ import annotations

import json
import random

import pandas as pd
import pytest

from pipeline.load import DataError, load_match
from pipeline.metrics import goals_by_team, possession_share, team_stats
from pipeline.normalize import events_frame, mirror_frame, mirror_point, regulation, shootout_score
from tests.helpers import ev, sample_events


@pytest.fixture()
def df() -> pd.DataFrame:
    return events_frame(sample_events())


def test_mirror_is_an_involution():  # TC-03
    rng = random.Random(42)
    for _ in range(200):
        p = (rng.uniform(0, 120), rng.uniform(0, 80))
        x, y = mirror_point(*mirror_point(*p))
        assert (x, y) == pytest.approx(p)


def test_mirror_frame_moves_both_point_columns(df):
    m = mirror_frame(df.dropna(subset=["x"]))
    first = df.dropna(subset=["x"]).iloc[0]
    assert m.iloc[0]["x"] == 120 - first["x"] and m.iloc[0]["y"] == 80 - first["y"]


def test_shootout_excluded_and_reported_separately(df):  # TC-05, FR-D4
    assert set(regulation(df)["period"]) == {1, 2}
    assert shootout_score(df) == {"Alpha": 1, "Beta": 1}
    without = df[df["period"] != 5]
    assert possession_share(regulation(df)) == possession_share(without)
    assert team_stats(regulation(df), "Alpha") == team_stats(without, "Alpha")


def test_possession_sums_to_one(df):  # TC-08
    p = possession_share(regulation(df))
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["Alpha"] > 0 and p["Beta"] > 0


def test_reset_clock_event_cannot_stretch_a_possession():
    evs = sample_events()
    # a Ball Receipt* at the end of period 2 whose timestamp restarted at 0.3 s (seen in the real final)
    evs.insert(11, ev(11, 2, 0.3, "Ball Receipt*", "A", 6))
    evs[11]["index"] = 10.5
    p = possession_share(regulation(events_frame(evs)))
    assert p["Alpha"] == pytest.approx(possession_share(regulation(events_frame(sample_events())))["Alpha"], abs=0.02)


def test_team_stats_counts(df):
    a, b = team_stats(regulation(df), "Alpha"), team_stats(regulation(df), "Beta")
    assert (a["shots"], a["on_target"], a["passes"], a["passes_completed"]) == (1, 1, 4, 3)
    assert a["pass_accuracy"] == pytest.approx(3 / 4, abs=1e-4)
    assert (a["yellow"], a["red"], a["fouls"], a["corners"]) == (1, 0, 1, 0)
    assert (b["shots"], b["on_target"], b["passes"], b["corners"]) == (1, 1, 1, 1)
    # a Yellow Card then a Second Yellow: two yellows shown, one red
    assert (b["yellow"], b["red"], b["fouls"]) == (2, 1, 1)
    assert a["xg_statsbomb"] == pytest.approx(0.3)


def test_goals_exclude_shootout(df):
    assert goals_by_team(regulation(df)) == {"Alpha": 1}


def test_missing_events_file_names_match_and_item(tmp_path):  # TC-02
    (tmp_path / "matches" / "1").mkdir(parents=True)
    rec = {"match_id": 99, "match_date": "2020-01-01", "home_team": {}, "away_team": {}, "home_score": 0,
           "away_score": 0, "competition": {}, "season": {}}
    (tmp_path / "matches" / "1" / "1.json").write_text(json.dumps([rec]), encoding="utf8")
    (tmp_path / "lineups").mkdir()
    (tmp_path / "lineups" / "99.json").write_text("[]", encoding="utf8")
    with pytest.raises(DataError) as exc:
        load_match(tmp_path, 99)
    assert "99" in str(exc.value) and "events" in str(exc.value)


def test_missing_raw_dir_says_how_to_fix(tmp_path):
    with pytest.raises(DataError) as exc:
        load_match(tmp_path / "nope", 1)
    assert "tasks.py fetch" in str(exc.value)
