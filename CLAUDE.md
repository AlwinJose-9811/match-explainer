# Match Explainer - agent instructions

## What this is
Static website + offline Python pipeline that explains finished football matches to
beginners using StatsBomb open data. Specs live in docs/ (MX-01 to MX-04) with the scope
changes recorded in docs/CORRECTIONS.md (read it first; it overrides the .docx files).
Follow MX-02 requirement IDs and MX-03 design. Do not add features outside the MX-02 M and S lists
plus the "Listen" button.

## Commands (Windows: no make; use tasks.py)
- Setup: python -m venv C:/mx-data/venv ; C:/mx-data/venv/Scripts/activate ; python tasks.py setup
- Fetch data: python tasks.py fetch   (raw data lives OUTSIDE the repo, see config/default.json raw_dir)
- Verify data: python tasks.py verify
- Train xG: python tasks.py train
- Build all picker matches (10): python tasks.py build   (then optionally python tasks.py voice for the recorded commentary)   (single: python -m pipeline.run_pipeline --match-id 3869685)
- Test: python tasks.py test
- Serve site: python tasks.py serve   (http://localhost:8000)

## Rules
- Read raw StatsBomb JSON directly; do not call external data APIs at runtime.
- Never use shot.outcome, shot.end_location or shot.statsbomb_xg as xG features.
- Exclude period 5 (shootout) from possession, positions and xG training.
- Keep coordinates in the 120 x 80 StatsBomb frame; mirror the away team only at export.
- Penalties: fixed conversion rate, shown as simple cards (no build-up or snapshot).
- Show moments as a clock time (mm:ss), StatsBomb minutes are 0-based.
- Explanations are template-based (no LLM in this build); every text is labelled "Automated analysis".
- Web app: vanilla JS + SVG, no framework, no third-party runtime requests, works offline.
  "Listen" button uses the browser Web Speech API only.
- Keep modules small (about 300 lines), add type hints and tests for each module.
- Do not commit secrets, raw data or large files.
- Always keep the StatsBomb attribution footer (text + logo, see licence) and the "Automated analysis" labels.
- If a spec detail conflicts with the real data, stop and report it rather than guessing.

## Workflow
- One task (T-xx) per commit. Run pytest before committing. Stop at each gate (G1 to G4) and wait for the owner.
