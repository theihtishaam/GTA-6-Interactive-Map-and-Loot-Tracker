"""Offline source, filtering, provenance, and scheduler tests for Bounty Watch."""

from datetime import timedelta
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
import unittest
from urllib.error import URLError

from bounty_watch import (
    BOUNTY_SOURCES, bounty_report, discover_bounties, merge_bounty_reports, parse_search,
)
from discovery import LAUNCH, parse_feed
from server import Atlas, LocalServer, utcnow

PUBLISHED = (LAUNCH + timedelta(hours=1)).isoformat()
PRIMARY = "https://github.com/example/atlas/issues/9"
MIRROR = "https://bsky.app/profile/did:plc:example/post/item"
TITLE = "GTA VI bounty target captured near Synthetic Harbor"
BODY = ("I captured the bounty target at Synthetic Harbor after I found the wanted poster during chapter 2. "
        "The in-game mission log marked the target as delivered and Jason received the payout.")
LANDMARK = {
    "id": "synthetic-harbor", "title": "Synthetic Harbor", "category": "landmark",
    "region": "Synthetic Region", "x": 0.25, "y": 0.75,
}
GITHUB, BLUESKY = BOUNTY_SOURCES[:2]


class BountyFilterTests(unittest.TestCase):
    def test_eligible_claim_and_exact_duplicate_provenance(self):
        github = bounty_report(GITHUB, (TITLE, BODY, PRIMARY, PUBLISHED, {"+1": 8, "-1": 2}), [LANDMARK])
        bluesky = bounty_report(BLUESKY, (TITLE, BODY, MIRROR, PUBLISHED, None), [LANDMARK])
        self.assertEqual(github["category"], "bounty")
        self.assertEqual(github["watchStatus"], "source claim")
        self.assertEqual(github["x"], .25)
        self.assertEqual(github["communityVotes"]["up"], 8)
        self.assertNotIn("_extract", github)
        report, = merge_bounty_reports([], [github, bluesky, bluesky])
        self.assertEqual(report["source"], PRIMARY)
        self.assertEqual(report["relatedSources"], [{"name": BLUESKY.name, "platform": "Bluesky", "url": MIRROR}])

    def test_explicit_rejections(self):
        for title, excerpt in (
            ("Has anyone found a bounty in GTA VI?", "Has anyone found a bounty in chapter 2?"),
            ("GTA 6 bounty hunt guide", "Could Jason be the bounty target? Where is it?"),
            ("GTA VI bounty hunting", "No confirmed bounties in Jason's chapter 2."),
            ("GTA 6 bounty target captured", BODY + " This is actually GTA Online."),
            ("GTA 6 bounty target captured", BODY + " This is a FiveM mod."),
            ("GTA VI bug bounty payout", "The GTA 6 bug bounty paid $50,000."),
            ("GTA 6 bounties giveaway", "To claim the bounty reward, sign up for our real-world giveaway."),
            ("GTA 6 bounty target captured", "Leaked pre-release footage reportedly revealed a bounty target."),
            ("GTA 6 bounty payout", "If Rockstar adds a bounty mission, Jason would gain a cash reward."),
            ("GTA 6 bounty hunter guide", "Subscribe for more, I discuss a bounty here."),
        ):
            with self.subTest(title=title, excerpt=excerpt):
                self.assertIsNone(bounty_report(BLUESKY, (title, excerpt, MIRROR, PUBLISHED, None), []))
        self.assertIsNone(bounty_report(BLUESKY, (TITLE, BODY, MIRROR, "2026-11-18", None), []))

    def test_independent_health_and_manual_never_fetched(self):
        manual = {source.url for source in BOUNTY_SOURCES if source.kind == "manual"}
        contacted = set()

        def mock(url, **kwargs):
            contacted.add(url)
            self.assertNotIn("Authorization", kwargs.get("headers") or {})
            if "api.github.com" in url:
                return json.dumps({"items": [{"title": TITLE, "body": BODY, "created_at": PUBLISHED,
                                               "html_url": PRIMARY, "reactions": {"+1": 4, "-1": 1}}]}).encode()
            if "api.bsky.app" in url:
                return b'{"posts":[]}'
            raise URLError("dummy upstream value")

        sources, reports = discover_bounties([LANDMARK], mock)
        self.assertEqual(len(manual & contacted), 0)
        index = {source["platform"]: source for source in sources}
        self.assertEqual((index["GitHub"]["seen"], index["GitHub"]["matched"]), (1, 1))
        self.assertEqual(index["Bluesky"]["status"], "ok")
        self.assertEqual(index["Lemmy"]["status"], "error")
        self.assertEqual(index["Discord"]["status"], "manual")
        self.assertNotIn("dummy upstream value", str(sources))
        self.assertEqual(len(reports), 1)

    def test_real_adapter_shapes_offline(self):
        bsky = {"posts": [{"uri": "at://did:plc:example/app.bsky.feed.post/item",
                           "record": {"text": BODY, "createdAt": PUBLISHED}}]}
        self.assertEqual(parse_search(json.dumps(bsky), "bluesky")[0][2], MIRROR)
        lemmy = {"posts": [{"post": {"name": TITLE, "body": BODY, "ap_id": "https://lemmy.world/post/10",
                                     "published": PUBLISHED}}]}
        self.assertEqual(parse_search(json.dumps(lemmy), "lemmy")[0][0], TITLE)
        video = f'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
        <entry><title>{TITLE}</title><link href="https://www.youtube.com/watch?v=fictional"/>
        <published>{PUBLISHED}</published><media:group><media:description>{BODY}</media:description></media:group>
        </entry></feed>'''
        self.assertEqual(parse_feed(video.encode())[0][1], BODY)


class BountyApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = 0
        self.started = Event()
        self.release = Event()
        self.atlas = Atlas(self.root / "state.json", self.root, bounty_discovery=self.mock_scan)
        self.atlas.last_run = self.atlas.bounty_last_run = utcnow()
        self.atlas.next_run = self.atlas.bounty_next_run = utcnow() + timedelta(hours=24)
        self.server = LocalServer(self.atlas, 0)
        self.addCleanup(self.server.server_close)
        thread = Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        self.watcher = Thread(target=self.atlas.bounty_worker, daemon=True)
        self.watcher.start()
        self.addCleanup(self.stop_worker)

    def stop_worker(self):
        self.release.set()
        self.atlas.stop()
        self.watcher.join(2)

    def mock_scan(self, landmarks):
        self.calls += 1
        self.started.set()
        self.release.wait(2)
        sources = [source.health() for source in BOUNTY_SOURCES]
        row = bounty_report(GITHUB, (TITLE, BODY, PRIMARY, PUBLISHED, None), landmarks)
        return sources, [row, dict(row)]

    def request(self, method, path, body=None, origin=None):
        client = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {}
        if body is not None:
            headers = {"Content-Type": "application/json",
                       "Origin": origin or f"http://127.0.0.1:{self.server.server_port}"}
            body = json.dumps(body).encode()
        try:
            client.request(method, path, body, headers)
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()

    def wait_for_report(self, old_last=None):
        deadline = monotonic() + 2
        while monotonic() < deadline:
            current = self.request("GET", "/api/bounty/state")[1]
            if current["reports"] and current["lastRun"] != old_last:
                return current
            sleep(.025)
        self.fail("Bounty job never completed")

    def test_scoped_manual_run_and_persistent_independent_cadence(self):
        initial = self.request("GET", "/api/state")[1]
        self.assertEqual(self.request("POST", "/api/bounty/settings", {"interval": 12})[0], 200)
        self.assertEqual(self.request("POST", "/api/bounty/settings", {"interval": 10})[0], 400)
        self.assertEqual(self.request("POST", "/api/bounty/refresh", {}, origin="https://hidden.test")[0], 403)
        self.assertEqual(self.request("POST", "/api/bounty/refresh", {})[0], 202)
        self.assertTrue(self.started.wait(1))
        self.assertEqual(self.request("POST", "/api/bounty/refresh", {})[0], 202)
        self.release.set()
        watch = self.wait_for_report(initial["bounty"]["lastRun"])
        self.assertEqual(self.calls, 1)
        self.assertEqual(len(watch["reports"]), 1)
        current = self.request("GET", "/api/state")[1]
        self.assertEqual(current["lastRun"], initial["lastRun"])
        self.assertEqual(current["nextRun"], initial["nextRun"])
        self.assertEqual(self.request("POST", "/api/settings", {"interval": 12})[0], 200)
        self.assertEqual(self.request("POST", "/api/settings", {"interval": 6})[0], 200)
        loaded = Atlas(self.root / "state.json", self.root)
        self.assertEqual(loaded.interval, 6)
        self.assertEqual(loaded.bounty_interval, 12)
        self.assertEqual(loaded.bounty_next_run - loaded.bounty_last_run, timedelta(hours=12))
        self.assertEqual(len(loaded.bounty_reports), 1)

    def test_watch_schedule_runs_without_manual_request(self):
        with self.atlas.change:
            self.atlas.bounty_next_run = utcnow() - timedelta(seconds=1)
            self.atlas.change.notify_all()
        self.assertTrue(self.started.wait(1))
        self.release.set()
        self.wait_for_report()


if __name__ == "__main__":
    unittest.main()
