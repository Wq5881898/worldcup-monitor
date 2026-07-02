import unittest

from worldcup_monitor.flashscore import detail_version, infer_team_names, latest_score, parse_goals, parse_summary


SUMMARY = (
    "CA÷b16df8150f99fd37a0b9038182a99453¬"
    "CD÷eb32766343f643f6dac0bcb3d8364509¬"
    "CE÷5f0023a9bd8a8ebf88ec5237beda15e6¬"
    "CF÷0ff1a7461431b7f9bb49fb774d0e9338¬"
    "A1÷52a59b52e7deade8e4437c8a91918dea¬~"
)

DETAIL = (
    "AC÷1st Half¬IG÷1¬IH÷0¬~"
    "III÷nyLBv6zg¬IA÷1¬IB÷45'¬IE÷3¬INX÷1¬IOX÷0¬"
    "IF÷Balogun F.¬IU÷/player/balgun-folarin/rVZLmUsU/¬"
    "ICT÷Goal! Folarin Balogun (USA) pounced on a loose ball.¬"
    "IK÷Goal¬IM÷rVZLmUsU¬~"
    "MIT÷REF¬MIV÷Claus R.¬~"
    "A1÷eb32766343f643f6dac0bcb3d8364509¬~"
)

DETAIL_WITH_DOUBLE_TILDE_A1 = (
    "AC÷1st Half¬IG÷0¬IH÷0¬~"
    "TVT÷FOX¬TVB÷¬~~A1÷3d5e0e13de4f4c463143d232fab8bc17¬~"
)

DETAIL_TWO_GOALS = (
    "III÷h2HRzOZH¬IA÷1¬IB÷45'¬IE÷3¬INX÷1¬IOX÷0¬IF÷Balogun F.¬IK÷Goal¬~"
    "III÷8KtVVEbC¬IA÷1¬IB÷82'¬IE÷3¬INX÷2¬IOX÷0¬IF÷Tillman M.¬IK÷Goal¬~"
    "A1÷c9a783ed0a4d0ac52c7b2b213ecff40a¬~"
)


class FlashscoreParserTests(unittest.TestCase):
    def test_summary_cd(self):
        summary = parse_summary(SUMMARY)
        self.assertEqual(summary["CD"], "eb32766343f643f6dac0bcb3d8364509")
        self.assertEqual(summary["CF"], "0ff1a7461431b7f9bb49fb774d0e9338")

    def test_detail_goals_and_version(self):
        self.assertEqual(detail_version(DETAIL), "eb32766343f643f6dac0bcb3d8364509")
        goals = parse_goals(DETAIL)
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].event_id, "nyLBv6zg")
        self.assertEqual(goals[0].minute, "45'")
        self.assertEqual(goals[0].player, "Balogun F.")
        self.assertEqual((goals[0].home_score, goals[0].away_score), ("1", "0"))

    def test_detail_version_handles_double_tilde_prefix(self):
        self.assertEqual(detail_version(DETAIL_WITH_DOUBLE_TILDE_A1), "3d5e0e13de4f4c463143d232fab8bc17")

    def test_latest_score_uses_last_goal(self):
        goals = parse_goals(DETAIL_TWO_GOALS)
        self.assertEqual(len(goals), 2)
        self.assertEqual(latest_score(goals), ("2", "0"))

    def test_infers_team_names_from_event_text(self):
        raw = (
            "III÷h2HRzOZH¬IA÷1¬IB÷45'¬IF÷Balogun F.¬"
            "ICT÷Goal! Folarin Balogun (USA) scores.¬IK÷Goal¬~"
            "III÷K6SSXRAG¬IA÷2¬IB÷51'¬IF÷Gigovic A.¬"
            "ICT÷Armin Gigovic is replaced by Esmir Bajraktarevic (Bosnia & Herzegovina).¬IK÷Substitution - Out¬~"
            "A1÷abc¬~"
        )

        self.assertEqual(infer_team_names(raw), {"1": "USA", "2": "Bosnia & Herzegovina"})


if __name__ == "__main__":
    unittest.main()
