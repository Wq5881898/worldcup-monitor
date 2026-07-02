import unittest
from unittest.mock import MagicMock, patch

from worldcup_monitor.cli import main


class CliTests(unittest.TestCase):
    @patch("worldcup_monitor.cli.WorldcupMonitor")
    @patch("worldcup_monitor.cli.load_match_config")
    @patch("worldcup_monitor.cli.Path")
    def test_run_defaults_to_match_json_when_no_local_config(self, path_cls, load_config, monitor_cls):
        path_cls.return_value.exists.return_value = False
        monitor_cls.return_value.run.return_value = 0

        result = main(["run"])

        self.assertEqual(result, 0)
        load_config.assert_called_once_with("match.json")

    @patch("worldcup_monitor.cli.WorldcupMonitor")
    @patch("worldcup_monitor.cli.load_match_config")
    @patch("worldcup_monitor.cli.Path")
    def test_run_defaults_to_match_local_json_when_present(self, path_cls, load_config, monitor_cls):
        path_cls.return_value.exists.return_value = True
        monitor_cls.return_value.run.return_value = 0

        result = main(["run"])

        self.assertEqual(result, 0)
        load_config.assert_called_once_with("match.local.json")

    @patch("worldcup_monitor.cli.WorldcupMonitor")
    @patch("worldcup_monitor.cli.load_match_config")
    def test_run_uses_explicit_config(self, load_config, monitor_cls):
        monitor_cls.return_value.run.return_value = 0

        result = main(["run", "--config", "custom.json"])

        self.assertEqual(result, 0)
        load_config.assert_called_once_with("custom.json")


if __name__ == "__main__":
    unittest.main()
