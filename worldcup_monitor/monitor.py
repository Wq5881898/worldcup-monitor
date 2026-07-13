from __future__ import annotations

import time
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from curl_cffi import requests as curl_requests

from .config import MatchConfig
from .curl_cmd import CurlRequest, derive_df_sui_request, parse_curl
from .flashscore import (
    GoalEvent,
    MatchSnapshot,
    detail_version,
    dict_from_pairs,
    infer_team_names,
    looks_finished,
    parse_blocks,
    parse_goals,
    parse_match_snapshot,
    parse_summary,
)
from .telegram import send_message


@dataclass
class MonitorState:
    last_cd: str = ""
    current_score: tuple[str, str] | None = None
    seen_goal_ids: set[str] = field(default_factory=set)
    started_at: float = field(default_factory=time.time)
    goals: list[GoalEvent] = field(default_factory=list)
    team_names: dict[str, str] = field(default_factory=dict)
    snapshot: MatchSnapshot | None = None
    startup_notified: bool = False


@dataclass(frozen=True)
class ScoreAlert:
    minute: str
    player: str
    home_score: str
    away_score: str
    event_id: str = ""


class WorldcupMonitor:
    def __init__(self, config: MatchConfig) -> None:
        self.config = config
        self.summary_req = parse_curl(config.summary_curl)
        self.detail_req = parse_curl(config.detail_curl) if config.detail_curl.strip() else derive_df_sui_request(self.summary_req)
        self.state = MonitorState()

    def fetch(self, req: CurlRequest) -> tuple[int, str]:
        resp = curl_requests.request(
            method=req.method,
            url=req.url,
            params=req.params or None,
            headers=req.headers or None,
            cookies=req.cookies or None,
            json=req.json_data,
            data=None if req.json_data is not None else (req.data or None),
            impersonate="chrome120",
            timeout=20,
        )
        return resp.status_code, resp.text

    def initialize(self) -> None:
        code, summary_text = self.fetch(self.summary_req)
        if code not in (200, 304, 204):
            raise RuntimeError(f"summary initialization failed: HTTP {code}")
        summary = parse_summary(summary_text)
        self.state.last_cd = summary.get("CD", "")

        code, detail_text = self.fetch(self.detail_req)
        if code != 200:
            raise RuntimeError(f"detail initialization failed: HTTP {code}")
        goals = parse_goals(detail_text)
        self.state.goals = goals
        self.state.seen_goal_ids = {goal.event_id for goal in goals if goal.event_id}
        self.state.team_names.update(infer_team_names(detail_text))
        self.state.snapshot = parse_match_snapshot(detail_text)
        if not self.state.last_cd:
            self.state.last_cd = detail_version(detail_text)
        official_home, official_away = self.official_score_from_detail(detail_text)
        self.state.current_score = (official_home, official_away)
        self.state.snapshot = MatchSnapshot(
            phase=self.state.snapshot.phase,
            home_score=official_home,
            away_score=official_away,
            minute=self.state.snapshot.minute,
        )
        self.send_startup_message()

    def team_label(self, side: str, fallback: str) -> str:
        default = "home_team" if side == "1" else "away_team"
        return self.state.team_names.get(side) or fallback or default

    def startup_message(self) -> str:
        snapshot = self.state.snapshot or MatchSnapshot("unknown", "0", "0", "")
        home_team = self.team_label("1", self.config.home_team)
        away_team = self.team_label("2", self.config.away_team)
        return (
            f"MONITOR STARTED\n"
            f"{home_team} {snapshot.home_score}-{snapshot.away_score} {away_team}\n"
            f"Phase: {snapshot.phase}\n"
            f"CD: {self.state.last_cd or '-'}"
        )

    def send_startup_message(self) -> None:
        if self.state.startup_notified:
            return
        message = self.startup_message()
        print(message, flush=True)
        send_message(self.config.telegram_token, self.config.telegram_chat_ids, message)
        self.state.startup_notified = True

    def send_repeated_goal_message(self, message: str) -> None:
        count = max(1, self.config.goal_repeat_count)
        interval = max(0.0, self.config.goal_repeat_interval_seconds)
        send_message(self.config.telegram_token, self.config.telegram_chat_ids, message)
        if count <= 1:
            return

        def worker() -> None:
            for _ in range(count - 1):
                if interval > 0:
                    time.sleep(interval)
                send_message(self.config.telegram_token, self.config.telegram_chat_ids, message)

        thread = threading.Thread(target=worker, name="goal-telegram-repeat", daemon=False)
        thread.start()

    def format_goal(self, goal: GoalEvent) -> str:
        home = goal.home_score or "?"
        away = goal.away_score or "?"
        minute = goal.minute or "?"
        player = goal.player or "Unknown"
        home_team = self.team_label("1", self.config.home_team)
        away_team = self.team_label("2", self.config.away_team)
        return f"GOAL {minute} {home_team} {home}-{away} {away_team}\n{player}"

    def format_score_alert(self, alert: ScoreAlert) -> str:
        minute = alert.minute or "?"
        home_team = self.team_label("1", self.config.home_team)
        away_team = self.team_label("2", self.config.away_team)
        base = f"SCORE {minute} {home_team} {alert.home_score}-{alert.away_score} {away_team}"
        if alert.player:
            return f"{base}\n{alert.player}"
        return base

    def log_goal(self, goal: GoalEvent, message: str) -> None:
        path = Path(self.config.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "match": self.config.name,
            "event_id": goal.event_id,
            "minute": goal.minute,
            "player": goal.player,
            "home_team": self.state.team_names.get("1") or self.config.home_team,
            "away_team": self.state.team_names.get("2") or self.config.away_team,
            "home_score": goal.home_score,
            "away_score": goal.away_score,
            "message": message,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def log_score_alert(self, alert: ScoreAlert, message: str) -> None:
        path = Path(self.config.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "match": self.config.name,
            "event_id": alert.event_id,
            "minute": alert.minute,
            "player": alert.player,
            "home_team": self.state.team_names.get("1") or self.config.home_team,
            "away_team": self.state.team_names.get("2") or self.config.away_team,
            "home_score": alert.home_score,
            "away_score": alert.away_score,
            "message": message,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def official_score_from_detail(self, detail_text: str) -> tuple[str, str]:
        for pairs in parse_blocks(detail_text):
            block = dict_from_pairs(pairs)
            if "AC" in block:
                return block.get("IG", "0") or "0", block.get("IH", "0") or "0"
        snapshot = parse_match_snapshot(detail_text)
        return snapshot.home_score, snapshot.away_score

    def handle_cd_change(self, cd: str) -> list[ScoreAlert]:
        detail_text = ""
        detail_code = 0
        detail_a1 = ""
        for attempt in range(4):
            detail_code, detail_text = self.fetch(self.detail_req)
            detail_a1 = detail_version(detail_text) if detail_text else ""
            if detail_code == 200 and detail_a1 == cd:
                break
            if attempt < 3:
                time.sleep(0.25)
        else:
            if detail_code != 200:
                raise RuntimeError(f"detail fetch failed HTTP {detail_code} for CD {cd}")
            print(f"warning: detail A1 {detail_a1 or '-'} did not match summary CD {cd}; processing latest detail", flush=True)

        alerts: list[ScoreAlert] = []
        self.state.team_names.update(infer_team_names(detail_text))
        self.state.snapshot = parse_match_snapshot(detail_text)
        parsed_goals = parse_goals(detail_text)
        new_goal_for_score: GoalEvent | None = None
        for goal in parsed_goals:
            if goal.event_id in self.state.seen_goal_ids:
                continue
            self.state.seen_goal_ids.add(goal.event_id)
            self.state.goals.append(goal)
        official_score = self.official_score_from_detail(detail_text)
        self.state.snapshot = MatchSnapshot(
            phase=self.state.snapshot.phase,
            home_score=official_score[0],
            away_score=official_score[1],
            minute=self.state.snapshot.minute,
        )
        for goal in reversed(parsed_goals):
            if goal.home_score == official_score[0] and goal.away_score == official_score[1]:
                new_goal_for_score = goal
                break
        if self.state.current_score != official_score:
            alerts.append(
                ScoreAlert(
                    minute=self.state.snapshot.minute,
                    player=(new_goal_for_score.player if new_goal_for_score else ""),
                    home_score=official_score[0],
                    away_score=official_score[1],
                    event_id=(new_goal_for_score.event_id if new_goal_for_score else ""),
                )
            )
            self.state.current_score = official_score

        self.state.last_cd = cd
        if looks_finished(detail_text):
            raise StopIteration("match finished")
        return alerts

    def run(self) -> int:
        self.initialize()
        if not self.config.quiet:
            score = self.state.current_score or ("0", "0")
            print(f"started {self.config.name}: CD={self.state.last_cd or '-'} score={score[0]}-{score[1]}", flush=True)

        while True:
            if time.time() - self.state.started_at >= self.config.ttl_seconds:
                print("stopped: ttl expired", flush=True)
                return 0

            try:
                code, summary_text = self.fetch(self.summary_req)
                if code in (204, 304):
                    if not self.config.quiet:
                        print(f"heartbeat HTTP {code}", flush=True)
                    time.sleep(self.config.interval_seconds)
                    continue
                if code != 200:
                    print(f"summary failed HTTP {code}", flush=True)
                    time.sleep(self.config.interval_seconds)
                    continue

                summary = parse_summary(summary_text)
                cd = summary.get("CD", "")
                if not cd or cd == self.state.last_cd:
                    if not self.config.quiet:
                        print(f"heartbeat HTTP 200 CD={cd or '-'}", flush=True)
                    if looks_finished(summary_text):
                        print("stopped: match finished", flush=True)
                        return 0
                    time.sleep(self.config.interval_seconds)
                    continue

                if not self.config.quiet:
                    print(f"CD changed {self.state.last_cd or '-'} -> {cd}", flush=True)
                alerts = self.handle_cd_change(cd)
                for alert in alerts:
                    message = self.format_score_alert(alert)
                    print(message, flush=True)
                    self.log_score_alert(alert, message)
                    self.send_repeated_goal_message(message)
            except StopIteration as exc:
                print(f"stopped: {exc}", flush=True)
                return 0
            except KeyboardInterrupt:
                print("stopped: interrupted", flush=True)
                return 130
            except Exception as exc:
                print(f"error: {exc}", flush=True)

            time.sleep(self.config.interval_seconds)
