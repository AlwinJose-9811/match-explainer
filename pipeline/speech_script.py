"""Spoken commentary scripts: written to be heard, not read.

Differences from the on-screen text: no digits, clock times or "xG" jargon (numbers become words, minutes become
"the thirty-sixth minute"), short punchy sentences, exclamations on goals so the voice can lift its tone, and a
little variety in the opening line. Every name still comes from the facts, and the validator checks it.
"""
from __future__ import annotations

import re
from typing import Any

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
IRREGULAR = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}


def words(n: int) -> str:
    """0-999 as English words: 36 -> 'thirty-six', 108 -> 'one hundred and eight'."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else "")
    return f"{ONES[n // 100]} hundred" + (f" and {words(n % 100)}" if n % 100 else "")


def ordinal(n: int) -> str:
    """36 -> 'thirty-sixth', 108 -> 'one hundred and eighth'."""
    w = words(n)
    head, sep, last = w.rpartition("-") if "-" in w.split(" ")[-1] else w.rpartition(" ")
    if last in IRREGULAR:
        last = IRREGULAR[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return f"{head}{sep}{last}"


def year_words(y: int) -> str:
    """2022 -> 'twenty twenty-two', 2005 -> 'two thousand and five'."""
    if 2000 <= y <= 2009:
        return "two thousand" + (f" and {words(y - 2000)}" if y > 2000 else "")
    return f"{words(y // 100)} {words(y % 100)}" if y % 100 else f"{words(y // 100)} hundred"


def speak_years(text: str) -> str:
    """Replace every 19xx/20xx in a name like 'FIFA World Cup 2022' or '2015/2016' with spoken years."""
    out = re.sub(r"\b((?:19|20)\d{2})/((?:19|20)\d{2})\b", lambda m: f"{year_words(int(m[1]))} to {year_words(int(m[2]))}", text)
    return re.sub(r"\b((?:19|20)\d{2})\b", lambda m: year_words(int(m[1])), out)


def per_ten(xg: float) -> str:
    n = round(xg * 10)
    return "fewer than one in ten" if n < 1 else f"about {words(n)} in ten"


def minute_phrase(m: dict[str, Any]) -> str:
    return f"the {ordinal(m['minute'] + 1)} minute"   # StatsBomb minutes are 0-based: 35:22 is in the 36th minute


HOW = {"From Corner": "It comes from a corner.", "From Free Kick": "It comes from a free kick.",
       "From Goal Kick": "It starts from a goal kick.", "From Kick Off": "It comes straight from the kick-off.",
       "From Keeper": "It starts with the goalkeeper.", "From Counter": "It all starts with a lightning counter-attack."}
OUTCOME = {"Saved": "the goalkeeper saves it", "Saved to Post": "the goalkeeper tips it onto the post", "Blocked": "a defender gets in the way",
           "Off T": "it goes wide", "Wayward": "it sails well wide", "Post": "it hits the post", "Saved Off Target": "the goalkeeper keeps it out"}
GOAL_OPEN = ("{when}, and it's {who} for {team}!", "Goal! {who} scores for {team} in {when}!", "{team} strike! {who} finds the net in {when}!")
CHANCE_OPEN = ("{when}, and {team} have a big chance. {who} shoots", "Big chance in {when}! {who} shoots for {team}")


def _how(f: dict[str, Any], who: str) -> str:
    n = f.get("sequence_len", 0)
    if f.get("rebound"):
        return f"{who} is first to the rebound."
    pattern = f.get("play_pattern")
    if pattern in HOW and not (pattern in ("From Goal Kick", "From Keeper", "From Kick Off") and n >= 2):
        return HOW[pattern]
    if n >= 2:
        return f"A smooth move of {words(n)} passes opens the defence."
    return "One pass, and the chance is on." if n == 1 else "A direct shot, and the defence is caught out."


def _why(f: dict[str, Any]) -> str:
    gap, line = f.get("gap_to_line"), f.get("defensive_line_height")
    if f.get("rebound"):
        return "The first shot was saved, and the defence was caught out as the ball ran loose."
    if f.get("play_pattern") == "From Counter":
        return "The defence simply could not get back in time."
    if gap is not None and gap > 5:
        return "The defence was stretched, and the pass found space behind the last defender."
    if line is not None and line >= 60:
        return "The defenders had pushed right up the pitch, so a ball over the top was dangerous."
    if f.get("first_time"):
        return "Hit first time, the goalkeeper had almost no time to react."
    if f.get("sequence_len", 0) >= 5:
        return "Patient build-up, and in the end the chance opened up."
    if f.get("shot_distance", 99) <= 10:
        return "From that close to goal, chances are usually at their best."
    return "A clear chance, from a clean move."


def spoken_moment(m: dict[str, Any], facts: dict[str, Any]) -> str:
    """Commentary-style script for one moment. `facts` comes from explain.text_facts."""
    who, team, f, t = facts.get("player") or facts["team"], facts["team"], m["facts"], m["type"]
    when, variant = minute_phrase(m), int(m["id"][1:]) % 3
    xg = m["xg_model"] if m["xg_model"] is not None else m["xg_statsbomb"]
    if m["is_penalty"]:
        head = f"{when.capitalize()}, penalty for {team}. {who} steps up"
        end = " and scores!" if m["is_goal"] else f", but {OUTCOME.get(m['outcome'] or '', 'it does not go in')}!"
        tail = ("Most penalties go in, about " + per_ten(xg).replace("about ", "") + " of them, so the odds favour the taker."
                if m["is_goal"] else "Most penalties go in, so that one really hurts.")
        return f"{head}{'...' if m['is_goal'] else ''}{end} {tail}"
    if t == "red_card":
        reason = "after a second yellow card" if f.get("card") == "Second Yellow" else "with a straight red card"
        return f"{when.capitalize()}, red card! {who} of {team} is sent off {reason}. {team} must play on with one player fewer."
    if t == "own_goal":
        return f"{when.capitalize()}, and it's an own goal! {who} turns the ball into their own net, and {team} take it."
    parts = []
    if m["is_goal"]:
        parts.append(GOAL_OPEN[variant].format(when=when.capitalize() if variant == 0 else when, who=who, team=team))
    else:
        parts.append(CHANCE_OPEN[variant % 2].format(when=when.capitalize() if variant % 2 == 0 else when, who=who, team=team)
                     + f"... but {OUTCOME.get(m['outcome'] or '', 'it does not go in')}!")
    parts.append(_how(f, who))
    if xg is not None:
        parts.append(f"Our model says {per_ten(xg)} shots like that are goals.")
    assist = facts.get("assist")
    if assist and assist != who:
        parts.append(f"{assist} played the pass that made it.")
    parts.append(_why(f))
    return " ".join(parts)


def score_words(a: int, b: int) -> str:
    return f"{words(a) if a else 'nil'} {words(b) if b else 'nil'}"


def spoken_story(summary: dict[str, Any], moments: dict[str, Any], names: dict[str, str]) -> str:
    """A calm, clear spoken version of the match story."""
    t, sc, ps = summary["teams"], summary["score"], summary["possession"]
    h, a, hs, as_ = t["home"]["name"], t["away"]["name"], sc["home"], sc["away"]
    event = speak_years(f"{summary['competition']} {summary['season']}")
    where = f" in the {summary['stage']} of the {event}" if summary.get("stage") else f" in the {event}"
    first = (f"{h} and {a} drew{where}, {words(hs)} all." if hs == as_ else
             f"{(h if hs > as_ else a)} beat {(a if hs > as_ else h)}{where}, {score_words(max(hs, as_), min(hs, as_))}.")
    out = [first]
    if sc["shootout"]:
        sh = sc["shootout"]
        w, l = (h, a) if sh["home"] > sh["away"] else (a, h)
        out.append(f"{w} won it {score_words(max(sh['home'], sh['away']), min(sh['home'], sh['away']))} on penalties after extra time.")
    lead = (h, round(ps["home"] * 100)) if ps["home"] >= ps["away"] else (a, round(ps["away"] * 100))
    xg = {s: summary["stats"][s]["xg_model"] if summary["stats"][s]["xg_model"] is not None else summary["stats"][s]["xg_statsbomb"] for s in ("home", "away")}
    better = h if xg["home"] >= xg["away"] else a
    out.append(f"{lead[0]} had more of the ball, {words(lead[1])} percent, and {better} {'also ' if better == lead[0] else ''}created the better chances.")
    goals = []
    for m in moments["moments"]:
        if m["is_goal"]:
            who = names.get(m["player"], m["player"]) if m["player"] else m["team_name"]
            goals.append(f"{who} in the {ordinal(m['minute'] + 1)} minute" + (", from the spot" if m["is_penalty"] else ""))
    if goals:
        out.append("The goals came from " + ", ".join(goals[:-1]) + (", and " if len(goals) > 1 else "") + goals[-1] + ".")
    return " ".join(out)
