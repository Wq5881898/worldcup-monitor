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
    summary_curl_file: str
    detail_curl_file: str
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


def _load_text_file(path: str) -> str:
    if not path:
        return ""
    fp = Path(path)
    if not fp.exists():
        return ""
    return fp.read_text(encoding="utf-8").strip()


def load_match_config(path: str) -> MatchConfig:
    config_path = Path(path)
    raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
    base_dir = config_path.resolve().parent
    qmonitor_path = str(raw.get("qmonitor_config_path") or "")
    q_token, q_chat_ids = _load_qmonitor_settings(qmonitor_path)
    env_chat_ids = _chat_ids_from_value(os.getenv("TELEGRAM_CHAT_IDS"))
    summary_curl_file = str(raw.get("summary_curl_file") or "")
    detail_curl_file = str(raw.get("detail_curl_file") or "")
    summary_file_path = str((base_dir / summary_curl_file).resolve()) if summary_curl_file else ""
    detail_file_path = str((base_dir / detail_curl_file).resolve()) if detail_curl_file else ""

    token = str(raw.get("telegram_token") or os.getenv("TELEGRAM_TOKEN") or q_token or "")
    chat_ids = _chat_ids_from_value(raw.get("telegram_chat_ids")) or env_chat_ids or q_chat_ids
    summary_curl = str(raw.get("summary_curl") or "").strip() or _load_text_file(summary_file_path)
    detail_curl = str(raw.get("detail_curl") or "").strip() or _load_text_file(detail_file_path)

    return MatchConfig(
        name=str(raw.get("name") or "Match"),
        home_team=str(raw.get("home_team") or ""),
        away_team=str(raw.get("away_team") or ""),
        summary_curl=summary_curl,
        detail_curl=detail_curl,
        summary_curl_file=summary_curl_file,
        detail_curl_file=detail_curl_file,
        interval_seconds=float(raw.get("interval_seconds") or 1.0),
        ttl_seconds=int(raw.get("ttl_seconds") or 7200),
        telegram_token=token,
        telegram_chat_ids=chat_ids,
        qmonitor_config_path=qmonitor_path,
        log_path=str(raw.get("log_path") or "logs/goals.jsonl"),
        quiet=bool(raw.get("quiet", False)),
    )
