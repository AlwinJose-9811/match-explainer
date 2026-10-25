"""Print the detected moments table (clock, player, type, xG, steps) for review.

Usage: python scripts/print_moments.py [match_id ...]   (default: all processed matches)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    proc = ROOT / "data" / "processed"
    index = json.loads((proc / "index.json").read_text(encoding="utf8"))
    ids = [int(a) for a in sys.argv[1:]] or [m["match_id"] for m in index["matches"]]
    for mid in ids:
        mom = json.loads((proc / str(mid) / "moments.json").read_text(encoding="utf8"))
        summ = json.loads((proc / str(mid) / "summary.json").read_text(encoding="utf8"))
        t = summ["teams"]
        print(f"\n{t['home']['name']} {summ['score']['home']}-{summ['score']['away']} {t['away']['name']}  (match {mid})")
        print(f"{'id':<4}{'clock':>7}  {'type':<9}{'team':<12}{'player':<30}{'xG(SB)':>7} {'pen':<4}{'steps':>5} {'passes':>6} "
              f"{'dur_s':>6} {'360':>4} {'line':>5} {'gap':>5}  note")
        for m in mom["moments"]:
            f, sn = m["facts"], m["snapshots"]
            has360 = "yes" if (sn["key_pass"] or sn["shot"]) else "-"
            note = ("rebound " if f.get("rebound") else "") + (f.get("card") or "") + (f"{f['play_pattern']}" if f.get("play_pattern") not in (None, "Regular Play") else "")
            print(f"{m['id']:<4}{m['clock']:>7}  {m['type']:<9}{m['team_name']:<12}{(m['player'] or '-')[:28]:<30}"
                  f"{(m['xg_statsbomb'] if m['xg_statsbomb'] is not None else float('nan')):>7.2f} {'PEN' if m['is_penalty'] else '':<4}"
                  f"{len(m['sequence']):>5} {f.get('sequence_len', '-'):>6} {f.get('duration_s', '-'):>6} {has360:>4} "
                  f"{str(f.get('defensive_line_height', '-')):>5} {str(f.get('gap_to_line', '-')):>5}  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
