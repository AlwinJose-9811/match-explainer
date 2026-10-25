"""Release-quality checks: colour contrast (NFR-4), no secrets (NFR-8/TC-42), docs/attribution, determinism (NFR-7)."""
from __future__ import annotations

import json
import re

import pytest

from pipeline.config import ROOT, load_config

CSS = (ROOT / "web" / "css" / "style.css").read_text(encoding="utf8")
TOKENS = dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", CSS.split("}", 1)[0]))


def lum(hex_: str) -> float:
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def colour(x: str) -> str:
    return x if x.startswith("#") else TOKENS[x]


PAIRS = [("text", "card"), ("text", "bg"), ("muted", "card"), ("muted", "bg"), ("navy", "card"), ("navy", "#EEF3FA"),
         ("navy", "#E3EAF6"), ("#FFFFFF", "navy"), ("#FFFFFF", "home"), ("#FFFFFF", "away"), ("home", "card"), ("away", "card")]


@pytest.mark.parametrize("fg,bg", PAIRS)
def test_text_contrast_is_at_least_4_5_to_1(fg, bg):  # NFR-4
    assert contrast(colour(fg), colour(bg)) >= 4.5, (fg, bg, round(contrast(colour(fg), colour(bg)), 2))


def test_team_colours_in_css_match_the_data():
    summary = json.loads((ROOT / "data" / "processed" / str(load_config()["default_match_id"]) / "summary.json").read_text(encoding="utf8"))
    assert summary["teams"]["home"]["color"].lower() == TOKENS["home"].lower()
    assert summary["teams"]["away"]["color"].lower() == TOKENS["away"].lower()


def test_repository_has_no_secrets():  # TC-42
    pattern = re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]\s*['\"][^'\"]{12,}|BEGIN (RSA|PRIVATE) KEY)", re.I)
    skip = {".git", "__pycache__", ".pytest_cache", "interim"}
    hits = []
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.parts) & skip) and p.suffix in {".py", ".js", ".json", ".md", ".html", ".css", ".txt", ".toml"}:
            if pattern.search(p.read_text(encoding="utf8", errors="ignore")):
                hits.append(str(p.relative_to(ROOT)))
    assert not hits, hits
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf8")


def test_readme_documents_setup_attribution_and_limits():  # T-32
    readme = (ROOT / "README.md").read_text(encoding="utf8")
    for needle in ("StatsBomb", "python tasks.py", "Limits", "Automated analysis", "xG"):
        assert needle in readme, needle
    steps = re.findall(r"^(?:python|git|cd) .*$", readme.split("## Quick start", 1)[1].split("##", 1)[0], flags=re.M)
    assert 1 <= len(steps) <= 10


def test_processed_outputs_are_deterministic_given_the_same_inputs():  # NFR-7 (in-process)
    from pipeline.config import raw_dir
    from pipeline.load import load_match
    from pipeline.metrics import build_summary
    from pipeline.moments import build_moments
    from pipeline.normalize import events_frame
    from pipeline.positions import build_positions

    cfg = load_config()
    if not (raw_dir(cfg) / "competitions.json").exists():
        pytest.skip("raw data not fetched")
    d = load_match(raw_dir(cfg), cfg["default_match_id"])
    df = events_frame(d.events)
    home, away = d.record["home_team"]["home_team_name"], d.record["away_team"]["away_team_name"]
    runs = [json.dumps([build_summary(d, df), build_positions(df, d.lineups, home, away, cfg), build_moments(df, d.three_sixty, home, cfg)],
                       sort_keys=True) for _ in range(2)]
    assert runs[0] == runs[1]
