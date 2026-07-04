import unittest
from unittest.mock import MagicMock, patch

from worldcup_monitor.config import MatchConfig
from worldcup_monitor.flashscore import GoalEvent, MatchSnapshot
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
            goal_repeat_count=10,
            goal_repeat_interval_seconds=3.0,
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

    def test_startup_message_contains_snapshot(self):
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
            goal_repeat_count=10,
            goal_repeat_interval_seconds=3.0,
            qmonitor_config_path="",
            log_path="logs/goals.jsonl",
            quiet=False,
        )
        monitor = WorldcupMonitor(cfg)
        monitor.state.team_names.update({"1": "USA", "2": "Bosnia & Herzegovina"})
        monitor.state.snapshot = MatchSnapshot("1st Half", "0", "0", "")
        monitor.state.last_cd = "abc"

        self.assertEqual(
            monitor.startup_message(),
            "MONITOR STARTED\nUSA 0-0 Bosnia & Herzegovina\nPhase: 1st Half\nCD: abc",
        )

    def test_startup_message_uses_home_away_fallback_labels(self):
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
            goal_repeat_count=10,
            goal_repeat_interval_seconds=3.0,
            qmonitor_config_path="",
            log_path="logs/goals.jsonl",
            quiet=False,
        )
        monitor = WorldcupMonitor(cfg)
        monitor.state.snapshot = MatchSnapshot("1st Half", "0", "0", "")
        monitor.state.last_cd = "abc"

        self.assertEqual(
            monitor.startup_message(),
            "MONITOR STARTED\nhome_team 0-0 away_team\nPhase: 1st Half\nCD: abc",
        )

    @patch("worldcup_monitor.monitor.threading.Thread")
    @patch("worldcup_monitor.monitor.send_message")
    def test_repeated_goal_message_sends_first_message_and_starts_background_thread(self, send_message, thread_cls):
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
            telegram_token="token",
            telegram_chat_ids=["1"],
            goal_repeat_count=10,
            goal_repeat_interval_seconds=3.0,
            qmonitor_config_path="",
            log_path="logs/goals.jsonl",
            quiet=False,
        )
        monitor = WorldcupMonitor(cfg)

        monitor.send_repeated_goal_message("GOAL")

        send_message.assert_called_once_with("token", ["1"], "GOAL")
        thread_cls.assert_called_once()
        self.assertEqual(thread_cls.call_args.kwargs["name"], "goal-telegram-repeat")
        self.assertFalse(thread_cls.call_args.kwargs["daemon"])
        thread_cls.return_value.start.assert_called_once()

    def test_score_advance_skips_replayed_historical_goals(self):
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
            goal_repeat_count=10,
            goal_repeat_interval_seconds=3.0,
            qmonitor_config_path="",
            log_path="logs/goals.jsonl",
            quiet=False,
        )
        monitor = WorldcupMonitor(cfg)
        monitor.state.current_score = ("3", "0")

        self.assertFalse(
            monitor.is_score_advance(
                GoalEvent("new-id-1", "36'", "Oyarzabal M.", "1", "0", "1", "")
            )
        )
        self.assertFalse(
            monitor.is_score_advance(
                GoalEvent("new-id-2", "66'", "Porro P.", "2", "0", "1", "")
            )
        )
        self.assertFalse(
            monitor.is_score_advance(
                GoalEvent("new-id-3", "89'", "Oyarzabal M.", "3", "0", "1", "")
            )
        )
        self.assertTrue(
            monitor.is_score_advance(
                GoalEvent("new-id-4", "90+5'", "Player", "4", "0", "1", "")
            )
        )

    def test_cd_change_processes_latest_detail_when_a1_does_not_match(self):
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
            goal_repeat_count=10,
            goal_repeat_interval_seconds=3.0,
            qmonitor_config_path="",
            log_path="logs/goals.jsonl",
            quiet=False,
        )
        monitor = WorldcupMonitor(cfg)
        monitor.fetch = MagicMock(
            return_value=(
                200,
                "III÷g1¬IA÷2¬IB÷70'¬IE÷10¬INX÷0¬IOX÷1¬IF÷Mbappe K.¬IK÷Penalty¬~"
                "A1÷different-detail-version¬~",
            )
        )

        goals = monitor.handle_cd_change("summary-version")

        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].player, "Mbappe K.")
        self.assertEqual(monitor.state.last_cd, "summary-version")
        self.assertEqual(monitor.fetch.call_count, 4)


if __name__ == "__main__":
    unittest.main()
