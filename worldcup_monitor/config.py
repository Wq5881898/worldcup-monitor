from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MatchConfig:
    name: str
    home_team: str
    away_team: str
    summary_curl: str
    detail_curl: str
    interval_seconds: float
    ttl_seconds: int
    telegram_token: str
    telegram_chat_ids: list[str]
    qmonitor_config_path: str
    log_path: str
    quiet: bool


def _chat_ids_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _load_qmonitor_settings(path: str) -> tuple[str, list[str]]:
    if not path:
        return "", []
    fp = Path(path)
    if not fp.exists():
        return "", []
    try:
        raw = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return "", []
    settings = raw.get("settings") or {}
    return str(settings.get("telegram_token") or ""), _chat_ids_from_value(settings.get("telegram_chat_ids"))


def load_match_config(path: str) -> MatchConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    qmonitor_path = str(raw.get("qmonitor_config_path") or "")
    q_token, q_chat_ids = _load_qmonitor_settings(qmonitor_path)
    env_chat_ids = _chat_ids_from_value(os.getenv("TELEGRAM_CHAT_IDS"))

    token = str(raw.get("telegram_token") or os.getenv("TELEGRAM_TOKEN") or q_token or "")
    chat_ids = _chat_ids_from_value(raw.get("telegram_chat_ids")) or env_chat_ids or q_chat_ids

    return MatchConfig(
        name=str(raw.get("name") or "Match"),
        home_team=str(raw.get("home_team") or "Home"),
        away_team=str(raw.get("away_team") or "Away"),
        summary_curl=str(raw.get("summary_curl") or ""),
        detail_curl=str(raw.get("detail_curl") or ""),
        interval_seconds=float(raw.get("interval_seconds") or 1.0),
        ttl_seconds=int(raw.get("ttl_seconds") or 7200),
        telegram_token=token,
        telegram_chat_ids=chat_ids,
        qmonitor_config_path=qmonitor_path,
        log_path=str(raw.get("log_path") or "logs/goals.jsonl"),
        quiet=bool(raw.get("quiet", False)),
    )
