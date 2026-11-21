"""Integrity checks for the manually reviewed, offline mission catalogue."""

from collections import Counter
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

PUBLIC = Path(__file__).resolve().parents[1] / "public"


class MissionCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.missions = json.loads((PUBLIC / "missions.json").read_text(encoding="utf8"))
        cls.by_id = {row["id"]: row for row in cls.missions}
        cls.guides = json.loads((PUBLIC / "guide-positions.json").read_text(encoding="utf8"))

    def test_chapter_roster_and_overlapping_contact_strands(self):
        self.assertEqual(len(self.by_id), len(self.missions))
        self.assertEqual(len(self.missions), 176)
        chapters = [row["chapter"] for row in self.missions]
        self.assertEqual(chapters, sorted(chapters))
        self.assertEqual(Counter(chapters), {0:1, 1:38, 2:31, 3:52, 4:44, 5:10})
        self.assertEqual(self.missions[0]["title"], "Prologue")
        self.assertEqual(self.by_id["mission-help-kirk-find-mr-mangrove"]["chapter"], 2)
        self.assertEqual(self.by_id["mission-help-kirk-find-mr-mangrove"]["strandStartChapter"], 1)
        self.assertEqual(self.by_id["mission-thrillbillies"]["strand"], "Billy")
        self.assertEqual({row["chapter"] for row in self.missions if row["title"] == "Pay Abe’s Fee"}, {4, 5})

    def test_records_have_legible_objectives_and_attributed_coverage(self):
        for row in self.missions:
            with self.subTest(row=row["title"]):
                self.assertRegex(row["id"], r"^mission-[a-z0-9-]+$")
                self.assertIn(row["kind"], {"story", "optional", "stranger", "side"})
                self.assertIn(row["coverage"], {"walkthrough", "reference"})
                self.assertTrue(row["steps"])
                self.assertTrue(all(isinstance(s,str) and 8 <= len(s) <= 210 for s in row["steps"]))
                self.assertEqual(urlsplit(row["source"]).scheme, "https")
                self.assertTrue(row["sourceLabel"])
                self.assertIsNone(row.get("x"))
                self.assertIsNone(row.get("y"))
        self.assertEqual(self.by_id["mission-rafas-kidnapping"]["coverage"], "reference")
        self.assertEqual(self.by_id["mission-taking-liberties"]["coverage"], "walkthrough")
        self.assertIn("BuckMe", self.by_id["mission-save-for-the-future"]["steps"][0])

    def test_starts_have_specific_evidence_and_shared_guides_identify_the_same_mission(self):
        for row in self.missions:
            if row.get("startMode") in ("remote", "automatic"):
                self.assertNotIn("startImage", row)
            if row.get("startImage"):
                self.assertEqual(urlsplit(row["startImage"]).hostname, "www.powerpyx.com")
            if row.get("guideId"):
                anchor = self.guides[row["guideId"]]
                self.assertEqual(anchor["precision"], "mission-marker")
                self.assertEqual(anchor["locationSource"], row["source"])
        self.assertEqual(self.by_id["mission-crosstown-traffic"]["actionLabel"], "Meet Raul (Lucia) / Meet Karim (Jason)")
        self.assertNotIn("startVenue", self.by_id["mission-send-money-to-lorena"])


if __name__ == "__main__":
    unittest.main()
