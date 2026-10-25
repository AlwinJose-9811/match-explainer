"""Template explanations for every moment plus the match story (FR-E1 to FR-E5, FR-M5).

No LLM is used in this build: text is deterministic, built only from structured facts, checked by
validate.validate_text, and always labelled "Automated analysis". The facts passed to the validator are the
same strings the templates interpolate, so any name or number outside them is rejected.
"""
from __future__ import annotations

from typing import Any

from .config import load_config
from .speech_script import spoken_moment, spoken_story
from .validate import validate_text
from .voice import audio_rel

LABEL = "Automated analysis"
SET_PIECE = {"From Corner": "from a corner", "From Free Kick": "from a free kick", "From Throw In": "from a throw-in",
             "From Goal Kick": "from a goal kick", "From Kick Off": "straight from the kick-off",
             "From Keeper": "from a goalkeeper's throw or kick", "From Counter": "on a fast counter-attack"}
MISS = {"Saved": "the goalkeeper saved it", "Saved to Post": "the goalkeeper pushed it onto the post",
        "Blocked": "a defender blocked it", "Off T": "it went off target", "Wayward": "it went well off target",
        "Post": "it hit the post", "Saved Off Target": "the goalkeeper kept it out"}
HIGH_LINE_FROM_GOAL = 60.0   # opponents' last visible defender at least this far from their own goal
GAP_STRETCHED = 5.0          # key pass ended this many units beyond the last visible defender


def display_names(lineups: list[dict[str, Any]], overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Full StatsBomb name -> short display name (the lineup nickname, else the full name).

    `overrides` (config `name_overrides`) fixes nicknames StatsBomb cuts short, e.g. 'Randal Kolo' for
    'Randal Kolo Muani'; such a cut is indistinguishable from a deliberate short name like 'Kylian Mbappé'.
    """
    out = {p["player_name"]: p.get("player_nickname") or p["player_name"] for t in lineups for p in t["lineup"]}
    out.update({k: v for k, v in (overrides or {}).items() if k in out})
    return out


def per_ten(xg: float) -> str:
    n = round(xg * 10)
    return "fewer than 1 in 10" if n < 1 else f"about {n} in 10"


def text_facts(m: dict[str, Any], summary: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    """Everything a template may mention, already formatted as the text will show it."""
    teams = summary["teams"]
    other = "away" if m["team"] == "home" else "home"
    f = m["facts"]
    xg = m["xg_model"] if m["xg_model"] is not None else m["xg_statsbomb"]
    out: dict[str, Any] = {"clock": m["clock"], "team": m["team_name"], "opponent": teams[other]["name"],
                           "player": names.get(m["player"], m["player"]) if m["player"] else None,
                           "outcome_phrase": MISS.get(m["outcome"] or "", "it did not go in")}
    if xg is not None:
        out.update(xg=f"{xg:.2f}", per_ten=per_ten(xg))
    if f.get("assist_player"):
        out["assist"] = names.get(f["assist_player"], f["assist_player"])
    for k in ("sequence_len", "gap_to_line", "defensive_line_height"):
        if f.get(k) is not None:
            out[k] = f"{f[k]:.1f}" if isinstance(f[k], float) else f[k]
    return out


def _how(f: dict[str, Any], facts: dict[str, Any], pattern: str | None) -> str:
    if f.get("rebound"):
        return "from a rebound after an earlier shot in the same move"
    n = f.get("sequence_len", 0)
    if pattern in SET_PIECE:
        if pattern not in ("From Corner", "From Free Kick", "From Counter") and n >= 2:
            return f"after a {n}-pass move that started {SET_PIECE[pattern]}"
        return SET_PIECE[pattern]
    return "with a direct shot" if n == 0 else ("after a single pass" if n == 1 else f"after a {n}-pass move")


def _why(f: dict[str, Any], facts: dict[str, Any]) -> str:
    gap, line = f.get("gap_to_line"), f.get("defensive_line_height")
    if f.get("rebound"):
        return "The first shot was saved, and the defence had not yet got back into shape when the ball came loose."
    if f.get("play_pattern") == "From Counter":
        return "The attack started on a quick counter, before the defence could get back into position."
    if gap is not None and gap > GAP_STRETCHED:
        return (f"The defence was stretched: the key pass reached {facts['gap_to_line']} units beyond the last "
                "visible defender, leaving space to attack.")
    if line is not None and line >= HIGH_LINE_FROM_GOAL:
        return (f"The defenders had pushed far up the pitch, {facts['defensive_line_height']} units from their own "
                "goal, so a ball played behind them was dangerous.")
    if f.get("first_time"):
        return "The shot was taken first time, which gives the goalkeeper very little time to react."
    if f.get("sequence_len", 0) >= 5:
        return "A long passing move gave the team time to work a shooting chance."
    if f.get("shot_distance", 99) <= 10:
        return "The shot came from very close to goal, where chances are usually at their best."
    return "The team created a clear shooting chance from this move."


def explain_moment(m: dict[str, Any], summary: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    """Build and validate the explanation dict for one moment."""
    facts = text_facts(m, summary, names)
    f, t, who, team, clock = m["facts"], m["type"], facts.get("player"), m["team_name"], m["clock"]
    gloss = f"{facts['xg']} xG (expected goals), meaning {facts['per_ten']} shots like this are goals" if "xg" in facts else ""
    if m["is_penalty"]:
        end = "scored a penalty for" if m["is_goal"] else "took a penalty for"
        text = f"At {clock}, {who} {end} {team}" + ("." if m["is_goal"] else f", but {facts['outcome_phrase']}.")
        text += f" A penalty is a free shot at the goalkeeper after a foul in the box, and {facts['per_ten']} are scored."
        why = ("Penalties are scored most of the time, so the foul that earned it mattered more than the kick."
               if m["is_goal"] else "Even though most penalties are scored, a save, a miss or the post can still stop one.")
    elif t == "red_card":
        what = "was sent off after a second yellow card" if f.get("card") == "Second Yellow" else "was shown a red card"
        text = (f"At {clock}, {who} of {team} {what}. A sent-off player cannot be replaced, so {team} played the rest "
                "of the match with one player fewer.")
        why = "With fewer players, a team has less pitch covered and usually has to defend deeper."
    elif t == "own_goal":
        text = (f"At {clock}, {who or 'a defender'} put the ball into their own net, which counted as a goal for {team}. "
                "An own goal happens when the ball is accidentally played into a team's own net.")
        why = "Own goals show how one touch near the goal can change a match."
    else:
        how = _how(f, facts, f.get("play_pattern"))
        if m["is_goal"]:
            text = f"At {clock}, {who} scored for {team} {how}."
        else:
            text = f"At {clock}, {who} had a big chance for {team} {how}, but {facts['outcome_phrase']}."
        text += f" The chance was worth {gloss}."
        if facts.get("assist") and facts["assist"] != who:
            text += f" The last pass before the shot came from {facts['assist']}."
        why = _why(f, facts)
    problems = validate_text(text, facts, max_sentences=3, max_words=80) + validate_text(
        why, {**facts, "extra": ""}, max_sentences=1, max_words=35)
    speech = spoken_moment(m, facts)
    problems += check_speech(speech, facts, 110)
    if problems:
        raise ValueError(f"moment {m['id']} explanation failed validation: {problems}\n{text}\n{why}\n{speech}")
    return {"text": text, "why": why, "speech": speech, "source": "template", "label": LABEL}


def check_speech(speech: str, facts: dict[str, Any], max_words: int) -> list[str]:
    """Spoken text must be grounded like written text, and must contain no digits (they are spoken as words)."""
    problems = validate_text(speech, facts, max_sentences=9, max_words=max_words)
    return problems + (["spoken text contains digits"] if any(c.isdigit() for c in speech) else [])


def story_facts(summary: dict[str, Any], moments: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    t, sc, ps, st = summary["teams"], summary["score"], summary["possession"], summary["stats"]
    h, a = t["home"]["name"], t["away"]["name"]
    goals = []
    for m in moments["moments"]:
        if m["is_goal"]:
            who = names.get(m["player"], m["player"]) if m["player"] else m["team_name"]
            goals.append(f"{who} at {m['clock']}" + (" (penalty)" if m["is_penalty"] else ""))
    xg = {s: st[s]["xg_model"] if st[s]["xg_model"] is not None else st[s]["xg_statsbomb"] for s in ("home", "away")}
    return {"home": h, "away": a, "hs": sc["home"], "as": sc["away"], "stage": summary.get("stage"),
            "competition": summary["competition"], "season": summary["season"], "note": sc.get("note"),
            "ph": round(ps["home"] * 100), "pa": round(ps["away"] * 100), "xh": f"{xg['home']:.2f}",
            "xa": f"{xg['away']:.2f}", "goals": goals, "xg": xg}


def explain_story(summary: dict[str, Any], moments: dict[str, Any], names: dict[str, str]) -> dict[str, str]:
    """Match story, at most 150 words, from facts only."""
    f = story_facts(summary, moments, names)
    h, a, hs, as_ = f["home"], f["away"], f["hs"], f["as"]
    where = f" in the {f['stage']} of the {f['competition']} {f['season']}" if f["stage"] else f" in the {f['competition']} {f['season']}"
    s1 = (f"{h} and {a} drew {hs}-{as_}{where}." if hs == as_ else
          f"{h if hs > as_ else a} beat {a if hs > as_ else h} {max(hs, as_)}-{min(hs, as_)}{where}.")
    ball = (h, f["ph"], a, f["pa"]) if f["ph"] >= f["pa"] else (a, f["pa"], h, f["ph"])
    better = (h, f["xh"], a, f["xa"]) if f["xg"]["home"] >= f["xg"]["away"] else (a, f["xa"], h, f["xh"])
    also = "also " if ball[0] == better[0] else ""
    s3 = (f"{ball[0]} had more of the ball ({ball[1]} percent to {ball[3]} percent), and {better[0]} {also}created the "
          f"better chances by expected goals, or xG, a measure of chance quality ({better[1]} to {better[3]}).")
    goals = f["goals"]
    s4 = ("The goals came from " + ", ".join(goals[:-1]) + (" and " if len(goals) > 1 else "") + goals[-1] + "."
          if goals else "There were no goals.")
    text = " ".join(x for x in (s1, f["note"], s3, s4) if x)
    flat = {k: v for k, v in f.items() if k != "xg"}
    flat["goals"] = " ".join(goals)
    problems = validate_text(text, flat, max_sentences=6, max_words=150)
    speech = spoken_story(summary, moments, names)
    problems += check_speech(speech, flat, 150)
    if problems:
        raise ValueError(f"story failed validation: {problems}\n{text}\n{speech}")
    return {"text": text, "speech": speech, "label": LABEL}


def explain_match(summary: dict[str, Any], moments: dict[str, Any], lineups: list[dict[str, Any]],
                  overrides: dict[str, str] | None = None) -> None:
    """Fill moments[*].explanation and summary.story in place."""
    names = display_names(lineups, overrides)
    for m in moments["moments"]:
        m["explanation"] = explain_moment(m, summary, names)
    summary["story"] = explain_story(summary, moments, names)
    used = {m["player"] for m in moments["moments"]} | {m["facts"].get("assist_player") for m in moments["moments"]}
    for m in moments["moments"]:
        used |= {s["player"] for s in m["sequence"]} | {s["recipient"] for s in m["sequence"]}
    moments["names"] = {n: names.get(n, n) for n in sorted(x for x in used if x)}  # full name -> display name for the UI
    link_audio(summary, moments)


def link_audio(summary: dict[str, Any], moments: dict[str, Any]) -> None:
    """Point each explanation and the story at its rendered clip (if python -m pipeline.voice has made it)."""
    cfg, mid = load_config(), summary["match_id"]
    pairs = [("story", summary["story"])] + [(m["id"], m["explanation"]) for m in moments["moments"]]
    for key, obj in pairs:
        path = audio_rel(mid, key, obj.get("speech") or obj["text"], cfg)
        if path:
            obj["audio"] = path
