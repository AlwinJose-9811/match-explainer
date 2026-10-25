"""JSON Schema validation of pipeline outputs (T-08)."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from .config import ROOT


def validate_json(obj: Any, schema_name: str) -> None:
    """Raise ValueError listing every violation of schemas/<schema_name>.schema.json."""
    schema = json.loads((ROOT / "schemas" / f"{schema_name}.schema.json").read_text(encoding="utf8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(obj), key=lambda e: list(e.path))
    if errors:
        lines = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
        raise ValueError(f"{schema_name} failed validation:\n  " + "\n  ".join(lines))
