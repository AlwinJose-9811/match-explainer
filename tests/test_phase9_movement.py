"""Tests for the off-the-ball movement reconstruction (360 snapshots -> estimated tracks)."""
from __future__ import annotations

import json
import math

import pytest

from pipeline.config import ROOT, load_config
from pipeline.tracking import (build_movement, max_speed, smooth, split_frame, to_attacking_frame, track_side)

CFG = load_config()
IDS = [m["match_id"] for m in CFG["matches"]]


def pt(x, y, keeper=False, name=None):
    return {"x": x, "y": y, "keeper": keeper, "name": name}


def test_opposition_snapshots_are_mirrored_into_the_attacking_frame():
    assert to_attacking_frame(100, 30, True) == (100, 30)
    assert to_attacking_frame(100, 30, False) == (20, 50)
    # an event by the DEFENDING team: its teammate flags mean "defender", and its coordinates are in its own frame
    frame = [{"location": [30, 40], "teammate": True, "actor": True, "keeper": False},    # the defender who acted
             {"location": [10, 20], "teammate": False, "actor": False, "keeper": False}]  # an attacker (opponent of the event team)
    out = split_frame(frame, event_is_attacking=False, actor_name="Defender D")
    assert [(p["x"], p["y"], p["name"]) for p in out["def"]] == [(90.0, 40.0, "Defender D")]
    assert [(p["x"], p["y"]) for p in out["att"]] == [(110.0, 60.0)]
    # an event by the attacking team
    out = split_frame(frame, event_is_attacking=True, actor_name="Attacker A")
    assert [(p["x"], p["y"], p["name"]) for p in out["att"]] == [(30, 40, "Attacker A")]
    assert [(p["x"], p["y"]) for p in out["def"]] == [(10, 20)]


def test_same_player_is_linked_across_snapshots_and_crossing_paths_do_not_swap():
    # two players run towards each other along different lanes and cross at t = 2
    frames = [(float(t), [pt(10 + 5 * t, 20), pt(30 - 5 * t, 22)]) for t in range(0, 5)]
    tracks = track_side(frames, "a")
    assert len(tracks) == 2
    for tr in tracks:
        ys = {round(p[2]) for p in tr["pts"]}
        assert len(ys) == 1 and len(tr["pts"]) == 5   # each track keeps its own lane


def test_named_actor_only_matches_his_own_track_and_keepers_stay_keepers():
    frames = [(0.0, [pt(50, 40, name="Ann"), pt(52, 40)]), (1.0, [pt(51, 40), pt(53, 40, name="Ann")])]
    tracks = track_side(frames, "a")
    ann = next(t for t in tracks if t["name"] == "Ann")
    assert [p[1] for p in ann["pts"]] == [50, 53]   # followed the NAME, not the nearest dot
    k = track_side([(0.0, [pt(5, 40, keeper=True)]), (1.0, [pt(6, 40), pt(5.5, 40, keeper=True)])], "d")
    assert [t["keeper"] for t in k] == [True, False] and len(k[0]["pts"]) == 2


def test_players_cannot_teleport_and_lost_players_start_new_tracks():
    tracks = track_side([(0.0, [pt(10, 10)]), (0.5, [pt(60, 60)])], "a")
    assert len(tracks) == 2


def test_smoothing_keeps_times_and_reduces_noise():
    noisy = [(float(t) * 0.5, 10 + t * 2 + (1.5 if t % 2 else -1.5), 40.0) for t in range(8)]
    sm = smooth(noisy)
    assert [p[0] for p in sm] == [p[0] for p in noisy]
    assert max_speed(sm) < max_speed(noisy)


def test_build_movement_uses_times_relative_to_the_first_pass():
    frames = [{"t": 100.0 + i, "att": [pt(20 + i * 3, 30), pt(40, 50 + i)], "def": [pt(60, 40 - i)]} for i in range(4)]
    mv = build_movement(frames, 100.5, {"A": 7})
    assert mv["t_start"] == -0.5 and mv["t_end"] == 2.5 and mv["quality"]["snapshots"] == 4
    assert {t["side"] for t in mv["tracks"]} == {"att", "def"}
    assert build_movement(frames[:1], 100.0) is None


def at(pts, t):
    for a, b in zip(pts, pts[1:]):
        if a[0] <= t <= b[0]:
            f = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
    return None


@pytest.fixture(scope="module")
def all_replays():
    out = []
    for mid in IDS:
        d = json.loads((ROOT / "data" / "processed" / str(mid) / "moments.json").read_text(encoding="utf8"))
        out += [(mid, m) for m in d["moments"] if m["sequence"]]
    return out


@pytest.fixture(scope="module")
def moments(all_replays):
    return [(mid, m) for mid, m in all_replays if m["movement"]]


def test_every_real_move_has_movement_and_only_one_snapshot_moves_are_ball_only(all_replays):
    assert len(all_replays) >= 20
    for mid, m in all_replays:
        if len(m["sequence"]) >= 3:
            assert m["movement"], (mid, m["clock"])      # a multi-step move always has enough snapshots
    assert sum(1 for _, m in all_replays if m["movement"]) / len(all_replays) >= 0.85


def test_every_replay_has_movement_for_both_teams(moments):
    assert len(moments) >= 20
    for mid, m in moments:
        mv = m["movement"]
        sides = [t["side"] for t in mv["tracks"]]
        long_move = len(m["sequence"]) >= 3     # a one- or two-step move may have only two snapshots, so fewer tracks
        need_att, need_def = (4, 5) if long_move else (1, 2)
        assert sides.count("att") >= need_att and sides.count("def") >= need_def, (mid, m["clock"], sides.count("att"), sides.count("def"))
        assert mv["quality"]["avg_visible"] >= (5 if long_move else 4)   # a tight camera can show as few as 5 players at a time


def test_track_data_is_well_formed_and_speeds_plausible(moments):
    for mid, m in moments:
        mv = m["movement"]
        assert mv["t_start"] >= -1.01 and mv["t_end"] >= mv["t_start"]
        assert mv["quality"]["max_speed"] <= 16, (mid, m["clock"], mv["quality"])   # yards per second (world-class sprint is ~11)
        for tr in mv["tracks"]:
            ts = [p[0] for p in tr["pts"]]
            assert ts == sorted(ts) and all(-2 <= p[1] <= 122 and -2 <= p[2] <= 82 for p in tr["pts"])


def test_reconstruction_agrees_with_the_event_data_where_it_is_known(moments):
    """The actor's own track must pass through the position the event recorded for him."""
    errs = []
    for _, m in moments:
        named: dict[str, list] = {}
        for t in m["movement"]["tracks"]:
            if t["name"]:
                named.setdefault(t["name"], []).append(t)
        for s in m["sequence"]:
            # a player who left the camera view and came back can have two tracks: use the one that covers this moment
            found = [p for t in named.get(s["player"], []) if t["pts"][0][0] <= s["t"] <= t["pts"][-1][0] and (p := at(t["pts"], s["t"]))]
            if found:
                errs.append(min(math.hypot(p[0] - s["from"][0], p[1] - s["from"][1]) for p in found))
    errs.sort()
    assert len(errs) >= 250
    assert errs[len(errs) // 2] < 1.5 and errs[int(len(errs) * 0.9)] < 4.0, (errs[len(errs) // 2], errs[int(len(errs) * 0.9)])


def test_goalkeepers_are_at_the_right_ends_so_the_opposition_is_mirrored_correctly(moments):
    """At the shot the defending keeper must be near the goal being attacked (x near 120), the attacking
    team's own keeper near the other end. A wrong mirror of the opposition's snapshots would flip this."""
    seen_def = seen_att = bad = 0
    for _, m in moments:
        shot_t = m["sequence"][-1]["t"]
        for tr in m["movement"]["tracks"]:
            p = tr["keeper"] and at(tr["pts"], shot_t)
            if not p:
                continue
            if tr["side"] == "def":
                seen_def += 1
                bad += p[0] < 85
            else:
                seen_att += 1
                bad += p[0] > 40
    assert seen_def >= 15, (seen_def, seen_att)   # the attacking keeper is almost never on camera, so it is not required
    assert bad <= 0.1 * (seen_def + seen_att), (bad, seen_def, seen_att)


def test_moments_files_stay_small():
    for mid in IDS:
        assert (ROOT / "data" / "processed" / str(mid) / "moments.json").stat().st_size < 1_500_000
