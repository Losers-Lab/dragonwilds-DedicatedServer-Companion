import unittest
import os
import tempfile
import shutil
from campaign import get_campaign_status, find_newest_save


class TestCampaignMilestones(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_campaign_empty_dir(self):
        res = get_campaign_status(saves_dir=self.temp_dir)
        self.assertIn("summary", res)
        self.assertEqual(res["summary"]["shrines_unlocked"], 0)
        self.assertEqual(res["summary"]["spells_unlocked"], 0)
        self.assertEqual(res["summary"]["buildings_unlocked"], 0)
        self.assertEqual(res["summary"]["recipes_unlocked"], 0)
        self.assertEqual(res["summary"]["bosses_and_elites"], 0)
        self.assertEqual(res["summary"]["player_gravestones"], 0)
        self.assertEqual(res["summary"]["player_bedrolls"], 0)
        self.assertEqual(res["summary"]["active_world_save"], "None")
        self.assertEqual(len(res["death_markers"]), 0)
        self.assertEqual(len(res["camps"]), 0)

    def test_campaign_mock_save(self):
        save_path = os.path.join(self.temp_dir, "World_Progress.sav")
        mock_content = (
            b"HeaderData...Prefix..."
            b'{"BuildingsUnlocked": ["B1", "B2", "B3"], '
            b'"RecipesUnlocked": ["R1", "R2"], '
            b'"ShrinesUnlocked": ["Shrine_01"], '
            b'"SpellsUnlocked": ["Spell_A", "Spell_B"], '
            b'"PlayerHooksTriggered": ["Hook_1"], '
            b'"KilledOnceAIs": ["Boss_Velgar", "Boss_Titan"]}'
            b"...BP_PlayerGraveyard_8Slots_C_UAID_BM_001..."
            b"...BP_PlayerGraveyard_8Slots_C_UAID_FH_002..."
            b"...BP_BaseBuilding_BedRoll_C...BP_BaseBuilding_BedRoll_C..."
            b"...BP_NPC_RestlessGhost_Quest...BP_NPC_Quest_CandleLight2..."
        )
        with open(save_path, "wb") as f:
            f.write(mock_content)

        res = get_campaign_status(saves_dir=self.temp_dir)
        s = res["summary"]
        self.assertEqual(s["buildings_unlocked"], 3)
        self.assertEqual(s["recipes_unlocked"], 2)
        self.assertEqual(s["shrines_unlocked"], 1)
        self.assertEqual(s["spells_unlocked"], 2)
        self.assertEqual(s["story_hooks"], 1)
        self.assertEqual(s["bosses_and_elites"], 2)
        self.assertEqual(s["player_gravestones"], 2)
        self.assertEqual(s["player_bedrolls"], 2)

        # Gravestones check
        self.assertEqual(len(res["death_markers"]), 2)
        self.assertEqual(res["death_markers"][0]["zone"], "Brynmoore")
        self.assertEqual(res["death_markers"][1]["zone"], "Fellhollow")
        self.assertIn("map_coords", res["death_markers"][0])
        self.assertIn("source", res["death_markers"][0])
        self.assertGreaterEqual(res["death_markers"][0]["map_coords"]["x"], 20.0)
        self.assertLessEqual(res["death_markers"][0]["map_coords"]["x"], 980.0)

        # Camps check
        self.assertEqual(len(res["camps"]), 2)
        self.assertIn("map_coords", res["camps"][0])
        self.assertGreaterEqual(res["camps"][0]["map_coords"]["x"], 20.0)
        self.assertLessEqual(res["camps"][0]["map_coords"]["x"], 980.0)

        # Quests check
        self.assertEqual(len(res["quests"]), 2)
        quest_names = [q["name"] for q in res["quests"]]
        self.assertIn("The Restless Ghost", quest_names)
        self.assertIn("Candle in the Dark", quest_names)

    def test_campaign_caching(self):
        save_path = os.path.join(self.temp_dir, "World_Cache.sav")
        with open(save_path, "wb") as f:
            f.write(b'{"KilledOnceAIs": ["Boss_1"]}...BP_PlayerGraveyard_8Slots_C_UAID_001')

        res1 = get_campaign_status(saves_dir=self.temp_dir)
        res2 = get_campaign_status(saves_dir=self.temp_dir)
        self.assertIs(res1, res2)

    def test_campaign_corrupted_json(self):
        save_path = os.path.join(self.temp_dir, "World_Corrupt.sav")
        with open(save_path, "wb") as f:
            f.write(b'"KilledOnceAIs" : {INVALID_JSON_CORRUPTED}')

        res = get_campaign_status(saves_dir=self.temp_dir)
        self.assertIn("summary", res)
        self.assertEqual(res["summary"]["bosses_and_elites"], 0)


if __name__ == "__main__":
    unittest.main()
