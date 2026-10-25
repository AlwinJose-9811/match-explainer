# Acceptance checklist against MX-02

Status as of the final build. **Done** = implemented and checked by a test or by inspection in the browser.
**Cut** = left out on purpose for the 8-hour scope (see CORRECTIONS.md). **Partial** = works with a stated limit.

| Req | Status | Evidence / note |
|---|---|---|
| FR-D1 read local files, no network | Done | Pipeline reads only `raw_dir`; all tests run offline |
| FR-D2 clear error naming match and file | Done | `test_missing_events_file_names_match_and_item` |
| FR-D3 120x80 frame, mirror helper | Done | mirror involution test; goals start at x >= 80 on all ten matches |
| FR-D4 period 5 excluded, shootout reported separately | Done | possession/positions/xG unchanged; final shows 4-2 separately |
| FR-D5 `--match-id` for any match | Done | all ten picker matches built this way |
| FR-S1 default match loads without a click | Done | final loads on page open |
| FR-S2 match picker | Done | dropdown reloads every page (browser-checked on 30 page/match combinations) |
| FR-M1 teams, score, extra time/penalties note | Done | summary page; scores equal the matches file (tested for all ten) |
| FR-M2 statistics equal independent recount | Done | `test_stats_match_independent_recount` |
| FR-M3 tooltip on every stat label (>= 8 terms) | Done | 12 labelled terms, test checks every label has text |
| FR-M4 possession method shown | Done | note under the possession bar |
| FR-M5 match story, labelled | Done | <= 150 words, validated, "Automated analysis" |
| FR-P1 SVG pitch 120x80 | Done | viewBox test |
| FR-P2 average positions per window | Done | window change changes positions (test) |
| FR-P3 three lines per team with numbers | Done | def < mid < att in the full match (test) |
| FR-P4 minute slider through extra time | Partial | slider steps through precomputed 15-minute windows to the last minute (125 for the final); window length is set at build time |
| FR-P5 shape label and metrics | Done | labels differ across windows and matches (test); thresholds from data |
| FR-P6 formation estimate | Cut | |
| FR-K1 goals, xG shots, penalties, red cards | Done | exactly 6 goals in the final; red card found in Morocco v Portugal |
| FR-K2 cap, order, spacing | Done | unit and per-match tests |
| FR-K3 moment schema | Done | every output validated against its JSON schema |
| FR-K4 build-up from same possession | Done | possession, team, period and shot-last test on all matches |
| FR-K5 goals-only filter | Done | button on the Key moments page |
| FR-A1 ball, arrows, dashed carries, shot arrow | Done | verified in the browser (arrows, ball, GOAL!) |
| FR-A2 play, pause, restart, 0.5x/1x, scrubber | Done | keyboard-operable buttons and a range input |
| FR-A3 step labels, key pass and shooter highlighted | Done | caption, numbered steps, KEY PASS label, shooter ring |
| FR-A4 360 snapshot at key pass and shot | Done | all visible players of both teams are shown during the replay, with "Freeze at the key pass / shot"; "visible players only" note |
| FR-A5 last-defender line and gap | Done | live line = x of the deepest visible defender (test); gap sentence at the key pass |
| Owner request: opposition positions and off-the-ball movement, ball path separate | Done, with limits | `tracking.py` reconstructs runs from 360 snapshots (both teams, mirrored into one frame); ball path is bold, white-cased and drawn on top; toggles for players, runs and the last-defender line. Accuracy vs the event data: median 0.6 yd, 90th percentile 1.9 yd, max 13 yd over 369 actions in the ten matches; implied speeds <= 16 yd/s; defending keepers land at the right end (mirroring test). It is an estimate (visible players only, up to ~6 s between snapshots), not tracking. 2 of 63 replays have one snapshot and are ball-only |
| FR-A6 reduced motion | Done | tested by overriding the media query: step-by-step view with Previous/Next |
| FR-X1 training exclusions logged | Done | counts in `xg_metrics.json` |
| FR-X2 pre-shot features only | Done | leakage guard test |
| FR-X3 baseline and model, select by validation | Partial | logistic regression only (no gradient boosting); C chosen by grouped CV |
| FR-X4 metrics, calibration plot, StatsBomb comparison | Done | log loss 0.264 vs baseline 0.290 vs StatsBomb 0.251 |
| FR-X5 per-shot xG, penalties at the stored rate | Done | tests: range, penalty rate, totals add up |
| FR-X6 shot map | Done | marker size = xG, goals outlined, accessible table |
| FR-X7 model card | Done | renders from the metrics file |
| FR-E1 explanation and why for every moment | Done | tested on all ten matches |
| FR-E2 generated at build time, no LLM needed | Done | no LLM at all in this build |
| FR-E3 template fallback | Done (trivially) | templates are the only source |
| FR-E4 validator rejects invented names/numbers | Done | injected-name and number tests |
| FR-E5 "Automated analysis" label | Done | on every explanation and story |
| FR-E6 team tactical summaries | Cut | |
| FR-N1 pass network, FR-N2 momentum graph, FR-L1 highlight links | Cut | |
| FR-G1 glossary >= 15 terms | Done | 35 terms |
| FR-C1 StatsBomb attribution in every footer | Partial | text credit and link on every page; **logo not added yet** (StatsBomb asks for it) |

## Non-functional
| Req | Status | Evidence |
|---|---|---|
| NFR-1 performance | Done | page load 55 ms, 302 KB; a replay frame draws in 0.35 ms (far above 30 fps); measured on the dev machine |
| NFR-2 no external network | Done | 0 of 19 requests left localhost; static test forbids third-party URLs |
| NFR-3 usability, any moment within 2 clicks | Partial | every moment is two clicks away; the test with three non-football users is for you to run |
| NFR-4 accessibility | Done | keyboard-operable controls, ARIA labels, live captions, focus ring, reduced motion, contrast >= 4.5:1 (tested; the orange was darkened to pass) |
| NFR-5 portability | Partial | checked in the in-app Chromium browser only; Firefox not checked |
| NFR-6 maintainability | Done | small modules, type hints, JSON Schema for every output |
| NFR-7 reproducibility | Done | retraining gives a byte-identical model and metrics; outputs identical across runs (test) |
| NFR-8 security/privacy | Done | secret scan test; no cookies, trackers or storage |
| NFR-9 legal | Partial | attribution text present, no footage; add the StatsBomb logo |
| NFR-10 explainability | Done | formulas in the docs and the method notes on the pages |

## Success criteria (MX-01 section 10)
S1 offline: Done. S2 six goals, scoreline matches: Done. S3 at least 6 animated moments: Done. With `moment_xg_threshold` at 0.10 the final has 10 moments: 7 animated replays (6 multi-step ones plus Messi's one-step rebound goal) and 3 penalty cards. The cap is 10 moments, goals always kept. S4 model beats baseline with published calibration: Done. S5 grounded explanations: Done. **S6 three non-football testers: yours to run.** S7 reproducible rebuild: Done (see NFR-7).
