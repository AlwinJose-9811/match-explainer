"""360 freeze-frame snapshots and the last-defender (offside) line (FR-A4, FR-A5; MX-03 section 6.6).

Only players visible on the broadcast frame are present, so the UI states "visible players only".
360 coordinates share the event frame (verified: the actor's 360 location equals the event location).
"""
from __future__ import annotations

from typing import Any


def index_360(three_sixty: list[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    """event_uuid -> freeze_frame list (empty dict when the match has no 360 file)."""
    return {r["event_uuid"]: r["freeze_frame"] for r in three_sixty or []}


def _role(p: dict[str, Any]) -> str:
    if p.get("actor") or p.get("teammate"):
        return "own_keeper" if p.get("keeper") else "attacker"
    return "keeper" if p.get("keeper") else "defender"


def snapshot(frame: list[dict[str, Any]] | None, actor_xy: tuple[float, float] | None = None) -> dict[str, Any] | None:
    """Visible players with roles, plus the offside line = x of the deepest-advanced visible defender.

    The line is None when fewer than two defenders are visible. `actor_xy` adds the event's actor when the
    frame (an event-level shot freeze frame) does not flag one.
    """
    if not frame:
        return None
    players = [{"x": round(p["location"][0], 1), "y": round(p["location"][1], 1), "role": _role(p),
                "actor": bool(p.get("actor"))} for p in frame]
    if actor_xy is not None and not any(p["actor"] for p in players):
        players.append({"x": round(actor_xy[0], 1), "y": round(actor_xy[1], 1), "role": "attacker", "actor": True})
    defenders = [p["x"] for p in players if p["role"] == "defender"]
    return {"players": players, "offside_line_x": max(defenders) if len(defenders) >= 2 else None}
