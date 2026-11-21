from collections import Counter
import json
from pathlib import Path
import unittest
from urllib.parse import urlparse

PUBLIC = Path(__file__).resolve().parents[1] / "public"


class ActivityPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guides = {row["id"]: row for row in json.loads(
            (PUBLIC / "guides.json").read_text(encoding="utf-8"))}
        cls.positions = json.loads((PUBLIC / "guide-positions.json").read_text(encoding="utf-8"))

    def test_all_guides_can_be_placed_with_recorded_precision(self):
        self.assertTrue(self.positions.keys() <= self.guides.keys())
        self.assertTrue(all(
            all(isinstance(entry.get(axis), (int, float)) for axis in ("x", "y"))
            for key, guide in self.guides.items()
            for entry in [self.positions.get(key, guide)]
        ))
        self.assertEqual(Counter(row["precision"] for row in self.positions.values()),
                         {"map-marker": 44, "mission-marker": 5, "landmark": 1})

    def test_each_bank_has_a_distinct_pin_and_gameside_source(self):
        branches = [row for key, row in self.positions.items()
                    if key.startswith(("guide-job-", "guide-vault-"))]
        self.assertEqual(len(branches), 22)
        self.assertEqual(len({(row["x"], row["y"]) for row in branches}), 22)
        for row in self.positions.values():
            self.assertTrue(0 < row["x"] < 1 and 0 < row["y"] < 1)
            self.assertTrue(row["evidenceNote"])
            self.assertEqual(urlparse(row["locationSource"]).scheme, "https")
            self.assertEqual(urlparse(row["sourceImage"]).hostname, "www.powerpyx.com")
            self.assertRegex(row["sourceImageSha256"], r"^[0-9a-f]{64}$")
            x, y = row["sourceMarkerPixel"]
            self.assertTrue(0 < x < 1920 and 0 < y < 1080)
            self.assertLessEqual(row["markerAlignment"]["p90ImagePixels"], 3)


if __name__ == "__main__":
    unittest.main()
