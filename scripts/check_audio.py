"""Technical sanity check of rendered audio (WAV or OGG): duration, loudness, silence, clipping.

Usage: python scripts/check_audio.py <file-or-folder> ...
This cannot judge how natural a voice sounds: a person has to listen. It catches empty, clipped or broken clips.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def stats(path: Path) -> dict[str, float]:
    x, sr = sf.read(str(path), dtype="float32")
    x = x if x.ndim == 1 else x.mean(axis=1)
    win = int(sr * 0.05)
    frames = np.sqrt(np.mean(x[: len(x) // win * win].reshape(-1, win) ** 2, axis=1))
    return {"seconds": round(len(x) / sr, 1), "sr": sr, "rms": round(float(np.sqrt(np.mean(x ** 2))), 3), "peak": round(float(np.abs(x).max()), 2),
            "silent_pct": round(float((frames < 0.004).mean() * 100), 1),
            "longest_silence_s": round(max((len(g) for g in np.split(frames < 0.004, np.where(np.diff(frames < 0.004))[0] + 1) if g.size and g[0]), default=0) * 0.05, 2)}


def main() -> int:
    files = [f for a in sys.argv[1:] for f in ([Path(a)] if Path(a).is_file() else sorted(Path(a).rglob("*")))
             if f.suffix in (".wav", ".ogg")]
    for f in files:
        print(f"{f.name:<34}", stats(f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
