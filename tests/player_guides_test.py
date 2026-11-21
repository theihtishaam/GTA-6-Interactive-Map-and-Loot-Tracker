"""Integrity checks for published guides and their venue-level map links."""

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


PUBLIC = Path(__file__).resolve().parents[1] / "public"


class PlayerGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guides = json.loads((PUBLIC / "guides.json").read_text(encoding="utf-8"))
        cls.positions = json.loads((PUBLIC / "guide-positions.json").read_text(encoding="utf-8"))
        cls.landmarks = {
            item["id"]: item
            for item in json.loads((PUBLIC / "landmarks.json").read_text(encoding="utf-8"))
        }

    def test_guides_have_unique_ids_and_player_evidence(self):
        ids = [guide["id"] for guide in self.guides]
        self.assertEqual(len(ids), len(set(ids)))
        for guide in self.guides:
            with self.subTest(guide=guide["id"]):
                self.assertTrue(all(guide[key] for key in ("title", "region", "details", "steps")))
                self.assertEqual(urlsplit(guide["source"]).scheme, "https")
                self.assertEqual(guide["confidence"], "guide")

    def test_venue_positions_have_named_map_sources(self):
        for guide in self.guides:
            with self.subTest(guide=guide["id"]):
                if guide["precision"] == "area":
                    self.assertEqual((guide["x"], guide["y"]), (None, None))
                    self.assertNotIn("landmarkId", guide)
                    continue
                self.assertEqual(guide["precision"], "venue")
                marker = self.landmarks[guide["landmarkId"]]
                self.assertEqual(guide["landmark"], marker["title"])
                self.assertEqual(guide["locationSource"], marker["source"])
                for axis in ("x", "y"):
                    self.assertEqual(guide[axis], marker[axis])
                    self.assertLessEqual(0, guide[axis])
                    self.assertLessEqual(guide[axis], 1)

    def test_known_branches_remain_distinct(self):
        bank_ids = {
            item["id"] for item in self.guides
            if item["id"].startswith(("guide-job-", "guide-vault-"))
        }
        self.assertEqual(len(bank_ids), 22)
        self.assertEqual(sum(item["id"].startswith("guide-loan-") for item in self.guides), 7)
        self.assertIn("guide-vault-ocean-lombank-high", bank_ids)
        self.assertIn("guide-vault-ocean-lombank-medium", bank_ids)

    def test_registered_game_markers_have_auditable_positions(self):
        ids = {r["id"] for r in self.guides}
        self.assertTrue(self.positions.keys() <= ids)
        pinned_branches = {}
        for entry_id, point in self.positions.items():
            with self.subTest(guide=entry_id):
                self.assertTrue(0 <= point["x"] <= 1 and 0 <= point["y"] <= 1)
                self.assertEqual(urlsplit(point["locationSource"]).scheme, "https")
                self.assertTrue(point.get("evidenceNote"))
                self.assertIn(point["precision"], {"map-marker", "mission-marker", "landmark"})
                self.assertEqual(urlsplit(point["sourceImage"]).scheme, "https")
                self.assertEqual(len(point["sourceMarkerPixel"]), 2)
                alignment = point["markerAlignment"]
                self.assertGreater(alignment.get("heldOutMatches", alignment.get("inliers", 0)), 0)
                self.assertGreaterEqual(alignment["p90ImagePixels"], 0)
                if entry_id.startswith(("guide-job-", "guide-vault-", "guide-loan-")):
                    pinned_branches[entry_id] = (point["x"], point["y"])
        self.assertEqual(len(pinned_branches), 29)
        self.assertEqual(len(set(pinned_branches.values())), 29)

    def test_known_mission_and_venue_marker_meanings(self):
        for name in ("duffel-bag", "kingpin-watch", "kingpin-trophy", "kenton-dives", "yasmani-tips"):
            self.assertEqual(self.positions["guide-" + name]["precision"], "mission-marker")
        self.assertEqual(self.positions["guide-marquise-card"]["precision"], "landmark")
        for axis in ("x", "y"):
            self.assertEqual(self.positions["guide-kingpin-watch"][axis],
                             self.positions["guide-kingpin-trophy"][axis])


if __name__ == "__main__":
    unittest.main()
