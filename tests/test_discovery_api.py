"""Offline verification of source, provider and loopback API behavior."""

from datetime import timedelta
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
import unittest
from urllib.error import URLError

from discovery import LAUNCH, REVIEW_EMBARGO, SOURCES, discover, make_report, parse_feed
from providers import Provider, add_source_steps, configure, list_models
from report_verification import review_reports
from server import Atlas, LocalServer

PUBLISHED = LAUNCH.isoformat()
PUBLIC_LINK = "https://github.com/example/game/issues/123"
LANDMARK = {
    "id": "synthetic-harbor", "title": "Synthetic Harbor", "category": "landmark",
    "region": "Synthetic Region", "x": 0.25, "y": 0.75,
}
TITLE = "GTA VI gloves found near Synthetic Harbor"
EXCERPT = "Open the lockers behind the sign to find the gloves."


class DiscoveryTests(unittest.TestCase):
    def test_public_game_grid_becomes_reported_pin(self):
        def locate(body):
            return make_report(SOURCES[0],("GTA VI collectible found",body,PUBLIC_LINK,PUBLISHED,None),[])
        r=locate("Found one. ATLAS_GTA6_GRID=(-3328,768)")
        self.assertEqual((r["confidence"],r["x"],r["y"]),("reported",0.5,0.5))
        for body in ("Found one on GPS at 25.5, -80.2","ATLAS_GTA6_GRID=(99999,1234)",
                     "ATLAS_GTA6_GRID=(1,2) and ATLAS_GTA6_GRID=(3,4)"):
            self.assertIsNone(locate(body)["x"])

    def test_fixed_anonymous_sources_report_errors_independently(self):
        def fetcher(url, **kwargs):
            if "api.github.com" in url:
                self.assertNotIn("Authorization", kwargs["headers"])
                return json.dumps({"items": [{
                    "html_url": PUBLIC_LINK, "title": TITLE, "body": EXCERPT,
                    "created_at": PUBLISHED, "reactions": {"+1": 11, "-1": 2, "heart": 19},
                }]}).encode()
            if "gta6.how" in url:
                return f"""<feed xmlns="http://www.w3.org/2005/Atom">
                <entry><title>Hidden reward found</title><summary>Found in a crate.</summary>
                <published>{PUBLISHED}</published><link rel="self" href="https://example.org/self"/>
                <link href="https://example.org/trail?utm_source=feed"/></entry></feed>""".encode()
            raise URLError("A private-looking upstream value must not surface.")

        sources, reports = discover([LANDMARK], fetcher)
        responding = {source["id"] for source in sources if source["status"] == "ok"}
        self.assertEqual(responding, {"github", "gta6-how"})
        self.assertEqual(sources[0]["matched"], 1)
        self.assertEqual(sources[0]["byCategory"], {"gloves": 1})
        self.assertNotIn("private-looking", json.dumps(sources))
        self.assertEqual(reports[0]["communityVotes"], {"up": 11, "down": 2, "url": PUBLIC_LINK})
        self.assertEqual(reports[0]["confidence"], "area")
        self.assertEqual((reports[0]["x"], reports[0]["y"]), (0.25, 0.75))
        self.assertEqual(reports[-1]["confidence"], "lead")
        self.assertEqual(reports[-1]["source"], "https://example.org/trail")

    def test_reject_unsafe_or_irrelevant_records(self):
        for title, url in [
            ("GTA 5 gloves found near Synthetic Harbor", PUBLIC_LINK),
            ("GTA VI gloves rumored to unlock", PUBLIC_LINK),
            (TITLE, "javascript:alert(1)"),
        ]:
            with self.subTest(title=title, url=url):
                self.assertIsNone(make_report(SOURCES[0], (title, EXCERPT, url, PUBLISHED, None), [LANDMARK]))
        with self.assertRaises(ValueError):
            parse_feed(b"<!DOCTYPE rss><rss/>")
        report = make_report(SOURCES[0], (TITLE, EXCERPT, PUBLIC_LINK, PUBLISHED, {"+1": -1, "-1": 2}),
                             [LANDMARK, {**LANDMARK, "id": "other"}])
        self.assertIsNone(report["x"])
        self.assertNotIn("communityVotes", report)

    def test_discovery_does_not_locate_reports_by_placeholder_or_counterpart_title(self):
        for origin in ("placeholder", "counterpart"):
            with self.subTest(origin=origin):
                landmark = {**LANDMARK, "nameOrigin": origin}
                report = make_report(SOURCES[0], (TITLE, EXCERPT, PUBLIC_LINK, PUBLISHED, None), [landmark])
                self.assertEqual(report["confidence"], "lead")
                self.assertIsNone(report["landmarkId"])

    def test_publisher_guide_launch_window_and_exact_venue_excerpt(self):
        source = next(source for source in SOURCES if source.id == "powerpyx")
        guide = ("GTA 6 headphones unlock guide",
                 "Buy the headphones at Synthetic Harbor.", "https://www.powerpyx.com/guide/",
                 REVIEW_EMBARGO.isoformat(), None)
        report = make_report(source, guide, [LANDMARK])
        self.assertEqual((report["category"], report["confidence"], report["landmarkId"]),
                         ("earbuds", "area", LANDMARK["id"]))
        self.assertIsNone(make_report(SOURCES[0], guide, [LANDMARK]))
        self.assertIsNone(make_report(source, (guide[0], guide[1], PUBLIC_LINK, *guide[3:]), [LANDMARK]))
        self.assertIsNone(make_report(source, ("GTA 6 pre-order headphone reward", *guide[1:]), [LANDMARK]))
        second_place = {**LANDMARK, "id": "synthetic-store", "title": "Synthetic Store"}
        conflicting = (guide[0], guide[1] + " Or look inside Synthetic Store.", *guide[2:])
        self.assertIsNone(make_report(source, conflicting, [LANDMARK, second_place])["x"])
        broad_guide = ("GTA 6 All Electronics Stores Locations", *guide[1:])
        self.assertEqual(make_report(source, broad_guide, [LANDMARK])["confidence"], "lead")
        no_location = (guide[0], "Synthetic Harbor is popular.", *guide[2:])
        self.assertIsNone(make_report(source, no_location, [LANDMARK])["x"])

    def test_single_mission_requires_a_walkthrough_and_routes_only_to_its_start(self):
        source = next(source for source in SOURCES if source.id == "powerpyx-missions")
        destination = {**LANDMARK, "id": "destination", "title": "Synthetic Store", "x": .5}
        item = (
            "GTA 6 Moonlight Shift Walkthrough",
            "Moonlight Shift is a main mission. Finish it by talking at Synthetic Store."
            " Starting Location: Synthetic County > Synthetic Harbor Chapter: Chapter 3"
            " Requirement: Complete the previous mission Can Be Started By: Lucia Reward: None",
            "https://www.powerpyx.com/gta-6-moonlight-shift-walkthrough/", PUBLISHED, None,
        )
        row = make_report(source, item, [LANDMARK, destination])
        self.assertEqual((row["category"], row["missionName"], row["chapter"], row["character"]),
                         ("mission", "Moonlight Shift", 3, "Lucia"))
        self.assertEqual(row["source"], item[2])
        self.assertEqual(row["sourceName"], source.name)
        self.assertEqual(row["landmarkId"], LANDMARK["id"])
        self.assertEqual(row["prerequisite"], "Complete the previous mission")
        self.assertEqual(row["confidence"], "area")
        self.assertEqual(row["startingLocation"], "Synthetic County > Synthetic Harbor")
        text_only = make_report(source, item, [destination])
        self.assertIsNone(text_only["x"])
        self.assertEqual(text_only["region"], "Synthetic County > Synthetic Harbor")
        for title in (
            "GTA 6 Full Walkthrough – All Missions",
            "GTA VI Release Times: Story Walkthrough",
            "GTA 6 Mission List and Rewards",
            "GTA VI Moonlight Shift Review",
            "GTA VI Moonlight Shift and Cold Noon Walkthrough: Both Chapter 3 Missions",
        ):
            with self.subTest(title=title):
                self.assertIsNone(make_report(source, (title, *item[1:]), [LANDMARK]))
        changed = (item[0], item[1] + " The mission was removed in the latest patch.", *item[2:])
        stale = make_report(source, changed, [LANDMARK])
        result, = review_reports([stale])
        self.assertEqual(result["verification"]["status"], "review")
        self.assertIsNone(result["x"])
        self.assertEqual(stale["x"], .25)

    def test_compact_publisher_mission_metadata_and_broad_collectible_leads(self):
        source = next(source for source in SOURCES if source.id == "gtaboom")
        row = make_report(source, (
            "How to Complete Moonlight Shift in GTA 6",
            "Follow the green signs to find the foreman, then take the bag to the northern gate.",
            "https://www.gtaboom.com/gta-6-moonlight-shift-walkthrough-ffff", PUBLISHED, None,
        ), [LANDMARK])
        self.assertEqual((row["missionName"], row["category"], row["confidence"]),
                         ("Moonlight Shift", "mission", "lead"))
        named_part = make_report(source, (
            "GTA VI Lighthouse Walkthrough (Part 2 of 3): Repair the Lantern",
            "Follow the marked footpath to the keeper, then return to the light tower.",
            "https://www.gtaboom.com/gta-6-repair-the-lantern-walkthrough-50a8", PUBLISHED, None,
        ), [LANDMARK])
        self.assertEqual(named_part["missionName"], "Repair the Lantern")
        self.assertIsNone(make_report(source, (
            "GTA 6 Unrelated Walkthrough", "Follow the map to find a prize and get a ride.",
            "https://www.gtaboom.com/review-trailer-ffff", PUBLISHED, None,
        ), [LANDMARK]))
        row = make_report(source, (
            "GTA 6 All Collectible Locations Walkthrough",
            "Find and collect the first item at Synthetic Harbor. There are more picks around the county.",
            "https://www.gtaboom.com/collectibles", PUBLISHED, None,
        ), [LANDMARK])
        self.assertEqual(row["category"], "collectible")
        self.assertIsNone(row["x"])


class ProviderTests(unittest.TestCase):
    def test_optional_model_venue_requires_a_literal_report_quote_and_unique_place(self):
        config = configure({"kind":"ollama-local","model":"fixture","enabled":True}, Provider())
        excerpt = "Pier Arcade stocks earbuds in its game shop."
        place = {"id":"p1","title":"Pier Arcade","region":"Leonida","x":0.38,"y":0.44}
        report = {"title":"New earbuds found","_extract":excerpt}
        def responder(quote):
            def fetcher(url, **kwargs):
                return json.dumps({"message":{"content":json.dumps({"steps":[],"venue":"Pier Arcade","quote":quote,"x":0.99})}}).encode()
            return fetcher
        sample = dict(report)
        add_source_steps(config,sample,responder(excerpt),landmarks=[place])
        self.assertEqual((sample["x"],sample["y"],sample["confidence"]),(.38,.44,"area"))
        for places,quote in (([place],"Pier Arcade sells every item."),([place,dict(place,id="p2")],excerpt)):
            sample=dict(report)
            add_source_steps(config,sample,responder(quote),landmarks=places)
            self.assertNotIn("x",sample)

    def test_ollama_cloud_payload_and_grounding(self):
        config = configure({"kind": "ollama-cloud", "model": "synthetic", "key": "mock-credential",
                            "enabled": True, "allowPaid": True, "base": "https://example.invalid"})
        self.assertTrue(config.active)
        self.assertNotIn("mock-credential", json.dumps(config.public()))
        report = {"_extract": EXCERPT}

        def fetcher(url, *, headers, payload, **kwargs):
            self.assertEqual(url, "https://ollama.com/api/chat")
            self.assertEqual(headers["Authorization"], "Bearer mock-credential")
            self.assertFalse(payload["stream"])
            self.assertNotIn("format", payload)
            return json.dumps({"message": {"content": json.dumps({
                "steps": ["Invented steps get dropped.", EXCERPT], "x": 0.2,
            })}}).encode()

        self.assertEqual(add_source_steps(config, report, fetcher), "Source step extracted.")
        self.assertEqual(report["steps"], [EXCERPT])
        self.assertNotIn("x", report)

    def test_provider_consent_and_separate_key_scope(self):
        config = configure({"kind": "openrouter", "key": "mock-credential"}, Provider())
        self.assertEqual(config.model, "")
        self.assertFalse(config.active)
        self.assertTrue(configure({"kind": "openrouter", "enabled": True}, config).active)
        self.assertFalse(configure({"kind": "ollama-cloud"}, config).key)
        with self.assertRaisesRegex(ValueError, "explicit consent"):
            configure({"kind": "openrouter", "model": "some/paid", "enabled": True}, config)
        with self.assertRaisesRegex(ValueError, "own client"):
            configure({"kind": "opencode", "model": "something-free"})
        with self.assertRaisesRegex(ValueError, "loopback"):
            configure({"kind": "ollama-local", "base": "https://example.com"})

    def test_metadata_probe_never_calls_chat(self):
        config = configure({"kind": "ollama-local", "model": "synthetic"}, probe=True)

        def fetcher(url, **kwargs):
            self.assertEqual(url, "http://127.0.0.1:11434/api/tags")
            self.assertIsNone(kwargs["payload"])
            return b'{"models":[{"name":"synthetic"},{"name":"skip-cloud"},{"name":"alias","remote_model":"x"}]}'

        self.assertEqual(list_models(config, fetcher), {"models": ["synthetic"], "selectedAvailable": True, "recommended": None})


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.public = root / "public"
        self.public.mkdir()
        (self.public / "example.mjs").write_text("export default 42;", encoding="utf-8")
        (root / "private.txt").write_text("outside public", encoding="utf-8")
        self.cache = root / "state.json"
        self.calls = 0
        self.atlas = Atlas(self.cache, self.public, self.synthetic_refresh)
        self.server = LocalServer(self.atlas, port=0)
        thread = Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.worker = Thread(target=self.atlas.worker, daemon=True)
        self.addCleanup(self.stop_worker)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def stop_worker(self):
        self.atlas.stop()
        if self.worker.is_alive():
            self.worker.join(2)

    def synthetic_refresh(self, landmarks):
        self.calls += 1
        health = [{**source.health(), "status": "ok"} for source in SOURCES]
        row = make_report(SOURCES[0], (TITLE, EXCERPT, PUBLIC_LINK, PUBLISHED, None), [])
        return health, [row, dict(row)]

    def request(self, method, path, body=None, headers=None):
        con = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            headers = dict(headers or {})
            if body is not None:
                headers.update({"Content-Type": "application/json", "Origin": headers.get("Origin", self.origin)})
                body = json.dumps(body).encode()
            con.request(method, path, body, headers)
            response = con.getresponse()
            payload = response.read()
            content_type = response.getheader("Content-Type")
            if content_type.startswith("application/json"):
                payload = json.loads(payload)
            return response.status, content_type, payload
        finally:
            con.close()

    def wait_for_run(self, old_last=None):
        deadline = monotonic() + 3
        while monotonic() < deadline:
            state = self.request("GET", "/api/state")[2]
            if not state["running"] and state["lastRun"] and state["lastRun"] != old_last:
                return state
            sleep(0.03)
        self.fail("Worker did not complete its run.")

    def test_browserless_refresh_and_restart_cache(self):
        self.worker.start()
        state = self.wait_for_run()
        self.assertEqual(self.calls, 1)
        self.assertEqual(len(state["reports"]), 1)
        self.assertIsNone(state["reports"][0]["x"])
        self.assertFalse(state["provider"]["active"])
        self.assertEqual(self.request("POST", "/api/settings", {"interval": 6})[0], 200)
        self.assertEqual(self.request("POST", "/api/refresh", {})[0], 202)
        state = self.wait_for_run(state["lastRun"])
        self.assertEqual(self.calls, 2)
        restored = Atlas(self.cache, self.public)
        self.assertEqual(restored.interval, 6)
        self.assertEqual(restored.next_run - restored.last_run, timedelta(hours=6))
        self.assertEqual(len(restored.reports), 1)
        status, _, saved = self.request("POST", "/api/provider", {"kind": "ollama-cloud",
            "model": "synthetic", "key": "mock-credential", "enabled": True, "allowPaid": True})
        self.assertEqual(status, 200)
        self.assertTrue(saved["provider"]["hasKey"])
        self.assertNotIn("mock-credential", json.dumps(saved))
        self.assertNotIn("mock-credential", self.cache.read_text(encoding="utf-8"))

    def test_host_origin_and_static_boundaries(self):
        self.assertEqual(self.request("GET", "/api/state", headers={"Host": "example.test"})[0], 403)
        self.assertEqual(self.request("POST", "/api/refresh", {}, {"Origin": "https://example.test"})[0], 403)
        self.assertEqual(self.request("POST", "/api/settings", {"interval": 8})[0], 400)
        self.assertEqual(self.request("GET", "/%2e%2e/private.txt")[0], 404)
        self.assertEqual(self.request("GET", "/example.mjs")[:2], (200, "text/javascript"))
        (self.cache.parent / "rockstar-map-original.jpg").write_bytes(b"fixture")
        self.assertEqual(self.request("GET", "/official-map.jpg"), (200, "image/jpeg", b"fixture"))
        self.assertEqual(self.request("GET", "/rockstar-map-original.jpg")[0], 404)

    def test_vote_through_local_http(self):
        player = "e0a8ab34-eeea-45dd-83c7-22cc7b843328"
        path = "/api/votes?id=synthetic-harbor"
        self.assertEqual(self.request("GET", path)[2], {"up": 0, "down": 0, "mine": 0})
        self.assertEqual(self.request("POST", "/api/votes", {
            "id": "synthetic-harbor", "player": player, "vote": -1,
        })[2], {"up": 0, "down": 1, "mine": -1})
        self.assertEqual(self.request("GET", path, headers={"X-Atlas-Player": player})[2],
                         {"up": 0, "down": 1, "mine": -1})

    def test_ephemeral_position_and_locate_size_limit(self):
        self.assertEqual(self.request("GET", "/api/position")[:1], (200,))
        self.assertIsNone(self.request("GET", "/api/position")[2])
        status, _, position = self.request("POST", "/api/position", {"x": 0.18, "y": 0.62})
        self.assertEqual(status, 200)
        self.assertEqual(self.request("GET", "/api/position")[2], position)
        self.assertIsNone(Atlas(self.cache, self.public).position())
        self.assertIsNone(self.request("POST", "/api/position", {"clear": True})[2])
        large = {"image": "a" * 5000, "pixelX": 0, "pixelY": 0}
        self.assertIn("JPEG screenshot", self.request("POST", "/api/locate", large)[2]["error"])
        self.assertIn("4096 bytes", self.request("POST", "/api/position", large)[2]["error"])
        self.assertEqual(self.request("POST", "/api/locate", large, {"Origin": "https://example.test"})[0], 403)


if __name__ == "__main__":
    unittest.main()
