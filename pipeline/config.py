"""Configuration loading: config/default.json plus the MX_RAW_DIR environment override."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict[str, Any]:
    """Read config/default.json; MX_RAW_DIR (if set) overrides raw_dir."""
    cfg = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf8"))
    cfg["raw_dir"] = os.environ.get("MX_RAW_DIR", cfg["raw_dir"])
    return cfg


def raw_dir(cfg: dict[str, Any]) -> Path:
    return Path(cfg["raw_dir"])


def processed_dir(match_id: int) -> Path:
    return ROOT / "data" / "processed" / str(match_id)
