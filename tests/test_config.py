import json
import tempfile
import unittest
from pathlib import Path

from worldcup_monitor.config import load_match_config
from worldcup_monitor.monitor import WorldcupMonitor


class ConfigTests(unittest.TestCase):
    def test_loads_summary_curl_from_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "summary.curl").write_text(
                'curl ^"https://global.flashscore.ninja/130/x/feed/g_1_A1Jughll^" ^\n'
                '  -H ^"Referer: https://www.flashscoreusa.com/^" ^\n'
                '  -H ^"x-fsign: SW9D1eZo^"',
                encoding="utf-8",
            )
            (root / "match.local.json").write_text(
                json.dumps(
                    {
                        "name": "USA vs Bosnia",
                        "home_team": "USA",
                        "away_team": "Bosnia",
                        "summary_curl": "",
                        "summary_curl_file": "summary.curl",
                        "detail_curl": "",
                        "telegram_token": "",
                        "telegram_chat_ids": [],
                    }
                ),
                encoding="utf-8",
            )

            cfg = load_match_config(str(root / "match.local.json"))
            monitor = WorldcupMonitor(cfg)

            self.assertIn("g_1_A1Jughll", cfg.summary_curl)
            self.assertEqual(monitor.detail_req.url, "https://global.flashscore.ninja/130/x/feed/df_sui_1_A1Jughll")


if __name__ == "__main__":
    unittest.main()
