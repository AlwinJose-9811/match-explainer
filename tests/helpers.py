"""Builders for tiny synthetic StatsBomb-shaped events used by unit tests."""
from __future__ import annotations

from typing import Any

TEAMS = {"A": {"id": 1, "name": "Alpha"}, "B": {"id": 2, "name": "Beta"}}


def ts(seconds: float) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def ev(index: int, period: int, sec: float, typ: str, team: str, poss: int, poss_team: str | None = None,
       loc: list[float] | None = None, **extra: Any) -> dict[str, Any]:
    e: dict[str, Any] = {
        "id": f"id-{index}", "index": index, "period": period, "timestamp": ts(sec),
        "minute": int(sec // 60), "second": int(sec % 60), "type": {"name": typ},
        "team": TEAMS[team], "possession": poss, "possession_team": TEAMS[poss_team or team],
        "play_pattern": {"name": "Regular Play"}, "player": {"id": index, "name": f"P{index}"},
    }
    if loc is not None:
        e["location"] = loc
    e.update(extra)
    return e


def sample_events() -> list[dict[str, Any]]:
    """Alpha: 3 passes (1 incomplete, 1 corner), 1 goal shot, a yellow. Beta: 1 pass, 1 saved shot,
    a foul, a second yellow. Plus a period-5 shootout goal that must never count."""
    return [
        ev(1, 1, 0, "Starting XI", "A", 1),
        ev(2, 1, 1, "Pass", "A", 1, loc=[60, 40], **{"pass": {"end_location": [70, 40]}}),
        ev(3, 1, 5, "Pass", "A", 1, loc=[70, 40], **{"pass": {"end_location": [90, 30], "outcome": {"name": "Incomplete"}}}),
        ev(4, 1, 20, "Pass", "B", 2, loc=[50, 40], **{"pass": {"end_location": [60, 40], "type": {"name": "Corner"}}}),
        ev(5, 1, 30, "Pass", "A", 3, loc=[80, 40], **{"pass": {"end_location": [100, 40]}}),
        ev(6, 1, 36, "Shot", "A", 3, loc=[105, 38],
           shot={"outcome": {"name": "Goal"}, "statsbomb_xg": 0.3, "type": {"name": "Open Play"},
                 "end_location": [120, 40, 1]}),
        ev(7, 1, 50, "Shot", "B", 4, loc=[100, 40],
           shot={"outcome": {"name": "Saved"}, "statsbomb_xg": 0.1, "type": {"name": "Open Play"}}),
        ev(8, 1, 55, "Foul Committed", "B", 4, loc=[50, 40], foul_committed={"card": {"name": "Yellow Card"}}),
        ev(9, 2, 10, "Bad Behaviour", "B", 5, loc=[50, 40], bad_behaviour={"card": {"name": "Second Yellow"}}),
        ev(10, 2, 30, "Pass", "A", 6, loc=[40, 40], **{"pass": {"end_location": [50, 40]}}),
        ev(11, 2, 45, "Foul Committed", "A", 6, loc=[40, 40], foul_committed={"card": {"name": "Yellow Card"}}),
        ev(12, 5, 5, "Shot", "A", 7, loc=[108, 40],
           shot={"outcome": {"name": "Goal"}, "statsbomb_xg": 0.78, "type": {"name": "Penalty"}}),
        ev(13, 5, 40, "Shot", "B", 8, loc=[108, 40],
           shot={"outcome": {"name": "Goal"}, "statsbomb_xg": 0.78, "type": {"name": "Penalty"}}),
    ]
