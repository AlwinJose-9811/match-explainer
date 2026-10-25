"""Fetch only the StatsBomb open-data files this project needs (sparse, blobless clone).

Stage 1 checks out competitions.json and the matches lists; stage 2 adds, per match, the
events file (all matches), plus lineups and three-sixty (picker matches only).
Safe to re-run: git skips files already present.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/statsbomb/open-data"
ROOT = Path(__file__).resolve().parents[1]


def git(cwd: Path, *args: str, stdin: str | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, input=stdin, text=True, check=True)


def season_match_ids(data: Path, comp: int, season: int) -> list[int]:
    f = data / "matches" / str(comp) / f"{season}.json"
    return [m["match_id"] for m in json.loads(f.read_text(encoding="utf8"))]


def main() -> int:
    cfg = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf8"))
    train = json.loads((ROOT / "config" / "train_competitions.json").read_text(encoding="utf8"))
    data = Path(cfg["raw_dir"])
    repo_dir = data.parent
    if not (repo_dir / ".git").exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
                        REPO, str(repo_dir)], check=True)
        git(repo_dir, "sparse-checkout", "init", "--no-cone")

    seasons = {(m["competition_id"], m["season_id"]) for m in cfg["matches"]}
    seasons |= {(c["competition_id"], c["season_id"]) for k in ("train", "test") for c in train[k]}
    stage1 = ["/data/competitions.json"] + [f"/data/matches/{c}/{s}.json" for c, s in sorted(seasons)]
    git(repo_dir, "sparse-checkout", "set", "--no-cone", "--stdin", stdin="\n".join(stage1) + "\n")
    git(repo_dir, "checkout")

    picker = {m["match_id"] for m in cfg["matches"]}
    paths = list(stage1)
    for comp, season in sorted({(c["competition_id"], c["season_id"]) for k in ("train", "test") for c in train[k]}):
        paths += [f"/data/events/{i}.json" for i in season_match_ids(data, comp, season)]
    for mid in sorted(picker):
        paths += [f"/data/events/{mid}.json", f"/data/lineups/{mid}.json", f"/data/three-sixty/{mid}.json"]
    print(f"Fetching {len(paths) - len(stage1)} match files ...", flush=True)
    git(repo_dir, "sparse-checkout", "set", "--no-cone", "--stdin", stdin="\n".join(sorted(set(paths))) + "\n")
    git(repo_dir, "checkout")
    print("Done. Data at", data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
