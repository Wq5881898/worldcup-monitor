from __future__ import annotations

from dataclasses import dataclass


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
    blocks: list[list[tuple[str, str]]] = []
    for block in raw.split("¬~"):
        block = block.strip()
        if not block:
            continue
        pairs: list[tuple[str, str]] = []
        for part in block.split("¬"):
            if "÷" not in part:
                continue
            key, value = part.split("÷", 1)
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


def latest_score(goals: list[GoalEvent]) -> tuple[str, str] | None:
    for goal in reversed(goals):
        if goal.home_score and goal.away_score:
            return goal.home_score, goal.away_score
    return None


def looks_finished(raw: str) -> bool:
    text = raw.lower()
    needles = ("full time", "finished", "after pen.", "match finished")
    return any(needle in text for needle in needles)
