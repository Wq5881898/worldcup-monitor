from __future__ import annotations

import re
from dataclasses import dataclass


def normalize_protocol_text(raw: str) -> str:
    # Some responses decode the Flashscore delimiters as Latin-1 bytes in a str.
    return raw.replace("\xac", "\u00ac").replace("\xf7", "\u00f7")


@dataclass(frozen=True)
class GoalEvent:
    event_id: str
    minute: str
    player: str
    home_score: str
    away_score: str
    team_side: str
    text: str


@dataclass(frozen=True)
class MatchSnapshot:
    phase: str
    home_score: str
    away_score: str
    minute: str


def parse_blocks(raw: str) -> list[list[tuple[str, str]]]:
    raw = normalize_protocol_text(raw)
    blocks: list[list[tuple[str, str]]] = []
    pair_sep = "\u00ac"
    kv_sep = "\u00f7"
    for block in raw.split(f"{pair_sep}~"):
        block = block.strip()
        if not block:
            continue
        pairs: list[tuple[str, str]] = []
        for part in block.split(pair_sep):
            if kv_sep not in part:
                continue
            key, value = part.split(kv_sep, 1)
            key = key.lstrip("~")
            pairs.append((key, value))
        if pairs:
            blocks.append(pairs)
    return blocks


def first_value(pairs: list[tuple[str, str]], key: str, default: str = "") -> str:
    for k, value in pairs:
        if k == key:
            return value
    return default


def values(pairs: list[tuple[str, str]], key: str) -> list[str]:
    return [value for k, value in pairs if k == key]


def dict_from_pairs(pairs: list[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in pairs:
        out[key] = value
    return out


SCORING_EVENT_TYPES = {"Goal", "Penalty", "Own Goal", "Own goal"}
NON_SCORING_EVENT_TYPES = {"Goal Disallowed", "Missed Penalty", "Penalty Awarded"}


def parse_summary(raw: str) -> dict[str, str]:
    blocks = parse_blocks(raw)
    if not blocks:
        return {}
    return {key: value for key, value in blocks[0]}


def detail_version(raw: str) -> str:
    version = ""
    for block in parse_blocks(raw):
        for key, value in block:
            if key == "A1":
                version = value
    return version


def parse_match_snapshot(raw: str) -> MatchSnapshot:
    phase = ""
    home_score = "0"
    away_score = "0"
    minute = ""

    for pairs in parse_blocks(raw):
        block = dict_from_pairs(pairs)
        if "AC" in block:
            phase = block.get("AC", phase)
            home_score = block.get("IG", home_score) or home_score
            away_score = block.get("IH", away_score) or away_score
        if "IB" in block:
            minute = block.get("IB", minute)
        if "INX" in block and "IOX" in block:
            home_score = block.get("INX") or home_score
            away_score = block.get("IOX") or away_score

    return MatchSnapshot(
        phase=phase or "unknown",
        home_score=home_score,
        away_score=away_score,
        minute=minute,
    )


def parse_goals(raw: str) -> list[GoalEvent]:
    goals: list[GoalEvent] = []
    for pairs in parse_blocks(raw):
        event_types = set(values(pairs, "IK"))
        if not event_types.intersection(SCORING_EVENT_TYPES):
            continue
        if event_types.issubset(NON_SCORING_EVENT_TYPES):
            continue
        home_score = first_value(pairs, "INX")
        away_score = first_value(pairs, "IOX")
        if not home_score or not away_score:
            continue
        event_id = first_value(pairs, "III")
        minute = first_value(pairs, "IB")
        player = first_value(pairs, "IF")
        team_side = first_value(pairs, "IA")
        text = first_value(pairs, "ICT")
        fallback_id = "|".join([minute, player, home_score, away_score, text])
        goals.append(
            GoalEvent(
                event_id=event_id or fallback_id,
                minute=minute,
                player=player,
                home_score=home_score,
                away_score=away_score,
                team_side=team_side,
                text=text,
            )
        )
    return goals


def infer_team_names(raw: str) -> dict[str, str]:
    teams: dict[str, str] = {}
    for pairs in parse_blocks(raw):
        side = first_value(pairs, "IA")
        if side not in ("1", "2") or side in teams:
            continue
        for text in values(pairs, "ICT"):
            if not text:
                continue
            for candidate in re.findall(r"\(([^()]+)\)", text):
                candidate = candidate.strip()
                if candidate and not candidate.isdigit():
                    teams[side] = candidate
                    break
            if side in teams:
                break
    return teams


def latest_score(goals: list[GoalEvent]) -> tuple[str, str] | None:
    for goal in reversed(goals):
        if goal.home_score and goal.away_score:
            return goal.home_score, goal.away_score
    return None


def looks_finished(raw: str) -> bool:
    text = raw.lower()
    needles = ("full time", "finished", "after pen.", "match finished")
    return any(needle in text for needle in needles)
