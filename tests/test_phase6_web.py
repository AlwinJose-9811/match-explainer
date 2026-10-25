"""Static checks on the web app (TC-09, TC-10, TC-35 glossary size, TC-36 footer, offline/no-third-party)."""
from __future__ import annotations

import json
import re

import pytest

from pipeline.config import ROOT

WEB = ROOT / "web"
JS = {p.name: p.read_text(encoding="utf8") for p in (WEB / "js").glob("*.js")}


def glossary_keys() -> set[str]:
    body = JS["glossary.js"].split("export const TERMS = {", 1)[1].split("\n};", 1)[0]
    return set(re.findall(r"^\s{2}(\w+):\s*\[", body, flags=re.M))


def test_glossary_has_at_least_15_terms_with_help_text():  # TC-35 (size part), FR-G1
    keys = glossary_keys()
    assert len(keys) >= 15
    entries = re.findall(r"^\s{2}\w+:\s*\['([^']+)',\s*'((?:[^'\\]|\\.)+)'\]", JS["glossary.js"], flags=re.M)
    assert len(entries) == len(keys) and all(name and len(help_) > 20 for name, help_ in entries)


def test_every_stat_label_has_a_glossary_tooltip():  # TC-09
    rows = re.findall(r"key: '(\w+)', label: '([^']+)'", JS["summary.js"])
    assert len(rows) >= 8
    missing = [k for k, _ in rows if k not in glossary_keys()]
    assert not missing, missing
    assert "term(row.key, row.label)" in JS["summary.js"]


def test_pitch_svg_uses_120_by_80_viewbox():  # TC-10
    assert "viewBox: '0 0 120 80'" in JS["pitch.js"]


def test_footer_attribution_and_automated_label_present():  # TC-36
    html = (WEB / "index.html").read_text(encoding="utf8")
    assert "github.com/statsbomb/open-data" in html and "Data provided by" in html and "StatsBomb" in html
    assert "automated analysis" in html.lower()
    assert 'id="view"' in html and '<footer class="foot">' in html


def test_no_third_party_requests_or_cookies():  # NFR-2, NFR-8
    src = "\n".join([(WEB / "index.html").read_text(encoding="utf8"), (WEB / "css" / "style.css").read_text(encoding="utf8"), *JS.values()])
    urls = {u for u in re.findall(r"https?://[^\s'\"<>)]+", src) if not u.startswith("http://localhost")}
    assert urls <= {"https://github.com/statsbomb/open-data", "http://www.w3.org/2000/svg"}, urls
    assert "document.cookie" not in src and "@import" not in src and "<script src=\"http" not in src
    assert "localStorage" not in src and "XMLHttpRequest" not in src


def test_accessibility_basics_in_shell():  # NFR-4
    html = (WEB / "index.html").read_text(encoding="utf8")
    assert 'lang="en"' in html and "viewport" in html and 'class="skip"' in html
    css = (WEB / "css" / "style.css").read_text(encoding="utf8")
    assert ":focus-visible" in css and "prefers-reduced-motion" in css
    assert "aria-live" in JS["pitch.js"] and "aria-label" in JS["pitch.js"] and "aria-label" in JS["shots.js"]


def test_web_data_is_in_sync_with_processed_bundle():
    idx = json.loads((ROOT / "data" / "processed" / "index.json").read_text(encoding="utf8"))
    assert (WEB / "data" / "index.json").read_text(encoding="utf8") == (ROOT / "data" / "processed" / "index.json").read_text(encoding="utf8")
    for m in idx["matches"]:
        for name in ("summary", "positions", "moments", "shots"):
            a = WEB / "data" / str(m["match_id"]) / f"{name}.json"
            b = ROOT / "data" / "processed" / str(m["match_id"]) / f"{name}.json"
            assert a.exists() and a.read_text(encoding="utf8") == b.read_text(encoding="utf8"), a
    assert (WEB / "data" / "model" / "xg_metrics.json").exists()
