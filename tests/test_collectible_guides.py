"""Verify complete meditation coverage and its coordinate evidence."""

from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
GUIDE_URL = "https://www.powerpyx.com/gta-6-all-meditation-spot-locations/"


def read(file):
    return json.loads(file.read_text(encoding="utf-8-sig"))


class MeditationGuidesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read(PUBLIC / "collectible-guides.json")

    def test_complete_set_and_stable_ids(self):
        self.assertEqual(len(self.rows), 10)
        self.assertEqual([row["collectibleIndex"] for row in self.rows], list(range(1, 11)))
        self.assertEqual(sum(row["meditations"] for row in self.rows), 18)
        self.assertEqual({row["meditations"] for row in self.rows[1:-1]}, {2})
        self.assertEqual(len({row["id"] for row in self.rows}), 10)
        self.assertEqual(len({(row["x"], row["y"]) for row in self.rows}), 10)
        self.assertEqual(self.rows[-1]["id"], "guide-mount-kalaga-meditation")
        self.assertIn("Chapter 1 only", self.rows[0]["details"])
        self.assertIn("unconfirmed", self.rows[0]["details"])
        for row in self.rows:
            self.assertEqual(row["setSize"], 10)
            self.assertEqual(row["collectibleSet"], "Meditations")
            self.assertEqual(row["category"], "collectible")
            self.assertEqual(row["confidence"], "guide")
            self.assertEqual(row["source"], GUIDE_URL)
            self.assertGreaterEqual(len(row["steps"]), 2)
            self.assertTrue(all(0 <= row[axis] <= 1 for axis in ("x", "y")))

    def test_jasons_house_uses_the_named_venue(self):
        row = self.rows[0]
        landmark = next(place for place in read(PUBLIC / "landmarks.json") if place["id"] == row["landmarkId"])
        self.assertEqual(row["precision"], "venue")
        self.assertEqual(row["locationSource"], landmark["source"])
        self.assertEqual((row["x"], row["y"]), (landmark["x"], landmark["y"]))
        self.assertEqual(landmark["nameOrigin"], "game")
        self.assertNotIn("sourceMarkerPixel", row)

    def test_public_marker_provenance_is_distinct(self):
        self.assertEqual({row["precision"] for row in self.rows[1:]}, {"map-marker"})
        self.assertEqual(len({row["sourceImage"] for row in self.rows[1:]}), 9)
        root = ROOT / ".atlas" / "collectible-evidence"
        for row in self.rows[1:]:
            self.assertEqual(row["sourceImage"], row["locationSource"])
            url = urlsplit(row["sourceImage"])
            self.assertEqual((url.scheme, url.hostname), ("https", "www.powerpyx.com"))
            self.assertRegex(url.path, r"^/wp-content/uploads/gta-6-meditation-spot-[1-9]-1\.jpg$")
            self.assertRegex(row["sourceImageSha256"], r"^[0-9a-f]{64}$")
            x, y = row["sourceMarkerPixel"]
            self.assertTrue(0 <= x < 1920 and 0 <= y < 1080)
            self.assertGreater(row["registrationInliers"], 300)
            self.assertLessEqual(row["registrationP90Pixels"], 5.5)
            downloaded = root / Path(url.path).name
            if downloaded.is_file():
                self.assertEqual(sha256(downloaded.read_bytes()).hexdigest(), row["sourceImageSha256"])


if __name__ == "__main__":
    unittest.main()
