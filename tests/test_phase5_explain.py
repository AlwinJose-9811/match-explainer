"""Tests for template explanations, the story and the text validator (TC-29, TC-31, TC-32 equivalents)."""
from __future__ import annotations

import copy
import json
import re

import pytest

from pipeline.config import load_config, processed_dir, raw_dir
from pipeline.explain import LABEL, display_names, explain_moment, per_ten, text_facts
from pipeline.load import load_match
from pipeline.validate import validate_json, validate_text

CFG = load_config()
RAW = raw_dir(CFG)
needs_data = pytest.mark.skipif(not (RAW / "competitions.json").exists(), reason="raw data not fetched")
IDS = [m["match_id"] for m in CFG["matches"]]
PROCESSED = processed_dir(CFG["default_match_id"]).parent
needs_bundle = pytest.mark.skipif(not (PROCESSED / "index.json").exists(), reason="processed bundle missing")

FACTS = {"clock": "35:22", "player": "Ángel Di María", "team": "Argentina", "xg": "0.30", "per_ten": "about 3 in 10"}


def test_validator_accepts_grounded_text():
    text = "At 35:22, Ángel Di María scored for Argentina. The chance was worth 0.30 xG, meaning about 3 in 10 shots are goals."
    assert validate_text(text, FACTS) == []


def test_validator_rejects_injected_fake_name():  # TC-32
    bad = "At 35:22, Cristiano Ronaldo scored for Argentina."
    assert any("Ronaldo" in p for p in validate_text(bad, FACTS))


def test_validator_rejects_invented_numbers_and_banned_phrases():
    assert any("number '7'" in p for p in validate_text("At 35:22, Ángel Di María scored after 7 passes.", FACTS))
    assert any("number '36'" in p for p in validate_text("At 36:10, Ángel Di María scored.", FACTS))
    assert any("banned" in p for p in validate_text("Ángel Di María deliberately scored for Argentina.", FACTS))
    assert any("too long" in p for p in validate_text("word " * 200 + ".", FACTS, max_words=150))


def test_per_ten_wording():
    assert per_ten(0.78) == "about 8 in 10" and per_ten(0.30) == "about 3 in 10" and per_ten(0.03) == "fewer than 1 in 10"


@needs_bundle
@pytest.mark.parametrize("mid", IDS)
def test_every_moment_has_text_and_why_and_label(mid):  # TC-29, TC-32 label
    d = processed_dir(mid)
    moments = json.loads((d / "moments.json").read_text(encoding="utf8"))
    summary = json.loads((d / "summary.json").read_text(encoding="utf8"))
    validate_json(moments, "moments")
    validate_json(summary, "summary")
    for m in moments["moments"]:
        e = m["explanation"]
        assert e and e["text"].strip() and e["why"].strip() and e["source"] == "template" and e["label"] == LABEL
        assert 1 <= e["text"].count(".") <= 6
    assert summary["story"]["label"] == LABEL and len(summary["story"]["text"].split()) <= 150


@needs_bundle
def test_final_goal_text_is_correct_and_plain():
    d = processed_dir(CFG["default_match_id"])
    moments = {m["clock"]: m for m in json.loads((d / "moments.json").read_text(encoding="utf8"))["moments"]}
    di_maria = moments["35:22"]["explanation"]
    assert "At 35:22" in di_maria["text"] and "fast counter-attack" in di_maria["text"]
    assert re.search(r"worth \d\.\d\d xG \(expected goals\), meaning about \d in 10", di_maria["text"])
    assert "Kolo Muani" in " ".join(m["explanation"]["text"] for m in moments.values())  # truncated nickname not used
    assert "counter" in di_maria["why"]
    assert "rebound" in moments["107:58"]["explanation"]["text"]
    pen = moments["22:24"]["explanation"]["text"]
    assert "scored a penalty" in pen and "about 8 in 10" in pen
    story = json.loads((d / "summary.json").read_text(encoding="utf8"))["story"]["text"]
    assert "drew 3-3" in story and "4-2 on penalties" in story and "22:24" in story


@needs_bundle
@needs_data
def test_tampered_explanation_fails_revalidation_and_output_is_deterministic():  # TC-32 spirit
    d = processed_dir(CFG["default_match_id"])
    summary = json.loads((d / "summary.json").read_text(encoding="utf8"))
    m = copy.deepcopy(json.loads((d / "moments.json").read_text(encoding="utf8"))["moments"][1])
    names = display_names(load_match(RAW, CFG["default_match_id"]).lineups)
    facts = text_facts(m, summary, names)
    assert validate_text(m["explanation"]["text"], facts, max_sentences=3, max_words=80) == []
    assert validate_text(m["explanation"]["text"].replace("Argentina", "Brazil"), facts)
    assert explain_moment(m, summary, names) == m["explanation"] == explain_moment(m, summary, names)


def test_display_names_use_nickname_with_explicit_overrides():
    lineups = [{"lineup": [
        {"player_name": "Randal Kolo Muani", "player_nickname": "Randal Kolo"},
        {"player_name": "Kylian Mbappé Lottin", "player_nickname": "Kylian Mbappé"},
        {"player_name": "Marcus Thuram", "player_nickname": None}]}]
    n = display_names(lineups, CFG["name_overrides"])
    assert n["Randal Kolo Muani"] == "Randal Kolo Muani" and n["Kylian Mbappé Lottin"] == "Kylian Mbappé"
    assert n["Marcus Thuram"] == "Marcus Thuram"
    assert display_names(lineups)["Randal Kolo Muani"] == "Randal Kolo"
