"""Debug helper: render every sentence of a match in its own process and report which ones crash the voice engine.

Usage: python scripts/find_voice_crash.py <match_id>
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.voice import sentences  # noqa: E402

CODE = """
import sys
sys.path.insert(0, r'%s')
from pipeline.voice import load_tts
t = load_tts()
a, sr = t.create(sys.argv[1], voice='bm_george', speed=1.0, lang='en-gb')
print('ok', len(a))
"""


def main() -> int:
    mid = sys.argv[1]
    d = ROOT / "data" / "processed" / mid
    summary = json.loads((d / "summary.json").read_text(encoding="utf8"))
    moments = json.loads((d / "moments.json").read_text(encoding="utf8"))["moments"]
    texts = [("story", summary["story"]["speech"])] + [(m["id"], m["explanation"]["speech"]) for m in moments]
    for key, text in texts:
        for sent, kind in sentences(text):
            r = subprocess.run([sys.executable, "-c", CODE % ROOT, sent], capture_output=True, text=True)
            if r.returncode != 0:
                print(f"CRASH ({r.returncode}) in {key}: {sent!r}", flush=True)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
