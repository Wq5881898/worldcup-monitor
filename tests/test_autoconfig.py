import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worldcup_monitor.autoconfig import (
    build_summary_curl,
    configure_query_match,
    parse_encoded_matches,
    parse_match_page_info,
    parse_tournament_candidates,
)


MATCH_HTML = """
<html><head><title>Mexico v England 06/07/2026 | Soccer - Flashscore</title></head>
<body>
<script>
window.environment = {"event_id_c":"bc27lzfo","config":{"feed_sign":"SW9D1eZo"}};
</script>
</body></html>
"""

TOURNAMENT_HTML = """
<html><body>
<a href="/game/soccer/england-j9N9ZNFA/mexico-O6iHcNkd/">Mexico - England</a>
<a href="/game/soccer/portugal-WvJrjFVN/spain-bLyo6mco/">Spain - Portugal</a>
</body></html>
"""

ENCODED_HTML = """
<script>
data: `SA÷1¬~ZA÷WORLD: World Championship - Play Offs¬~AA÷bc27lzfo¬PX÷O6iHcNkd¬AE÷Mexico¬WU÷mexico¬PY÷j9N9ZNFA¬AF÷England¬WV÷england¬~AA÷A1Jughll¬PX÷fuitL4CF¬AE÷USA¬WU÷usa¬PY÷fqe7WYTr¬AF÷Bosnia & Herzegovina¬WV÷bosnia-herzegovina¬~`
</script>
"""


class AutoConfigTests(unittest.TestCase):
    def test_parse_match_page_info(self):
        info = parse_match_page_info("https://www.flashscoreusa.com/game/soccer/england-j9N9ZNFA/mexico-O6iHcNkd/", MATCH_HTML)

        self.assertEqual(info.event_id, "bc27lzfo")
        self.assertEqual(info.feed_sign, "SW9D1eZo")
        self.assertEqual(info.home_team, "Mexico")
        self.assertEqual(info.away_team, "England")

    def test_parse_tournament_candidates(self):
        candidates = parse_tournament_candidates(TOURNAMENT_HTML)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].title, "Mexico - England")
        self.assertEqual(
            candidates[0].url,
            "https://www.flashscoreusa.com/game/soccer/england-j9N9ZNFA/mexico-O6iHcNkd/",
        )

    def test_build_summary_curl(self):
        curl = build_summary_curl("bc27lzfo", "SW9D1eZo")

        self.assertIn("g_1_bc27lzfo", curl)
        self.assertIn("x-fsign: SW9D1eZo", curl)
        self.assertNotIn("x-signature", curl)

    def test_parse_encoded_matches(self):
        matches = parse_encoded_matches(ENCODED_HTML)

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].event_id, "bc27lzfo")
        self.assertEqual(matches[0].home_team, "Mexico")
        self.assertEqual(matches[0].away_team, "England")
        self.assertEqual(
            matches[0].match_url,
            "https://www.flashscoreusa.com/game/soccer/england-j9N9ZNFA/mexico-O6iHcNkd/",
        )

    @patch("worldcup_monitor.autoconfig.http_get_text")
    def test_configure_query_match_updates_files(self, http_get_text):
        http_get_text.side_effect = [TOURNAMENT_HTML, ENCODED_HTML, "<html></html>", MATCH_HTML]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "match.local.json").write_text(
                json.dumps(
                    {
                        "name": "Match",
                        "home_team": "",
                        "away_team": "",
                        "summary_curl": "",
                        "summary_curl_file": "summary.curl",
                        "detail_curl": "",
                        "telegram_token": "",
                        "telegram_chat_ids": [],
                    }
                ),
                encoding="utf-8",
            )

            info = configure_query_match(str(root / "match.local.json"), "Mexico vs England")

            self.assertEqual(info.event_id, "bc27lzfo")
            summary_text = (root / "summary.curl").read_text(encoding="utf-8")
            self.assertIn("g_1_bc27lzfo", summary_text)
            saved = json.loads((root / "match.local.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["home_team"], "Mexico")
            self.assertEqual(saved["summary_curl_file"], "summary.curl")


if __name__ == "__main__":
    unittest.main()
