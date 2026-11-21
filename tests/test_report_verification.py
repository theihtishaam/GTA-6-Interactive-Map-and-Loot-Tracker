"""Conservative gameplay evidence review using synthetic, offline records."""

from copy import deepcopy
import unittest

from report_verification import review_reports

A = "https://guides.sample.test/articles/royal-sun?utm_source=example"
B = "https://players.example.net/post/13"
TITLE = "GTA VI Royal Sun card found"
BODY_A = "I collected it from a green shelf by the stage after the chapter event finished."
BODY_B = "The collectible is still there when the event ends. Check the shelves next to the stage."


def report(key, url=A, title=TITLE, details=BODY_A, **more):
    row = {
        "id": key, "category": "collectible", "title": title, "details": details,
        "x": .31, "y": .42, "confidence": "area", "landmarkId": "fictional-venue",
        "region": "Synthetic Harbor", "source": url, "sourceName": "Example guide",
    }
    return {**row, **more}


def grid(key, url=A, details=BODY_A, x=.31, y=.42, **more):
    return report(key, url, details=details, x=x, y=y, landmarkId=None,
                  confidence="reported", **more)


def statuses(rows):
    return [row["verification"]["status"] for row in rows]


class EvidenceReviewTests(unittest.TestCase):
    def test_independent_specific_activity_at_a_catalogue_venue(self):
        raw = [report("a"), report("b", B, details=BODY_B, sourceName="Example community", x=None, y=None)]
        expected = deepcopy(raw)
        reviewed = review_reports(raw)
        self.assertEqual(statuses(reviewed), ["corroborated", "corroborated"])
        self.assertEqual((reviewed[0]["x"], reviewed[0]["y"], reviewed[0]["confidence"]), (.31, .42, "area"))
        self.assertIsNone(reviewed[1]["x"])
        self.assertIn("approximate", reviewed[0]["verification"]["reason"])
        self.assertEqual(reviewed[0]["verification"]["sources"], [
            {"name": "Example guide", "url": A},
            {"name": "Example community", "url": B},
        ])
        self.assertEqual(raw, expected)
        self.assertTrue(all(result is not original for result, original in zip(reviewed, raw)))

    def test_nearby_game_grid_with_a_distinctive_subject(self):
        rows = [grid("a"), grid("b", B, details=BODY_B, x=.311, y=.4204)]
        reviewed = review_reports(rows)
        self.assertEqual(statuses(reviewed), ["corroborated", "corroborated"])
        self.assertIn("grid positions", reviewed[0]["verification"]["reason"])

    def test_disagreement_hides_coordinates_and_corrected_raw_evidence_recovers(self):
        raw = [grid("a"), grid("b", B, details=BODY_B, x=.46)]
        before = deepcopy(raw)
        reviewed = review_reports(raw)
        self.assertEqual(statuses(reviewed), ["review", "review"])
        for entry in reviewed:
            self.assertEqual((entry["x"], entry["y"]), (None, None))
            self.assertIn("disagree", entry["verification"]["reason"])
            self.assertEqual(len(entry["verification"]["sources"]), 2)
        self.assertEqual(raw, before)
        raw[1]["x"] = .311
        corrected = review_reports(raw)
        self.assertEqual(statuses(corrected), ["corroborated", "corroborated"])
        self.assertEqual([row["x"] for row in corrected], [.31, .311])

    def test_reported_retraction_or_change_is_a_review_not_a_proven_bug(self):
        for details in (
            "I posted the wrong coordinates and withdraw my report. The original story was mine.",
            "This location no longer spawns the card after the latest game update.",
            "It was patched. I can confirm what the previous article said.",
        ):
            with self.subTest(details=details):
                first = report("a")
                second = report("b", B, details=details)
                reviewed = review_reports([first, second])
                self.assertEqual(statuses(reviewed), ["review", "review"])
                self.assertEqual((reviewed[0]["x"], reviewed[1]["y"]), (None, None))
                self.assertNotIn("confirmed bug", reviewed[1]["verification"]["reason"].lower())
        negated = report("other", B, details="It was not patched. I played the chapter and collected the card at the stage today.")
        self.assertEqual(statuses(review_reports([report("a"), negated])), ["corroborated", "corroborated"])
        query = report("other", B, title="Does the Royal Sun card no longer spawn?",
                       details="Could someone tell me if they can see the card in the game?")
        self.assertEqual(statuses(review_reports([report("a"), query])), ["single-source", "single-source"])

    def test_no_corroboration_from_same_publisher_reposts_or_shared_primary_evidence(self):
        first = report("a")
        candidates = [
            report("b", "https://community.sample.test/post/13", details=BODY_B),
            report("b", B),
            report("b", B, details=BODY_A + " Additional wording from the feed."),
            report("b", B, details=f"{BODY_B} See https://guides.sample.test/articles/royal-sun."),
            report("b", B, details=f"According to Example guide, the scene is a chapter-end reward. {BODY_B}"),
            report("b", B, details=f"Reposted from another community. {BODY_B}"),
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertEqual(statuses(review_reports([first, candidate])), ["single-source", "single-source"])
        primary = "https://images.example.org/map/control.jpg"
        rows = [report("a", locationSource=primary), report("b", B, details=BODY_B, locationSource=primary)]
        self.assertEqual(statuses(review_reports(rows)), ["single-source", "single-source"])
        rows = [first, report("b", B, details="Reposted from another community. It was patched.")]
        self.assertEqual(statuses(review_reports(rows)), ["single-source", "review"])

    def test_distinct_objects_variants_venues_and_broad_claims_remain_separate(self):
        candidates = [
            report("b", B, title="GTA VI Royal Sun poster found", details=BODY_B),
            report("b", B, title="GTA VI Royal Sun card found", category="reward", details=BODY_B),
            report("b", B, details=BODY_B, landmarkId="another-venue"),
            report("b", B, title="GTA VI All Royal Sun card locations", details=BODY_B),
            report("b", B, title="Does the GTA VI Royal Sun card spawn?", details="I haven't found one."),
            report("b", B, details="Map point"),
            report("b", B, details="The fictional harbor is a scenic town with an impressive theater district."),
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertEqual(statuses(review_reports([report("a"), candidate])),
                                 ["single-source", "single-source"])
        self.assertEqual(statuses(review_reports([
            report("a", title=TITLE + " #2"), report("b", B, title=TITLE + " #3", details=BODY_B),
        ])), ["single-source", "single-source"])

    def test_unresolved_approximate_and_ambiguous_grid_positions_stay_single_source(self):
        rows = [
            grid("a"),
            grid("b", B, details=BODY_B, x=.32),
            report("c", "https://forum.example.org/post/5", details=BODY_B, landmarkId=None),
        ]
        self.assertEqual(statuses(review_reports(rows)), ["single-source"] * 3)
        rows = [report("a", title="GTA VI bounty found", category="bounty"),
                report("b", B, title="GTA VI bounty found", category="bounty", details=BODY_B)]
        self.assertEqual(statuses(review_reports(rows)), ["single-source"] * 2)

    def test_invalid_url_never_emitted_and_retained_excerpt_precedes_display(self):
        retained = report("a", url="javascript:alert(1)",
                          verificationExcerpt="I retract this report. The display excerpt omitted the correction.")
        result, = review_reports([retained])
        self.assertEqual(result["verification"]["status"], "review")
        self.assertEqual(result["verification"]["sources"], [])
        self.assertIsNone(result["x"])
        self.assertEqual(retained["x"], .31)


if __name__ == "__main__":
    unittest.main()
