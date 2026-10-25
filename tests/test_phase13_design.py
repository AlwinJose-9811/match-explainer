"""The stadium-night redesign: the stage and pitch realism, glass panels, replay extras, players panel, fixtures strip."""
from __future__ import annotations

import re

import pytest

from pipeline.config import ROOT
from tests.test_phase8_quality import TOKENS, contrast
from tests.test_phase12_landing import over

WEB = ROOT / "web"
JS = {p.stem: p.read_text(encoding="utf8") for p in (WEB / "js").glob("*.js")}
CSS = (WEB / "css" / "style.css").read_text(encoding="utf8")


def test_backdrop_is_not_painted_over_by_the_body_background():
    """Regression: an opaque body background hid the fixed liquid-pitch canvas (negative z-index) completely."""
    assert re.search(r"\nbody \{[^}]*background:\s*transparent", CSS)
    assert re.search(r"#backdrop \{[^}]*position: fixed[^}]*z-index: -10", CSS)
    assert "mountBackdrop" in JS["app"] and "setAnimated" in JS["app"]
    assert "setAnimated(false)" in JS["app"]                      # inner pages keep the backdrop still (saves battery)


def test_pitch_is_built_for_realism():
    p = JS["pitch"]
    for needle in ("stripes", "class: 'glow'", "net(0, -2.8)", "net(120, 122.8)", "'M1 0A1 1 0 0 1 0 1'", "ellipse", "viewBox: '0 0 120 80'"):
        assert needle in p, needle
    assert "length: 12" in p                                       # twelve mowing stripes of ten units each: they line up with the pitch
    for needle in (".turf {", ".crowd {", ".ads {", "radial-gradient", "feTurbulence", ".stage[data-tilt=\"on\"] .turf", "perspective("):
        assert needle in CSS, needle


def test_stage_has_a_tilt_toggle_and_an_overlay_for_cards():
    s = JS["stage"]
    for needle in ("export const camera", "data-tilt", "aria-pressed", "overlay", "hud", "tiltBtn"):
        assert needle in s, needle
    for page in ("pitch", "shots", "replay", "moments"):
        assert "stage(" in JS[page], page                          # every pitch lives in the stage
    assert "pitch-wrap" not in "".join(JS.values())


def test_replay_has_glass_controls_distance_lines_and_a_floating_card():
    r = JS["replay"]
    for needle in ("drawClosest", "yd`", "paintCallout", "'Closest defender'", "class: 'transport'", "class: 'round'", "class: 'switch'",
                   "'Distances'", "get('at')", "Players in the move", "The move"):
        assert needle in r, needle
    for needle in (".transport {", ".switch {", ".callout {", ".callout.flip", ".seg-btn", ".squad", "ol.steps li.on"):
        assert needle in CSS, needle


def test_pitch_page_has_a_players_panel_that_highlights_on_hover_and_focus():
    p = JS["pitch"]
    for needle in ("Players in this window", "class: 'prow'", "'mouseenter', 'focus'", "'mouseleave', 'blur'", "highlight()", "ROLE_ORDER"):
        assert needle in p, needle
    for needle in (".prow", ".plist", ".split", ".tab["):
        assert needle in CSS, needle


def test_summary_has_a_fixtures_strip_and_crest_scoreboard():
    s = JS["summary"]
    for needle in ("function fixtures", "class: 'fixtures'", "crest(", "class: 'board3'", "aria-current"):
        assert needle in s, needle
    for needle in (".fixtures", ".fx.on", ".crest.big", ".board3"):
        assert needle in CSS, needle


def test_phones_get_a_swipeable_moment_strip_and_no_floating_card():
    assert "@media (max-width: 860px) {\n  .moments { grid-template-columns: 1fr; }\n  .moments .mlist { display: flex; overflow-x: auto" in CSS
    assert "@media (max-width: 600px) { .callout { display: none; } }" in CSS


@pytest.mark.parametrize("name,alpha,base", [("callout", 0.74, "#081C12"), ("pill", 0.72, "#06160E"), ("panel", 0.78, "#0E2619")])
def test_floating_glass_stays_readable_over_the_brightest_turf_and_backdrop(name, alpha, base):
    bright = "#7FC48A"                                           # a floodlit patch of turf is the lightest thing under a card
    glass = over(base, alpha, bright)
    assert contrast(TOKENS["text"], glass) >= 4.5, (name, glass)
    assert contrast(TOKENS["muted"], glass) >= 4.5, (name, glass)


def test_calibration_plot_is_drawn_in_the_dark_theme():
    pil = pytest.importorskip("PIL.Image")
    im = pil.open(WEB / "data" / "model" / "xg_calibration.png").convert("RGB")
    r, g, b = im.getpixel((2, 2))
    assert (r, g, b) == (14, 38, 25)                              # the panel colour, not a white rectangle on a dark page
