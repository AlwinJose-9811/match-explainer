"""Tests for the replay engine, moments page and model card (TC-18 to TC-22 static/data parts)."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from pipeline.config import ROOT, load_config

WEB = ROOT / "web"
CFG = load_config()
IDS = [m["match_id"] for m in CFG["matches"]]
replay_js = (WEB / "js" / "replay.js").read_text(encoding="utf8")
moments_js = (WEB / "js" / "moments.js").read_text(encoding="utf8")
node = shutil.which("node")

NODE_TEST = r"""
import { timeline, stepText, trackAt } from 'file:///%s/web/js/replay.js';
const steps = [{kind:'pass',t:0,dur:1.2,player:'A',recipient:'B',from:[1,1],to:[2,2]},{kind:'carry',t:1.5,dur:9,player:'B',from:[2,2],to:[3,3]},
  {kind:'pass',t:10,dur:0.8,player:'B',recipient:'C',from:[3,3],to:[4,4],key:true},{kind:'pass',t:10.5,dur:null,player:'C',recipient:'D',from:[4,4],to:[5,5]},
  {kind:'shot',t:14,dur:0.3,player:'D',from:[5,5],to:[120,40],outcome:'Goal'}];
const tl = timeline(steps);
const track = {pts: [[0, 10, 10], [2, 20, 10], [4, 20, 30]]};
const at = t => trackAt(track, t);
console.log(JSON.stringify({starts: tl.map(x => x.start), ends: tl.map(x => +x.end.toFixed(3)),
  mid: at(1), fadeIn: at(-0.2), fadeOut: at(4.4), gone: [at(-1), at(6)], text: steps.map((s, i) => stepText(s, n => n, i))}));
"""


def run_node(code: str) -> dict:
    out = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(node is None, reason="node not installed")
def test_timeline_runs_in_real_time_and_tracks_fade_in_and_out():  # FR-A1
    r = run_node(NODE_TEST % ROOT.as_posix())
    assert r["starts"] == [0, 1.5, 10, 10.5, 14]                       # each step starts at its event time
    assert r["ends"] == [1.2, 10, 10.5, 11.3, 14.3]                    # real duration, but never past the next step's start; missing dur = 0.8 s
    assert r["mid"]["x"] == 15 and r["mid"]["opacity"] == 1            # linear between snapshots
    assert 0 < r["fadeIn"]["opacity"] < 1 and 0 < r["fadeOut"]["opacity"] < 1 and r["gone"] == [None, None]
    assert r["text"][2].endswith("the key pass") and "shoots (goal!)" in r["text"][4]


@pytest.mark.skipif(node is None, reason="node not installed")
def test_real_moment_timelines_are_short_and_inside_the_pitch():
    code = r"""
import { timeline } from 'file:///%s/web/js/replay.js';
import fs from 'node:fs';
const out = {max: 0, n: 0, bad: []};
for (const id of %s) {
  const d = JSON.parse(fs.readFileSync('%s/web/data/' + id + '/moments.json', 'utf8'));
  for (const m of d.moments) { if (!m.sequence.length) continue; const tl = timeline(m.sequence); out.n++; out.max = Math.max(out.max, tl.at(-1).end);
    for (const s of m.sequence) for (const p of [s.from, s.to]) if (p[0] < -1 || p[0] > 121 || p[1] < -1 || p[1] > 81) out.bad.push([id, m.clock, p]); }
}
console.log(JSON.stringify(out));
""" % (ROOT.as_posix(), json.dumps(IDS), ROOT.as_posix())
    r = run_node(code)
    assert r["n"] >= 10 and r["max"] < 35 and not r["bad"], r


def test_replay_has_required_controls_and_reduced_motion_mode():  # FR-A2, FR-A3, FR-A6
    for needle in ("Play replay", "Pause replay", "Restart replay", "[0.5, '0.5x']", "[1, '1x']", "[2, '2x']", "type: 'range'",
                   "prefers-reduced-motion", "Previous step", "Next step", "KEY PASS", "requestAnimationFrame"):
        assert needle in replay_js, needle
    assert "aria-live" in replay_js and "aria-label" in replay_js and "aria-valuetext" in replay_js


def test_replay_separates_ball_from_players_and_shows_both_teams():  # owner request: ball clearly visible, opposition + runs
    for needle in ("Other players", "Runs", "Last defender line", "Freeze at the key pass", "Freeze at the shot", "visible_players",
                   "Last visible defender", "movement", "trackAt", "defendSide"):
        assert needle in replay_js, needle
    # layer order: players are appended before the ball layer so the ball is always on top
    assert replay_js.index("svg.append(lineLayer, playerLayer, ballLayer)") > 0
    assert "white casing" in replay_js


def test_moments_page_filters_goals_and_labels_output():  # FR-K5, FR-E5
    assert "Goals only" in moments_js and "Automated analysis" not in moments_js.replace("exp.label", "")  # label comes from data
    assert "term('automated', exp.label)" in moments_js and "listenButton" in moments_js


def test_model_card_renders_from_metrics_and_names_limits():  # FR-X7
    js = (WEB / "js" / "model.js").read_text(encoding="utf8")
    for needle in ("model/xg_metrics.json", "Limits", "calibration", "permutation_importance", "baseline_distance_angle", "statsbomb_xg"):
        assert needle in js, needle
    m = json.loads((WEB / "data" / "model" / "xg_metrics.json").read_text(encoding="utf8"))
    assert m["beats_distance_angle_baseline"] is True


def test_moments_json_in_web_has_name_map_for_all_players():
    for mid in IDS:
        d = json.loads((WEB / "data" / str(mid) / "moments.json").read_text(encoding="utf8"))
        names = d["names"]
        for m in d["moments"]:
            for s in m["sequence"]:
                assert s["player"] in names and (s["recipient"] is None or s["recipient"] in names)
