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


def parse_goals(raw: str) -> list[GoalEvent]:
    goals: list[GoalEvent] = []
    for pairs in parse_blocks(raw):
        if "Goal" not in values(pairs, "IK"):
            continue
        event_id = first_value(pairs, "III")
        minute = first_value(pairs, "IB")
        player = first_value(pairs, "IF")
        home_score = first_value(pairs, "INX")
        away_score = first_value(pairs, "IOX")
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
        text = first_value(pairs, "ICT")
        if not text:
            continue
        for candidate in re.findall(r"\(([^()]+)\)", text):
            candidate = candidate.strip()
            if candidate and not candidate.isdigit():
                teams[side] = candidate
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
