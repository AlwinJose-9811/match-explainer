# Corrections and scope changes to MX-01 to MX-04

Baseline: the four .docx files in this folder. This file overrides them where they differ.
Verified against statsbomb/open-data on 2026-10-25.

## Scope (8-hour build)
- 5 pre-processed matches with a match picker (FR-D5, FR-S2 now required):
  3869685 Final Argentina-France (default), 3869321 Netherlands-Argentina (QF), 3869354 England-France (QF),
  3869519 Argentina-Croatia (SF), 3869486 Morocco-Portugal (QF). All FIFA World Cup 2022 (43/106), all with 360 data.
- xG: logistic regression only (no gradient boosting). Explanations: templates only (no LLM, no API key).
- Cut: pass network, momentum graph, highlight links, formation label, tactical summaries, dark mode.
- Added: "Listen" button reading the explanation aloud with the browser Web Speech API (no network).
- Shot map (FR-X6) is the first item cut if time runs short.

## Verified data facts
- 43/106 = FIFA World Cup 2022, 360 available. Match 3869685 = Argentina 3-3 France, 2022-12-18, Final.
- Periods 1-5, period 5 = shootout (Argentina 4-2). Event minutes run to 125 because of the shootout:
  take the slider maximum from periods 1-4 only.
- StatsBomb `minute` is 0-based. Final goals (period, min:sec): 22:24 pen, 35:22, 79:24 pen, 80:59, 107:58, 117:05 pen.
  The "about 23/36/108/80/81/118" oracle in MX-04 is off by one; display as a clock time instead.
- Three of six goals are penalties (no freeze frame, xG 0.78): show as simple penalty cards, no replay sequence.
- The 80:59 Mbappe goal has xG 0.10 (below the 0.15 threshold): goals are always kept.
- No own goals in the final. Only yellow cards (8), so red-card detection needs a test on another match.
- 360 file: 3683 rows, every event_uuid matches an event id. Open-play shots carry shot.freeze_frame.

## Design fixes
- "Shallow clone" does not reduce size; use `scripts/fetch_data.py` (sparse, blobless, per-file).
- No `make` on Windows: use `python tasks.py <task>`. Raw data and venv live outside OneDrive (C:/mx-data).
- Demo the 35:22 Di Maria goal and the 80:59 Mbappe volley, not a penalty.
- Player names in StatsBomb are full legal names; templates need a short-name map (lineup `player_nickname`).
- Block-label thresholds come from the data distribution, not tuned to make TC-13 pass.
  Measured on the 5 picker matches (223 windows, both teams): defensive-line terciles are 48.0 and 53.5, so
  `block_thresholds` is [48, 54] (not [35, 48], which would label nearly every window "high line").
  The labels are therefore relative to these matches; the UI says so.
- A role group needs at least 2 players in a window before its line is shown (a single defender gave nonsense).
- The k-means cross-check agrees with the role grouping for only 60-80% of players (spec asked for 80%+);
  it is a diagnostic in positions.json and not shown in the UI.
- Windows: named (full, first half, second half, extra time) plus 15-minute windows every 5 minutes.
- Average positions come from on-ball events only (biased towards where players touch the ball); state it in the UI.
- StatsBomb asks for the data source credit and their logo when publishing: read LICENSE.pdf before going public.
- xG split: train on Ligue 1 2021/22 + Bundesliga 2023/24, test on UEFA Euro 2020; WC 2022 is never trained on.
