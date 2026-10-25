# Match Explainer

Explains finished football matches to beginners: plain-English statistics, a tactical pitch view, and animated
replays of key moments. An offline Python pipeline processes free StatsBomb open data into JSON; a static
web page reads it. No backend, works offline.

Status: under construction (Phase 0). See docs/ for the specification and docs/CORRECTIONS.md for changes.

## Quick start (Windows)
```
python -m venv C:/mx-data/venv
C:/mx-data/venv/Scripts/activate
python tasks.py setup
python tasks.py fetch
python tasks.py verify
```

Data provided by [StatsBomb](https://github.com/statsbomb/open-data).
