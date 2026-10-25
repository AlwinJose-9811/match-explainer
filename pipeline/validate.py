"""JSON Schema validation of pipeline outputs (T-08) and fact-grounding checks for generated text (FR-E4)."""
from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import Draft202012Validator

from .config import ROOT


BANNED = ("deliberately", "on purpose", "intended to", "marking", "marked ", "mistake", "blunder", "fault of",
          "should have", "clearly", "obviously", "definitely")
COMMON_STARTERS = frozenset({"The", "A", "An", "At", "In", "With", "After", "From", "Penalties", "Own", "It", "This",
                             "When", "Even", "Playing", "Because", "They", "Both", "Goals", "Most", "That", "As", "But",
                             "Then", "Players", "Defenders", "One", "Two", "Three", "Straight", "Fewer", "Not", "Their"})
_NUM = re.compile(r"\d+(?:\.\d+)?")
_WORD = re.compile(r"(?<![\w'’])[A-ZÀ-ÝĀ-Ž][\w'’\-]*")


def validate_text(text: str, facts: dict[str, Any], max_sentences: int = 4, max_words: int = 150) -> list[str]:
    """Problems with generated text: every number and every name must come from `facts`.

    Numbers: all digit groups in the text must appear in some fact value. Names: every capitalised word
    (including at the start of a sentence unless it is a common English starter) must appear in some fact
    value. Also checks length and banned certainty phrases. An empty list means the text is grounded.
    """
    blob = " ".join(str(v) for v in facts.values())
    problems = [f"number {n!r} not in facts" for n in _NUM.findall(text) if n not in set(_NUM.findall(blob))]
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        for i, m in enumerate(_WORD.finditer(sentence)):
            word = m.group().strip("'’-")
            if i == 0 and m.start() == 0 and word in COMMON_STARTERS:
                continue
            if word not in blob:
                problems.append(f"name {word!r} not in facts")
    problems += [f"banned phrase {b!r}" for b in BANNED if b in text.lower()]
    if len(text.split()) > max_words:
        problems.append(f"too long ({len(text.split())} words)")
    if not 1 <= len(re.findall(r"[.!?](?:\s|$)", text)) <= max_sentences:
        problems.append("sentence count out of range")
    return problems


def validate_json(obj: Any, schema_name: str) -> None:
    """Raise ValueError listing every violation of schemas/<schema_name>.schema.json."""
    schema = json.loads((ROOT / "schemas" / f"{schema_name}.schema.json").read_text(encoding="utf8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(obj), key=lambda e: list(e.path))
    if errors:
        lines = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
        raise ValueError(f"{schema_name} failed validation:\n  " + "\n  ".join(lines))
