import unittest
import os
import tempfile
import shutil
from bosses import get_boss_encounters, get_live_world_events, CANONICAL_BOSS_ENCOUNTERS


class TestBossesAndWorldEvents(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_boss_encounters_empty(self):
        res = get_boss_encounters(saves_dir=self.temp_dir)
        self.assertIn("encounters", res)
        self.assertEqual(len(res["encounters"]), len(CANONICAL_BOSS_ENCOUNTERS))
        self.assertEqual(res["summary"]["discovered_arenas"], 0)
        self.assertTrue(all(not b["world_discovered"] for b in res["encounters"]))

    def test_boss_encounters_discovery(self):
        save_path = os.path.join(self.temp_dir, "World_Bosses.sav")
        # Simulate save data with Dragon Arena and Kalphite Queen Arena discovered
        dummy_content = (
            b"HeaderData...BP_InteractablePlayerTeleporter_IntoDragonArena..."
            b"BP_PROTOTYPE_InteractablePlayerTeleporter_KalphiteQueenArena"
        )
        with open(save_path, "wb") as f:
            f.write(dummy_content)

        res = get_boss_encounters(saves_dir=self.temp_dir)
        self.assertEqual(res["summary"]["discovered_arenas"], 2)

        dragon = next(b for b in res["encounters"] if "Dragon" in b["name"])
        self.assertTrue(dragon["world_discovered"])

        kq = next(b for b in res["encounters"] if "Kalphite" in b["name"])
        self.assertTrue(kq["world_discovered"])

        titan = next(b for b in res["encounters"] if "Titan" in b["name"])
        self.assertFalse(titan["world_discovered"])

    def test_live_world_events_parsing(self):
        log_path = os.path.join(self.temp_dir, "RSDragonwilds.log")
        dummy_log = (
            "[2026.10.10-18.55.03:742][192]LogWorldEventAIWaveSpawning: BP_BaseRaidEvent_BM_2_C_2146931300: Spawning wave\n"
            "[2026.10.10-18.55.04:709][221]LogWorldEventAIWaveSpawning: BP_BaseRaidEvent_BM_2_C_2146931300: AI Wave Spawn Complete\n"
            "[2026.10.10-07.24.10:745][820]LogNet: Join request: /Game/Maps/Server/L_ServerStartup?p=abc?c?Name=Replay?SplitscreenCount=1\n"
            "[2026.10.10-09.58.55:106][195]EvadeAttack: Verbose: [DedicatedServer] TryPerformAttack() : BP_AI_VaultMinibossMelee_Character_C starting attack on authority against player with id 1\n"
            "[2026.10.10-12.00.00:000][100]LogChests: [DedicatedServer] SetRespawnTimer() : Chest \"Chest_01\" set to respawn +08:00:00.000 from now\n"
        )
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(dummy_log)

        events = get_live_world_events(log_path=log_path)
        self.assertEqual(len(events), 5)
        # Most recent first
        self.assertEqual(events[0]["type"], "Chest Looted")
        self.assertEqual(events[1]["type"], "Miniboss Combat")
        self.assertEqual(events[2]["type"], "Player Joined")
        self.assertEqual(events[3]["type"], "World Raid")
        self.assertEqual(events[4]["type"], "World Raid")

        # Timestamp epoch and ISO verification
        for ev in events:
            self.assertIn("epoch", ev)
            self.assertIn("iso", ev)
            self.assertGreater(ev["epoch"], 0.0)
            self.assertTrue(ev["iso"].startswith("2026-10-10"))


if __name__ == "__main__":
    unittest.main()
