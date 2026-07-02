import unittest

from worldcup_monitor.curl_cmd import derive_df_sui_request, parse_curl


class CurlCmdTests(unittest.TestCase):
    def test_parse_copy_as_curl_cmd(self):
        raw = '''curl ^"https://global.flashscore.ninja/130/x/feed/g_1_A1Jughll^" ^
  -H ^"sec-ch-ua-platform: ^\\^"Windows^\\^"^" ^
  -H ^"x-signature: d25cf780e3e62d36dcae189b8b7bcc93^" ^
  -H ^"Referer: https://www.flashscoreusa.com/^" ^
  -H ^"User-Agent: Mozilla/5.0^" ^
  -H ^"x-fsign: SW9D1eZo^"'''

        req = parse_curl(raw)

        self.assertEqual(req.method, "GET")
        self.assertEqual(req.url, "https://global.flashscore.ninja/130/x/feed/g_1_A1Jughll")
        self.assertEqual(req.headers["x-fsign"], "SW9D1eZo")
        self.assertEqual(req.headers["x-signature"], "d25cf780e3e62d36dcae189b8b7bcc93")
        self.assertEqual(req.headers["sec-ch-ua-platform"], '"Windows"')

    def test_derive_df_sui_request_removes_summary_signature(self):
        req = parse_curl(
            'curl "https://global.flashscore.ninja/130/x/feed/g_1_A1Jughll" '
            '-H "x-signature: abc" -H "x-fsign: SW9D1eZo"'
        )

        detail = derive_df_sui_request(req)

        self.assertEqual(detail.url, "https://global.flashscore.ninja/130/x/feed/df_sui_1_A1Jughll")
        self.assertNotIn("x-signature", {key.lower(): value for key, value in detail.headers.items()})
        self.assertEqual(detail.headers["x-fsign"], "SW9D1eZo")


if __name__ == "__main__":
    unittest.main()
