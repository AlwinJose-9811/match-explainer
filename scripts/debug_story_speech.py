"""Debug helper: print the spoken story for a match and any digits in it."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.config import load_config, raw_dir  # noqa: E402
from pipeline.explain import display_names  # noqa: E402
from pipeline.load import load_match  # noqa: E402
from pipeline.metrics import build_summary  # noqa: E402
from pipeline.moments import build_moments  # noqa: E402
from pipeline.normalize import events_frame  # noqa: E402
from pipeline.speech_script import spoken_story  # noqa: E402

cfg = load_config()
d = load_match(raw_dir(cfg), int(sys.argv[1]))
df = events_frame(d.events)
s = build_summary(d, df)
mom = build_moments(df, d.three_sixty, d.record["home_team"]["home_team_name"], cfg, d.lineups)
text = spoken_story(s, mom, display_names(d.lineups, cfg.get("name_overrides")))
print(text)
print("digits at:", [(i, text[max(0, i - 25):i + 25]) for i, c in enumerate(text) if c.isdigit()])
