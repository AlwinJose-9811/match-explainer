"""Windows-friendly replacement for `make`. Usage: python tasks.py <task>

Tasks: setup, fetch, verify, train, build, test, serve, publish, voice, all
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(*args: str) -> None:
    print("->", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def build() -> None:
    cfg = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf8"))
    for m in cfg["matches"]:
        run(PY, "-m", "pipeline.run_pipeline", "--match-id", str(m["match_id"]), "--skip-train")


def publish() -> None:
    """Publish the web/ folder to the gh-pages branch, which GitHub Pages serves (run after committing your changes)."""
    run("git", "subtree", "split", "--prefix", "web", "-b", "gh-pages-tmp")
    try:
        run("git", "push", "origin", "gh-pages-tmp:gh-pages", "--force")
    finally:
        run("git", "branch", "-D", "gh-pages-tmp")


TASKS = {
    "publish": publish,
    "setup": lambda: run(PY, "-m", "pip", "install", "-r", "requirements.txt"),
    "fetch": lambda: run(PY, "scripts/fetch_data.py"),
    "verify": lambda: run(PY, "scripts/verify_ids.py"),
    "train": lambda: run(PY, "-m", "pipeline.xg_train"),
    "build": build,
    "test": lambda: run(PY, "-m", "pytest", "-q"),
    "serve": lambda: run(PY, "-m", "http.server", "-d", "web", "8000"),
    # optional: render the recorded commentary voice (needs requirements-voice.txt and the Kokoro model files, see pipeline/voice.py)
    "voice": lambda: run(PY, "-m", "pipeline.voice"),
}


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name == "all":
        for t in ("verify", "train", "build", "test"):
            TASKS[t]()
        return 0
    if name not in TASKS:
        print(__doc__)
        return 2
    TASKS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
