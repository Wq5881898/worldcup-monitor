import unittest

from worldcup_monitor.config import MatchConfig
from worldcup_monitor.flashscore import GoalEvent
from worldcup_monitor.monitor import WorldcupMonitor


class MonitorFormattingTests(unittest.TestCase):
    def test_format_goal_uses_inferred_team_names(self):
        cfg = MatchConfig(
            name="Match",
            home_team="",
            away_team="",
            summary_curl='curl "https://global.flashscore.ninja/130/x/feed/g_1_A1Jughll"',
            detail_curl="",
            summary_curl_file="",
            detail_curl_file="",
            interval_seconds=1.0,
            ttl_seconds=7200,
            telegram_token="",
            telegram_chat_ids=[],
            qmonitor_config_path="",
            log_path="logs/goals.jsonl",
            quiet=False,
        )
        monitor = WorldcupMonitor(cfg)
        monitor.state.team_names.update({"1": "USA", "2": "Bosnia & Herzegovina"})

        message = monitor.format_goal(
            GoalEvent(
                event_id="goal1",
                minute="45'",
                player="Balogun F.",
                home_score="1",
                away_score="0",
                team_side="1",
                text="",
            )
        )

        self.assertEqual(message, "GOAL 45' USA 1-0 Bosnia & Herzegovina\nBalogun F.")


if __name__ == "__main__":
    unittest.main()
