from collections import Counter
import json
import math
from pathlib import Path
import unittest

PUBLIC = Path(__file__).resolve().parents[1] / "public"


class MissionPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.missions = {row["id"]: row for row in json.loads(
            (PUBLIC / "missions.json").read_text(encoding="utf-8"))}
        cls.overlay = json.loads((PUBLIC / "mission-positions.json").read_text(encoding="utf-8"))

    def test_every_overlay_row_matches_source_and_geometry(self):
        self.assertTrue(self.overlay.keys() <= self.missions.keys())
        chapter_counts = Counter(self.missions[mission_id]["chapter"] for mission_id in self.overlay)
        self.assertEqual(chapter_counts, {1: 17, 2: 14, 3: 31, 4: 20})
        for mission_id, row in self.overlay.items():
            with self.subTest(mission=mission_id):
                mission = self.missions[mission_id]
                self.assertEqual(row["precision"], "mission-marker")
                self.assertEqual(row["sourceImage"], mission["startImage"])
                self.assertEqual(row["locationSource"], mission["source"])
                self.assertNotIn(mission.get("startMode"), {"automatic", "remote", "unmarked"})
                self.assertRegex(row["sourceImageSha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(len(row["sourceMarkerPixel"]), 2)
                self.assertTrue(all(type(value) is int and value > 0 for value in row["sourceMarkerPixel"]))
                self.assertTrue(all(math.isfinite(row[axis]) and 0 < row[axis] < 1 for axis in ("x", "y")))
                alignment = row["markerAlignment"]
                self.assertGreaterEqual(alignment["inliers"], 75)
                self.assertGreaterEqual(alignment["heldOutMatches"], 15)
                self.assertGreaterEqual(alignment["nearbyControls"], 4)
                self.assertLessEqual(alignment["p90ImagePixels"], 3)

    def test_ambiguous_cursors_and_phone_tasks_do_not_become_mission_pins(self):
        excluded = {
            "mission-attend-eddie-acostas-party",
            "mission-clock-out",
            "mission-crosstown-traffic",
            "mission-deposit-cash-into-buckme",
            "mission-don-gone",
            "mission-encrypted-hard-drive",
            "mission-home-sweet-home",
            "mission-painkiller-supplier",
            "mission-pay-abes-fee-ch4",
            "mission-rauls-next-job",
            "mission-send-money-to-lorena",
            "mission-steal-the-scooter",
            "mission-the-last-mile-passing-the-torch",
            "mission-yasmanis-jewelry-jobs",
        }
        self.assertTrue(excluded <= self.missions.keys())
        self.assertTrue(excluded.isdisjoint(self.overlay))

    def test_known_labeled_start_agrees_with_existing_activity_registration(self):
        guides = json.loads((PUBLIC / "guide-positions.json").read_text(encoding="utf-8"))
        for mission_id, guide_id in (
            ("mission-lab-fees", "guide-duffel-bag"),
            ("mission-hit-kingpin-bowling", "guide-kingpin-watch"),
            ("mission-thats-where-the-money-is", "guide-yasmani-tips"),
        ):
            a, b = self.overlay[mission_id], guides[guide_id]
            difference = math.hypot((a["x"] - b["x"]) * 3456, (a["y"] - b["y"]) * 4864)
            self.assertLess(difference, 3)


if __name__ == "__main__":
    unittest.main()
