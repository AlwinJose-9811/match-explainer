"""Read and validate the StatsBomb files for one match (FR-D1, FR-D2)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_EVENT_KEYS = ("id", "index", "period", "timestamp", "minute", "second", "type", "team", "possession")
REQUIRED_MATCH_KEYS = ("match_id", "match_date", "home_team", "away_team", "home_score", "away_score",
                       "competition", "season")


class DataError(Exception):
    """A required file or field is missing; the message names the match and the item."""

    def __init__(self, match_id: int | str, item: str) -> None:
        super().__init__(f"match {match_id}: {item}")
        self.match_id = match_id
        self.item = item


@dataclass
class MatchData:
    record: dict[str, Any]
    lineups: list[dict[str, Any]]
    events: list[dict[str, Any]]
    three_sixty: list[dict[str, Any]] | None  # None when the match has no 360 file


def _read(path: Path, match_id: int | str, what: str) -> Any:
    if not path.exists():
        raise DataError(match_id, f"{what} file missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except json.JSONDecodeError as exc:
        raise DataError(match_id, f"{what} file is not valid JSON: {path} ({exc})") from exc


def find_match_record(raw: Path, match_id: int) -> dict[str, Any]:
    """Locate the match in data/matches/*/*.json."""
    if not raw.exists():
        raise DataError(match_id, f"raw data folder missing: {raw} (run: python tasks.py fetch)")
    for f in sorted((raw / "matches").glob("*/*.json")):
        for rec in json.loads(f.read_text(encoding="utf8")):
            if rec.get("match_id") == match_id:
                missing = [k for k in REQUIRED_MATCH_KEYS if k not in rec]
                if missing:
                    raise DataError(match_id, f"match record lacks fields {missing} in {f.name}")
                return rec
    raise DataError(match_id, f"not found in any matches file under {raw / 'matches'}")


def load_match(raw: Path, match_id: int) -> MatchData:
    """Load matches record, lineups, events and (if present) three-sixty for a match."""
    record = find_match_record(raw, match_id)
    events = _read(raw / "events" / f"{match_id}.json", match_id, "events")
    lineups = _read(raw / "lineups" / f"{match_id}.json", match_id, "lineups")
    for e in events[:50]:
        missing = [k for k in REQUIRED_EVENT_KEYS if k not in e]
        if missing:
            raise DataError(match_id, f"event {e.get('id')} lacks fields {missing}")
    f360 = raw / "three-sixty" / f"{match_id}.json"
    return MatchData(record, lineups, events, _read(f360, match_id, "three-sixty") if f360.exists() else None)
