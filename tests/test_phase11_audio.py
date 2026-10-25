"""Rendered commentary audio: every clip exists, matches its script, and is technically sound (not silent, clipped or broken).

Whether it sounds natural is for a person to judge; these tests only catch empty, clipped, stale or missing clips.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from pipeline.config import ROOT, load_config
from pipeline.voice import clip_name, settings

sf = pytest.importorskip("soundfile")
CFG = load_config()
IDS = [m["match_id"] for m in CFG["matches"]]
VOICE, SPEED, _ = settings(CFG)
WEB = ROOT / "web"


def clips():
    for mid in IDS:
        d = WEB / "data" / str(mid)
        summary = json.loads((d / "summary.json").read_text(encoding="utf8"))
        moments = json.loads((d / "moments.json").read_text(encoding="utf8"))["moments"]
        yield mid, "story", summary["story"]
        for m in moments:
            yield mid, m["id"], m["explanation"]


def test_every_story_and_moment_links_to_a_clip_made_from_its_current_script():
    n = 0
    for mid, key, obj in clips():
        n += 1
        assert obj.get("audio"), (mid, key)
        assert obj["audio"] == f"audio/{mid}/{clip_name(key, obj['speech'], VOICE, SPEED)}", (mid, key, "stale clip")
        assert (WEB / obj["audio"]).exists()
    assert n >= 30


def test_clips_are_audible_unclipped_and_a_sensible_length():
    for mid, key, obj in clips():
        x, sr = sf.read(str(WEB / obj["audio"]), dtype="float32")
        x = x if x.ndim == 1 else x.mean(axis=1)
        seconds = len(x) / sr
        words = len(obj["speech"].split())
        assert sr == 24000
        assert 0.25 * words <= seconds <= 0.7 * words + 3, (mid, key, seconds, words)   # roughly 2.5-4 words a second
        rms = float(np.sqrt(np.mean(x ** 2)))
        assert 0.04 <= rms <= 0.15 and float(np.abs(x).max()) <= 0.96, (mid, key, rms)
        win = int(sr * 0.05)
        quiet = np.sqrt(np.mean(x[: len(x) // win * win].reshape(-1, win) ** 2, axis=1)) < 0.004
        runs = np.split(quiet, np.where(np.diff(quiet))[0] + 1)
        assert max((len(r) for r in runs if r.size and r[0]), default=0) * 0.05 <= 1.2, (mid, key)   # no dead air


def test_audio_folder_has_only_current_clips_and_stays_small():
    linked = {WEB / obj["audio"] for _, _, obj in clips()}
    on_disk = set((WEB / "audio").rglob("*.ogg"))
    assert on_disk == linked, on_disk ^ linked
    assert sum(p.stat().st_size for p in on_disk) < 25_000_000


def test_player_falls_back_to_the_browser_voice_when_a_clip_cannot_play():
    js = (WEB / "js" / "speech.js").read_text(encoding="utf8")
    for needle in ("playRecording", "RECORDED", "Commentator (recorded)", "onerror", "speakWithBrowser", "currentAudio.pause()"):
        assert needle in js, needle
    assert "exp.audio" in (WEB / "js" / "moments.js").read_text(encoding="utf8")
    assert "story.audio" in (WEB / "js" / "summary.js").read_text(encoding="utf8")
