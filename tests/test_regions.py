import unittest
from worldreader import format_region_name, get_canonical_regions, CANONICAL_MAP_REGIONS


class TestRegionResolution(unittest.TestCase):
    def test_weather_mappings(self):
        self.assertEqual(format_region_name("base"), "Central Ashenfall (Overworld)")
        self.assertEqual(format_region_name("dowdun"), "Dowdun Reach")
        self.assertEqual(format_region_name("sands"), "Umbral Sands")
        self.assertEqual(format_region_name("Scorned Wilderness"), "Scorned Wilderness")

    def test_canonical_id_lookups(self):
        self.assertEqual(format_region_name("MapRegionAlcarridOasis"), "Al Kharid Oasis")
        self.assertEqual(format_region_name("AlcarridOasis"), "Al Kharid Oasis")
        self.assertEqual(format_region_name("MapRegionWItchWillow"), "Witch Willow Mire")
        self.assertEqual(format_region_name("MapRegionLake"), "Mirror Lake")
        self.assertEqual(format_region_name("MapRegionDragonsRun"), "Dragon's Run")
        self.assertEqual(format_region_name("MapRegionHopesFall"), "Hope's Fall")

    def test_fallback_formatting(self):
        self.assertEqual(format_region_name("custom_volcano_biome"), "Custom Volcano Biome")
        self.assertEqual(format_region_name("FrostbitePeak"), "Frostbite Peak")

    def test_edge_cases_and_type_safety(self):
        self.assertEqual(format_region_name(None), "Unknown Region")
        self.assertEqual(format_region_name(""), "Unknown Region")
        self.assertEqual(format_region_name("   "), "Unknown Region")
        self.assertEqual(format_region_name("___"), "Unknown Region")
        self.assertEqual(format_region_name(12345), "Unknown Region")
        self.assertEqual(format_region_name(["invalid"]), "Unknown Region")

    def test_canonical_regions_immutability(self):
        regions_copy1 = get_canonical_regions()
        regions_copy2 = get_canonical_regions()
        self.assertEqual(len(regions_copy1), 31)
        # Verify modifying copy does not mutate original or second copy
        regions_copy1[0]["name"] = "MUTATED"
        self.assertNotEqual(regions_copy2[0]["name"], "MUTATED")
        self.assertEqual(CANONICAL_MAP_REGIONS[0]["name"], "Al Kharid Oasis")

    def test_canonical_regions_coordinates_and_lore(self):
        regions = get_canonical_regions()
        for r in regions:
            self.assertIn("x", r)
            self.assertIn("y", r)
            self.assertIn("lore", r)
            self.assertIsInstance(r["x"], int)
            self.assertIsInstance(r["y"], int)
            self.assertGreaterEqual(r["x"], 0)
            self.assertLessEqual(r["x"], 1000)
            self.assertGreaterEqual(r["y"], 0)
            self.assertLessEqual(r["y"], 1000)
            self.assertTrue(len(r["lore"]) > 10)


if __name__ == "__main__":
    unittest.main()
