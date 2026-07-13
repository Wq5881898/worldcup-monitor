import unittest
from dataclasses import replace
from unittest.mock import MagicMock, patch

from worldcup_monitor.config import MatchConfig
from worldcup_monitor.flashscore import GoalEvent, MatchSnapshot
from worldcup_monitor.monitor import ScoreAlert, WorldcupMonitor


def make_config() -> MatchConfig:
    return MatchConfig(
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


class MonitorFormattingTests(unittest.TestCase):
    def test_format_goal_uses_inferred_team_names(self):
        monitor = WorldcupMonitor(make_config())
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

    def test_format_score_alert_uses_current_score(self):
        monitor = WorldcupMonitor(make_config())
        monitor.state.team_names.update({"1": "France", "2": "Morocco"})

        message = monitor.format_score_alert(
            ScoreAlert(
                minute="87'",
                player="",
                home_score="2",
                away_score="1",
            )
        )

        self.assertEqual(message, "SCORE 87' France 2-1 Morocco")

    def test_startup_message_contains_snapshot(self):
        monitor = WorldcupMonitor(make_config())
        monitor.state.team_names.update({"1": "USA", "2": "Bosnia & Herzegovina"})
        monitor.state.snapshot = MatchSnapshot("1st Half", "0", "0", "")
        monitor.state.last_cd = "abc"

        self.assertEqual(
            monitor.startup_message(),
            "MONITOR STARTED\nUSA 0-0 Bosnia & Herzegovina\nPhase: 1st Half\nCD: abc",
        )

    def test_startup_message_uses_home_away_fallback_labels(self):
        monitor = WorldcupMonitor(make_config())
        monitor.state.snapshot = MatchSnapshot("1st Half", "0", "0", "")
        monitor.state.last_cd = "abc"

        self.assertEqual(
            monitor.startup_message(),
            "MONITOR STARTED\nhome_team 0-0 away_team\nPhase: 1st Half\nCD: abc",
        )

    def test_initialize_uses_official_score_not_latest_goal_score(self):
        monitor = WorldcupMonitor(make_config())
        monitor.send_startup_message = MagicMock()
        responses = [
            (200, "CD÷summary-version¬~"),
            (
                200,
                "AC÷1st Half¬IG÷1¬IH÷0¬~"
                "III÷goal-1¬IA÷1¬IB÷45'¬IE÷3¬INX÷1¬IOX÷0¬IF÷Player A¬IK÷Goal¬~"
                "III÷goal-2¬IA÷2¬IB÷46'¬IE÷3¬INX÷1¬IOX÷1¬IF÷Player B¬IK÷Goal¬~"
                "A1÷detail-version¬~",
            ),
        ]
        monitor.fetch = MagicMock(side_effect=responses)

        monitor.initialize()

        self.assertEqual(monitor.state.last_cd, "summary-version")
        self.assertEqual(monitor.state.current_score, ("1", "0"))
        self.assertEqual(monitor.state.snapshot, MatchSnapshot("1st Half", "1", "0", "46'"))
        monitor.send_startup_message.assert_called_once()

    @patch("worldcup_monitor.monitor.threading.Thread")
    @patch("worldcup_monitor.monitor.send_message")
    def test_repeated_goal_message_sends_first_message_and_starts_background_thread(self, send_message, thread_cls):
        cfg = replace(make_config(), telegram_token="token", telegram_chat_ids=["1"])
        monitor = WorldcupMonitor(cfg)

        monitor.send_repeated_goal_message("GOAL")

        send_message.assert_called_once_with("token", ["1"], "GOAL")
        thread_cls.assert_called_once()
        self.assertEqual(thread_cls.call_args.kwargs["name"], "goal-telegram-repeat")
        self.assertFalse(thread_cls.call_args.kwargs["daemon"])
        thread_cls.return_value.start.assert_called_once()

    def test_cd_change_alerts_when_official_score_changes(self):
        monitor = WorldcupMonitor(make_config())
        monitor.state.current_score = ("1", "1")
        monitor.fetch = MagicMock(
            return_value=(
                200,
                "AC÷2nd Half¬IG÷2¬IH÷1¬~"
                "III÷goal-1¬IA÷1¬IB÷87'¬IE÷3¬INX÷2¬IOX÷1¬IF÷Mbappe K.¬IK÷Goal¬~"
                "A1÷new-version¬~",
            )
        )

        alerts = monitor.handle_cd_change("summary-version")

        self.assertEqual(
            alerts,
            [ScoreAlert(minute="87'", player="Mbappe K.", home_score="2", away_score="1", event_id="goal-1")],
        )
        self.assertEqual(monitor.state.current_score, ("2", "1"))

    def test_cd_change_alerts_when_official_score_reverts(self):
        monitor = WorldcupMonitor(make_config())
        monitor.state.current_score = ("2", "1")
        monitor.fetch = MagicMock(
            return_value=(
                200,
                "AC÷2nd Half¬IG÷1¬IH÷1¬~"
                "III÷goal-1¬IA÷1¬IB÷70'¬IE÷3¬INX÷2¬IOX÷1¬IF÷Mbappe K.¬IK÷Goal¬~"
                "A1÷new-version¬~",
            )
        )

        alerts = monitor.handle_cd_change("summary-version")

        self.assertEqual(
            alerts,
            [ScoreAlert(minute="70'", player="", home_score="1", away_score="1", event_id="")],
        )
        self.assertEqual(monitor.state.current_score, ("1", "1"))

    def test_cd_change_processes_latest_detail_when_a1_does_not_match(self):
        monitor = WorldcupMonitor(make_config())
        monitor.state.current_score = ("0", "0")
        monitor.fetch = MagicMock(
            return_value=(
                200,
                "AC÷2nd Half¬IG÷0¬IH÷1¬~"
                "III÷g1¬IA÷2¬IB÷70'¬IE÷10¬INX÷0¬IOX÷1¬IF÷Mbappe K.¬IK÷Penalty¬~"
                "A1÷different-detail-version¬~",
            )
        )

        alerts = monitor.handle_cd_change("summary-version")

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].player, "Mbappe K.")
        self.assertEqual(alerts[0].home_score, "0")
        self.assertEqual(alerts[0].away_score, "1")
        self.assertEqual(monitor.state.last_cd, "summary-version")
        self.assertEqual(monitor.fetch.call_count, 4)


if __name__ == "__main__":
    unittest.main()
