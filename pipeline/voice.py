"""Render the spoken commentary to audio with the Kokoro neural voice (offline, build time only).

    python -m pipeline.voice              # render every moment and story that has no clip yet
    python -m pipeline.voice --samples    # four British male voices reading one goal, to choose from

Needs the optional packages (kokoro-onnx, soundfile) and the model files in MX_KOKORO_DIR (default C:/mx-data/kokoro):
kokoro-v1.0.onnx and voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx (release model-files-v1.0).
Clips are named by a hash of (voice, speed, text), so changing the script or the voice re-renders only what changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .config import ROOT, load_config

SR = 24000
# kind -> (speed multiplier, pause after in seconds): lift on "!", slow and build before "...", plain otherwise
KINDS = {"excited": (1.07, 0.22), "build": (0.90, 0.50), "plain": (1.00, 0.32)}
AUDIO_DIR = ROOT / "web" / "audio"
SAMPLE_VOICES = ("bm_george", "bm_fable", "bm_lewis", "bm_daniel")


def settings(cfg: dict[str, Any] | None = None) -> tuple[str, float, str]:
    v = (cfg or load_config()).get("voice", {})
    return v.get("name", "bm_george"), float(v.get("speed", 1.0)), v.get("lang", "en-gb")


def clip_name(key: str, text: str, voice: str, speed: float) -> str:
    return f"{key}-{hashlib.sha1(f'{voice}|{speed}|{text}'.encode('utf8')).hexdigest()[:8]}.ogg"


MIN_BYTES = 8000   # a real clip is tens of kilobytes; a crashed write leaves only a ~3 KB header


def valid(path: Path) -> bool:
    return path.exists() and path.stat().st_size >= MIN_BYTES


def audio_rel(match_id: int, key: str, text: str, cfg: dict[str, Any] | None = None) -> str | None:
    """Web path of the clip for this exact text and voice, or None if it has not been (properly) rendered."""
    voice, speed, _ = settings(cfg)
    name = clip_name(key, text, voice, speed)
    return f"audio/{match_id}/{name}" if valid(AUDIO_DIR / str(match_id) / name) else None


def sentences(text: str) -> list[tuple[str, str]]:
    """Same split as the browser: [(text, kind)] with kind excited (!), build (...) or plain."""
    parts = [t.strip() for t in re.split(r"(?<=[.!?…])\s+", text.replace("...", "…")) if t.strip()]
    return [(t.rstrip("…") + ("," if t.endswith("…") else ""), "excited" if t.endswith("!") else "build" if t.endswith("…") else "plain") for t in parts]


def respell(text: str, cfg: dict[str, Any]) -> str:
    """Optional pronunciation fixes (config `pronunciations`: written name -> how to spell it for the voice)."""
    for written, spoken in (cfg.get("pronunciations") or {}).items():
        text = text.replace(written, spoken)
    return text


def load_tts():
    from kokoro_onnx import Kokoro   # imported lazily: the optional voice packages are not needed to build or test the site
    d = Path(os.environ.get("MX_KOKORO_DIR", "C:/mx-data/kokoro"))
    for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        if not (d / f).exists():
            raise SystemExit(f"missing {d / f}: download it from github.com/thewh1teagle/kokoro-onnx (release model-files-v1.0)")
    return Kokoro(str(d / "kokoro-v1.0.onnx"), str(d / "voices-v1.0.bin"))


def render(tts, text: str, voice: str, speed: float, lang: str, cfg: dict[str, Any]):
    """Speak sentence by sentence with per-sentence pace, join with pauses, balance loudness."""
    import numpy as np
    pieces = []
    for sent, kind in sentences(respell(text, cfg)):
        k_speed, pause = KINDS[kind]
        audio, _ = tts.create(sent, voice=voice, speed=speed * k_speed, lang=lang)
        pieces += [audio, np.zeros(int(SR * pause), dtype=np.float32)]
    x = np.concatenate(pieces[:-1]).astype(np.float32)
    x = np.concatenate([np.zeros(int(SR * 0.15), np.float32), x, np.zeros(int(SR * 0.25), np.float32)])
    rms = float(np.sqrt(np.mean(x ** 2))) or 1.0
    x = x * (0.085 / rms)                       # similar loudness for every clip
    peak = float(np.max(np.abs(x)))
    return x * (0.9 / peak) if peak > 0.9 else x


def write_clip(path: Path, audio) -> None:
    import soundfile as sf
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial")
    with sf.SoundFile(str(tmp), "w", SR, 1, format="OGG", subtype="VORBIS") as f:   # in one-second blocks: one big write
        for i in range(0, len(audio), SR):                                            # crashed the encoder on clips over ~30 s
            f.write(audio[i:i + SR])
    if tmp.stat().st_size < MIN_BYTES:
        tmp.unlink()
        raise RuntimeError(f"rendered clip {path.name} is empty")
    tmp.replace(path)   # only a complete clip ever has the final name


def _jobs(match_id: int) -> tuple[Path, dict[str, Any], dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    d = ROOT / "data" / "processed" / str(match_id)
    summary, moments = (json.loads((d / f"{n}.json").read_text(encoding="utf8")) for n in ("summary", "moments"))
    return d, summary, moments, [("story", summary["story"])] + [(m["id"], m["explanation"]) for m in moments["moments"]]


def missing_clips(match_id: int, cfg: dict[str, Any]) -> int:
    voice, speed, _ = settings(cfg)
    jobs = _jobs(match_id)[3]
    return sum(not valid(AUDIO_DIR / str(match_id) / clip_name(k, o.get("speech") or o["text"], voice, speed)) for k, o in jobs)


def render_match(tts, match_id: int, cfg: dict[str, Any], max_clips: int | None = None) -> int:
    """Render missing clips (at most `max_clips`) and write the clip paths into the JSON files. Returns how many were made.

    The voice engine runs out of stack after roughly 80 sentences in one process, so main() calls this in small batches,
    each in a fresh process; clips already made are kept (named by a hash of voice, speed and text).
    """
    voice, speed, lang = settings(cfg)
    d, summary, moments, jobs = _jobs(match_id)
    made, keep = 0, set()
    for key, obj in jobs:
        text = obj.get("speech") or obj.get("text")
        name = clip_name(key, text, voice, speed)
        path = AUDIO_DIR / str(match_id) / name
        if not valid(path) and (max_clips is None or made < max_clips):
            write_clip(path, render(tts, text, voice, speed, lang, cfg))
            made += 1
            print(f"  {match_id}/{name}  ({len(text.split())} words)", flush=True)
        if valid(path):
            obj["audio"] = f"audio/{match_id}/{name}"
            keep.add(name)
        else:
            obj.pop("audio", None)
    for old in (AUDIO_DIR / str(match_id)).glob("*.ogg"):
        if old.name not in keep and max_clips is None:
            old.unlink()
    (d / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    (d / "moments.json").write_text(json.dumps(moments, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    return made


def samples(tts, cfg: dict[str, Any]) -> None:
    """One goal read by several British male voices, as WAV files to listen to and choose from."""
    import soundfile as sf
    d = ROOT / "data" / "processed" / str(cfg["default_match_id"])
    m = next(x for x in json.loads((d / "moments.json").read_text(encoding="utf8"))["moments"] if x["clock"] == "35:22")
    out = ROOT / "data" / "interim" / "voice-samples"
    out.mkdir(parents=True, exist_ok=True)
    available = set(tts.get_voices())
    for v in SAMPLE_VOICES:
        if v in available:
            sf.write(str(out / f"{v}.wav"), render(tts, m["explanation"]["speech"], v, 1.0, "en-gb", cfg), SR)
            print(out / f"{v}.wav", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--match-id", type=int, help="render only this match (one batch; used internally)")
    ap.add_argument("--max-clips", type=int, default=None)
    args = ap.parse_args()
    cfg = load_config()
    if args.samples:
        samples(load_tts(), cfg)
        return 0
    if args.match_id is not None:                      # one batch, in this process
        render_match(load_tts(), args.match_id, cfg, args.max_clips)
        return 0
    import subprocess
    from .export import sync_web
    index = json.loads((ROOT / "data" / "processed" / "index.json").read_text(encoding="utf8"))
    for m in index["matches"]:
        for _ in range(20):                            # batches of 5 clips, each in a fresh process; a crashed batch is retried
            if not missing_clips(m["match_id"], cfg):
                break
            subprocess.run([sys.executable, "-m", "pipeline.voice", "--match-id", str(m["match_id"]), "--max-clips", "5"])
    left = sum(missing_clips(m["match_id"], cfg) for m in index["matches"])
    for m in index["matches"]:                          # final pass in one cheap step: link clips and remove stale ones
        d, summary, moments, jobs = _jobs(m["match_id"])
        voice, speed, _ = settings(cfg)
        keep = set()
        for key, obj in jobs:
            name = clip_name(key, obj.get("speech") or obj["text"], voice, speed)
            if valid(AUDIO_DIR / str(m["match_id"]) / name):
                obj["audio"] = f"audio/{m['match_id']}/{name}"
                keep.add(name)
        for old in (AUDIO_DIR / str(m["match_id"])).glob("*.ogg"):
            if old.name not in keep:
                old.unlink()
        (d / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
        (d / "moments.json").write_text(json.dumps(moments, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    sync_web()
    print(f"done; {left} clips still missing")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
