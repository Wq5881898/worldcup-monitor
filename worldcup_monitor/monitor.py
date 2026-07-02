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
from .flashscore import GoalEvent, MatchSnapshot, detail_version, infer_team_names, latest_score, looks_finished, parse_goals, parse_match_snapshot, parse_summary
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
        self.state.current_score = latest_score(goals)
        self.state.team_names.update(infer_team_names(detail_text))
        self.state.snapshot = parse_match_snapshot(detail_text)
        if not self.state.last_cd:
            self.state.last_cd = detail_version(detail_text)
        self.send_startup_message()

    def team_label(self, side: str, fallback: str) -> str:
        return self.state.team_names.get(side) or fallback or f"Team {side}"

    def startup_message(self) -> str:
        snapshot = self.state.snapshot or MatchSnapshot("unknown", "0", "0", "")
        home_team = self.team_label("1", self.config.home_team)
        away_team = self.team_label("2", self.config.away_team)
        minute = snapshot.minute or "unknown"
        return (
            f"MONITOR STARTED\n"
            f"{home_team} {snapshot.home_score}-{snapshot.away_score} {away_team}\n"
            f"Phase: {snapshot.phase}\n"
            f"Minute: {minute}\n"
            f"CD: {self.state.last_cd or '-'}"
        )

    def send_startup_message(self) -> None:
        if self.state.startup_notified:
            return
        message = self.startup_message()
        print(message)
        send_message(self.config.telegram_token, self.config.telegram_chat_ids, message)
        self.state.startup_notified = True

    def send_repeated_goal_message(self, message: str) -> None:
        count = max(1, self.config.goal_repeat_count)
        interval = max(0.0, self.config.goal_repeat_interval_seconds)

        def worker() -> None:
            for i in range(count):
                send_message(self.config.telegram_token, self.config.telegram_chat_ids, message)
                if i < count - 1 and interval > 0:
                    time.sleep(interval)

        thread = threading.Thread(target=worker, name="goal-telegram-repeat", daemon=True)
        thread.start()

    def format_goal(self, goal: GoalEvent) -> str:
        home = goal.home_score or "?"
        away = goal.away_score or "?"
        minute = goal.minute or "?"
        player = goal.player or "Unknown"
        home_team = self.team_label("1", self.config.home_team)
        away_team = self.team_label("2", self.config.away_team)
        return f"GOAL {minute} {home_team} {home}-{away} {away_team}\n{player}"

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

    def handle_cd_change(self, cd: str) -> list[GoalEvent]:
        detail_text = ""
        for attempt in range(4):
            code, detail_text = self.fetch(self.detail_req)
            if code == 200 and detail_version(detail_text) == cd:
                break
            if attempt < 3:
                time.sleep(0.25)
        else:
            raise RuntimeError(f"detail version did not match CD {cd}")

        new_goals: list[GoalEvent] = []
        self.state.team_names.update(infer_team_names(detail_text))
        self.state.snapshot = parse_match_snapshot(detail_text)
        for goal in parse_goals(detail_text):
            if goal.event_id in self.state.seen_goal_ids:
                continue
            self.state.seen_goal_ids.add(goal.event_id)
            self.state.goals.append(goal)
            if goal.home_score and goal.away_score:
                self.state.current_score = (goal.home_score, goal.away_score)
            new_goals.append(goal)

        self.state.last_cd = cd
        if looks_finished(detail_text):
            raise StopIteration("match finished")
        return new_goals

    def run(self) -> int:
        self.initialize()
        if not self.config.quiet:
            score = self.state.current_score or ("0", "0")
            print(f"started {self.config.name}: CD={self.state.last_cd or '-'} score={score[0]}-{score[1]}")

        while True:
            if time.time() - self.state.started_at >= self.config.ttl_seconds:
                print("stopped: ttl expired")
                return 0

            try:
                code, summary_text = self.fetch(self.summary_req)
                if code in (204, 304):
                    if not self.config.quiet:
                        print(f"heartbeat HTTP {code}")
                    time.sleep(self.config.interval_seconds)
                    continue
                if code != 200:
                    print(f"summary failed HTTP {code}")
                    time.sleep(self.config.interval_seconds)
                    continue

                summary = parse_summary(summary_text)
                cd = summary.get("CD", "")
                if not cd or cd == self.state.last_cd:
                    if not self.config.quiet:
                        print(f"heartbeat HTTP 200 CD={cd or '-'}")
                    if looks_finished(summary_text):
                        print("stopped: match finished")
                        return 0
                    time.sleep(self.config.interval_seconds)
                    continue

                if not self.config.quiet:
                    print(f"CD changed {self.state.last_cd or '-'} -> {cd}")
                new_goals = self.handle_cd_change(cd)
                for goal in new_goals:
                    message = self.format_goal(goal)
                    print(message)
                    self.log_goal(goal, message)
                    self.send_repeated_goal_message(message)
            except StopIteration as exc:
                print(f"stopped: {exc}")
                return 0
            except KeyboardInterrupt:
                print("stopped: interrupted")
                return 130
            except Exception as exc:
                print(f"error: {exc}")

            time.sleep(self.config.interval_seconds)
