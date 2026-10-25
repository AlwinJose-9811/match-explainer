"""Save a matplotlib sanity image of average positions and lines for three windows (Phase 2 review).

Usage: python scripts/check_positions.py [match_id]  ->  docs/checks/positions_<match_id>.png
Home = circles (blue), away = squares (orange, already mirrored). Dashed verticals are the DEF/MID/ATT lines.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ("full", "m0_15", "m105_120")


def pitch(ax) -> None:
    ax.add_patch(Rectangle((0, 0), 120, 80, fc="#E8F3E0", ec="#444", lw=1.2))
    ax.plot([60, 60], [0, 80], c="#444", lw=1)
    for x0 in (0, 102):
        ax.add_patch(Rectangle((x0, 18), 18, 44, fill=False, ec="#444", lw=1))
    ax.set_xlim(-2, 122)
    ax.set_ylim(82, -2)  # y grows downward like the SVG
    ax.set_aspect("equal")
    ax.axis("off")


def main() -> int:
    mid = sys.argv[1] if len(sys.argv) > 1 else "3869685"
    d = ROOT / "data" / "processed" / mid
    pos = json.loads((d / "positions.json").read_text(encoding="utf8"))
    summ = json.loads((d / "summary.json").read_text(encoding="utf8"))
    names = {"home": summ["teams"]["home"]["name"], "away": summ["teams"]["away"]["name"]}
    wins = {w["id"]: w for w in pos["windows"]}
    wins = [w for w in WINDOWS if w in wins] or ["full"]
    fig, axes = plt.subplots(len(wins), 1, figsize=(9, 6.2 * len(wins) / 1.6))
    axes = [axes] if len(wins) == 1 else list(axes)
    for ax, wid in zip(axes, wins):
        pitch(ax)
        for side, color, marker in (("home", "#2E75B6", "o"), ("away", "#C55A11", "s")):
            v = pos["data"][wid][side]
            for p in v["players"]:
                ax.scatter(p["x"], p["y"], s=230, c=color, marker=marker, ec="white", zorder=3)
                ax.text(p["x"], p["y"], str(p["jersey"] or ""), ha="center", va="center", color="white",
                        fontsize=7, zorder=4)
            for grp, x in v["lines"].items():
                if x is None:
                    continue
                lx = 120 - x if side == "away" else x
                ax.plot([lx, lx], [3, 77], ls="--", c=color, lw=1, alpha=.8)
            sh = v["shape"]
            tag = f"{names[side]}: {sh['label']} (def {v['lines']['def']})" if sh else f"{names[side]}: n/a"
            ax.text(2 if side == "home" else 118, -0.8, tag, ha="left" if side == "home" else "right",
                    fontsize=8, color=color)
        ax.set_title(f"{wins and pos['windows'][[w['id'] for w in pos['windows']].index(wid)]['label']}  "
                     f"(home attacks right; away mirrored)", fontsize=9, pad=14)
    out = ROOT / "docs" / "checks"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"positions_{mid}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
