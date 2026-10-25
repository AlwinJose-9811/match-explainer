"""Spoken commentary: number words, script content for every moment, and the browser-side sentence/voice logic."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from pipeline.config import ROOT, load_config
from pipeline.speech_script import ordinal, per_ten, score_words, speak_years, words, year_words

IDS = [m["match_id"] for m in load_config()["matches"]]
node = shutil.which("node")


@pytest.mark.parametrize("n,w,o", [(0, "zero", "zeroth"), (5, "five", "fifth"), (12, "twelve", "twelfth"), (20, "twenty", "twentieth"),
                                   (36, "thirty-six", "thirty-sixth"), (81, "eighty-one", "eighty-first"), (100, "one hundred", "one hundredth"),
                                   (108, "one hundred and eight", "one hundred and eighth"), (123, "one hundred and twenty-three", "one hundred and twenty-third")])
def test_number_words_and_ordinals(n, w, o):
    assert words(n) == w and ordinal(n) == o


def test_years_scores_and_chances_are_spoken_naturally():
    assert year_words(2022) == "twenty twenty-two" and year_words(2005) == "two thousand and five" and year_words(2000) == "two thousand"
    assert speak_years("FIFA World Cup 2022") == "FIFA World Cup twenty twenty-two"
    assert speak_years("La Liga 2015/2016") == "La Liga twenty fifteen to twenty sixteen"
    assert speak_years("Round of 16") == "Round of sixteen"
    assert score_words(3, 0) == "three nil" and score_words(2, 2) == "two two"
    assert per_ten(0.4) == "about four in ten" and per_ten(0.02) == "fewer than one in ten"


@pytest.fixture(scope="module")
def bundles():
    out = []
    for mid in IDS:
        d = ROOT / "data" / "processed" / str(mid)
        out.append((json.loads((d / "summary.json").read_text(encoding="utf8")), json.loads((d / "moments.json").read_text(encoding="utf8"))))
    return out


def test_every_moment_and_story_has_a_clean_spoken_script(bundles):
    n = 0
    for summary, mom in bundles:
        sp = summary["story"]["speech"]
        assert sp and not any(c.isdigit() for c in sp) and len(sp.split()) <= 150
        for m in mom["moments"]:
            s = m["explanation"]["speech"]
            n += 1
            assert s.strip() and not any(c.isdigit() for c in s) and "xG" not in s and ":" not in s, s
            assert 15 <= len(s.split()) <= 110 and s.rstrip()[-1] in ".!", s
    assert n >= 25


def test_goals_sound_excited_and_penalties_build_tension(bundles):
    for _, mom in bundles:
        for m in mom["moments"]:
            s = m["explanation"]["speech"]
            if m["is_goal"]:
                assert "!" in s
            if m["is_penalty"]:
                assert "steps up" in s and ("..." in s or "but" in s)
            if m["type"] == "red_card":
                assert "red card" in s and "sent off" in s


def test_spoken_minute_matches_the_clock_but_is_one_based(bundles):
    summary, mom = bundles[0]            # the final
    di_maria = next(m for m in mom["moments"] if m["clock"] == "35:22")
    assert "thirty-sixth minute" in di_maria["explanation"]["speech"]
    rebound = next(m for m in mom["moments"] if m["clock"] == "107:58")
    assert "one hundred and eighth minute" in rebound["explanation"]["speech"] and "rebound" in rebound["explanation"]["speech"]


SPEECH_NODE = r"""
import { sentences, voiceScore } from 'file:///%s/web/js/speech.js';
const s = sentences('Argentina strike! Messi steps up... and scores! Most penalties go in. Is that right?');
const v = (name, lang) => voiceScore({name, lang});
console.log(JSON.stringify({s, order: [v('Microsoft Aria Online (Natural) - English (United States)', 'en-US'), v('Microsoft Sonia Online (Natural) - English (United Kingdom)', 'en-GB'),
  v('Google UK English Female', 'en-GB'), v('Microsoft Zira - English (United States)', 'en-US'), v('Microsoft Hortense - French', 'fr-FR')]}));
"""


@pytest.mark.skipif(node is None, reason="node not installed")
def test_sentence_splitting_prosody_kinds_and_voice_ranking():
    out = subprocess.run([node, "--input-type=module", "-e", SPEECH_NODE % ROOT.as_posix()], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert [(x["text"], x["kind"]) for x in r["s"]] == [("Argentina strike!", "excited"), ("Messi steps up,", "build"), ("and scores!", "excited"),
                                                          ("Most penalties go in.", "plain"), ("Is that right?", "plain")]
    natural_us, natural_gb, google, zira, french = r["order"]
    assert natural_gb > natural_us > google > zira > french and french < -500   # natural voices first, robotic ones last, non-English excluded


def test_speech_code_has_voice_picker_and_cancels_cleanly():
    js = (ROOT / "web" / "js" / "speech.js").read_text(encoding="utf8")
    for needle in ("voiceschanged", "Choose the voice", "PROSODY", "speechSynthesis.cancel", "token"):
        assert needle in js, needle
    assert "localStorage" not in js
