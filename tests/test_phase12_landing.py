"""Landing page: structure, motion safety, colour contrast (including worst cases over the art) and the pure drawing helpers."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from pipeline.config import ROOT
from tests.test_phase8_quality import TOKENS, contrast

WEB = ROOT / "web"
LP = (WEB / "js" / "landing.js").read_text(encoding="utf8") + (WEB / "js" / "flow.js").read_text(encoding="utf8")   # the backdrop lives in flow.js
CSS = (WEB / "css" / "style.css").read_text(encoding="utf8")
APP = (WEB / "js" / "app.js").read_text(encoding="utf8")
node = shutil.which("node")


def over(fg_hex: str, alpha: float, behind_hex: str) -> str:
    """Hex colour of a dark translucent layer (fg at `alpha`) over a background colour."""
    f = [int(fg_hex[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(behind_hex[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(alpha * x + (1 - alpha) * y):02X}" for x, y in zip(f, b))


def test_landing_is_the_default_page_and_links_into_the_app():
    assert "showLanding" in APP and "is-landing" in APP
    assert re.search(r"page: PAGES\.some\(p => p\.id === page\) \? page : 'home'", APP)    # no hash = landing first
    assert 'href="#home"' in (WEB / "index.html").read_text(encoding="utf8")
    for needle in ("#summary?m=${index.default}", "#moments?m=${index.default}", "lp-matches", "Data provided by", "automated analysis"):
        assert needle in LP, needle


def test_background_is_decorative_stops_when_hidden_and_respects_reduced_motion():
    for needle in ("'aria-hidden': 'true'", "visibilitychange", "canvas.isConnected", "prefersReduced", "lp-still", "ResizeObserver", "cancelAnimationFrame"):
        assert needle in LP, needle
    assert "prefers-reduced-motion" in CSS and ".lp-still" in CSS
    assert "<img" not in LP and "url(http" not in CSS and "Image(" not in LP        # nothing loaded: drawn entirely in code


def test_headline_sits_on_a_dark_scrim_with_enough_contrast():
    lawn, cream, lime = TOKENS["lawn"], TOKENS["cream"], TOKENS["lime"]
    assert contrast(cream, lawn) >= 7 and contrast(lime, lawn) >= 7 and contrast(TOKENS["cream-dim"], lawn) >= 4.5   # header and nav text
    assert contrast(lawn, cream) >= 7 and contrast(lawn, lime) >= 7                                                    # button text on cream / lime hover
    assert "rgba(6, 30, 16, .92)" in CSS                                                                              # the scrim behind the copy
    assert contrast(cream, over("#061E10", 0.92, cream)) >= 7                  # headline column, even over the lightest stripe highlight


def test_pills_and_caption_stay_readable_over_the_brightest_part_of_the_art():
    worst = over("#061E10", 0.78, TOKENS["cream"])         # a cream highlight directly under a pill
    assert contrast(TOKENS["cream"], worst) >= 4.5, (worst, contrast(TOKENS["cream"], worst))
    for cls in (".lp-chip", ".lp-feats li", ".lp-caption"):
        block = re.search(re.escape(cls) + r" \{[^}]*\}", CSS).group(0)
        assert "rgba(6, 30, 16, .78)" in block, cls


@pytest.mark.skipif(node is None, reason="node not installed")
def test_drawing_helpers_are_well_behaved():
    code = r"""
import { catmullRom, horizon, warp } from 'file:///%s/web/js/landing.js';
const pts = [[0, 0], [10, 5], [20, -5], [30, 0]];
const d = catmullRom(pts);
const nums = d.match(/-?[0-9.]+/g).map(Number);
const w = 1000, h = 600; const far = warp(10, 10, w, h, 0), near = warp(620, 408, w, h, 0);
const hs = [0, 250, 500, 750, 1000].map(x => horizon(x, h, 1));
console.log(JSON.stringify({d, segs: (d.match(/C/g) || []).length, endsAt: nums.slice(-2), empty: catmullRom([[1, 1]]),
  horizonRange: [Math.min(...hs), Math.max(...hs)], farShift: Math.hypot(far[0] - 10, far[1] - 10), finite: [...far, ...near].every(Number.isFinite)}));
""" % ROOT.as_posix()
    out = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["segs"] == 3 and r["endsAt"] == [30, 0] and r["empty"] == "" and r["finite"]
    assert 0.15 * 600 < r["horizonRange"][0] and r["horizonRange"][1] < 0.40 * 600       # the horizon stays in the upper part
    assert r["farShift"] < 0.12 * 600                                                    # far from the vortex only gentle waves move a point


def test_inner_pages_use_dark_glass_panels_with_readable_text():
    assert ".card {" in CSS and "backdrop-filter" in CSS and ".top {" in CSS
    assert contrast(TOKENS["text"], TOKENS["panel"]) >= 7 and contrast(TOKENS["text"], TOKENS["bg"]) >= 7
    glass = over(TOKENS["panel"], 0.78, TOKENS["cream"])         # the glass panel over the brightest highlight of the backdrop
    assert contrast(TOKENS["text"], glass) >= 4.5 and contrast(TOKENS["muted"], glass) >= 4.5, glass
