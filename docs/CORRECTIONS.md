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

## Phase 6-7 decisions (web app)
- Time-window length is fixed at build time (`window_minutes`, 15) with 5-minute steps; the slider selects among the
  precomputed windows (FR-P4 "configurable" is satisfied at build time, not in the browser).
- Replays always show the attacking team attacking to the right; the pitch and shot pages mirror the away team.
- Penalty goals and missed penalties render as a simple penalty card; red cards as a text card.
- The "Listen" button uses the browser Web Speech API (no network); it hides itself when unsupported.
- With reduced motion enabled the replay becomes a step-by-step view (previous/next buttons and scrubber).
- `web/data/` is a real copy of `data/processed/` plus `model/` (made by `pipeline.export.sync_web`).
- StatsBomb asks for their logo as well as a text credit: the logo is NOT included yet (add it from their Media Pack
  before making the repository public).

## Phase 4 decisions (xG model)
- Logistic regression only (no gradient boosting). C chosen by 5-fold CV grouped by match on the training seasons.
- Train: 877 matches (Premier League 2015/16, La Liga 2016/17-2020/21, FA WSL 2018/19-2020/21), 22,306 shots after
  exclusions (220 penalties out). Test: UEFA Euro 2020 (51 matches), 1,234 shots; shootout shots excluded.
- Penalty xG = training conversion rate 0.786 (173 of 220).
- The freeze frame inside shot events marks the goalkeeper by `position.name == "Goalkeeper"`, not by a
  `keeper` flag (360 files use the flag). The first training run missed this; fixed and retrained.
- Every shot in the data has a freeze frame, so `has_ff` is constant and the has/without-freeze-frame split in the
  model card shows one group.
- Model xG sums per team are written into summary.json and moments.json; shots.json lists regular-time shots.

## Phase 3 decisions (moments)
- Moment types: `goal` (incl. penalty goals, flagged `is_penalty`), `own_goal`, `penalty` (missed/saved), `red_card`,
  `shot` (xG >= threshold). Goals are never dropped by the cap or the 60 s spacing rule.
- Clock shown as StatsBomb minute:second (e.g. 80:59); ranking uses StatsBomb xG until the model's xG is attached (P4).
- Build-up: same team, possession and period, completed passes and carries only, last 12 within 20 s.
  If an earlier shot of the same possession exists the sequence starts after it and `facts.rebound` is true
  (Messi 107:58 in the final has no key pass and a one-step sequence for this reason).
- 360 coordinates share the event frame (checked: the actor's 360 location equals the event location).
- `offside_line_x` = x of the deepest visible defender (needs 2 visible defenders); `defensive_line_height` = 120 - that;
  `gap_to_line` = key-pass end x minus the line (positive = the pass reached behind the line).
  The line comes from visible players only; the UI says so. A snapshot at the shot falls back to the event's own
  shot freeze frame when the 360 file has no row for it (e.g. Alvarez 38:26 v Croatia).
- Matches other than the final have fewer than 6 replays (Argentina v Croatia has 2 non-penalty moments).
- Average positions come from on-ball events only (biased towards where players touch the ball); state it in the UI.
- StatsBomb asks for the data source credit and their logo when publishing: read LICENSE.pdf before going public.
- xG split: train on Ligue 1 2021/22 + Bundesliga 2023/24, test on UEFA Euro 2020; WC 2022 is never trained on.
