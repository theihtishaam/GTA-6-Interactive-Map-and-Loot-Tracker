from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
import unittest

from discovery import LAUNCH
from resource_discovery import PublicResponse, discover_resources, fetch_public, web_url

NOW = LAUNCH + timedelta(days=3, hours=16)
OLD = LAUNCH + timedelta(hours=1)
FRESH = LAUNCH + timedelta(hours=23)
A = "https://games.example/"
B = "https://guides.example/"


def index_snapshot(rows):
    return ("<rss><channel>" + "".join(
        f"<item><title>{escape(title)}</title><pubDate>{format_datetime(stamp)}</pubDate>"
        f'<source url="{url}">{escape(name)}</source></item>'
        for title, stamp, url, name in rows
    ) + "</channel></rss>").encode()


def feed_snapshot(rows):
    return ("<rss><channel>" + "".join(
        f"<item><title>{escape(title)}</title><description>Find this guide and unlock the collectible.</description>"
        f"<link>{escape(url)}</link><pubDate>{format_datetime(stamp)}</pubDate></item>"
        for title, url, stamp in rows
    ) + "</channel></rss>").encode()


class ResourceTests(unittest.TestCase):
    def fixture(self, index_down=False):
        calls = []
        index = index_snapshot([
            ("GTA VI Headphones Locations", FRESH, A, "Games Example"),
            ("GTA 6 Collectible Locations", FRESH, B, "Guides Example"),
            ("GTA 6 Hidden Rewards Locations", FRESH, "https://www.gamesradar.com", "Existing Source"),
            ("GTA 6 Story Mission Walkthrough", FRESH, "https://www.gtaboom.com", "Existing Fixed Guide"),
            ("GTA 6 Rumored Collectibles", FRESH, "https://rumor.example", "Rumor"),
            ("GTA 6 Earbuds Locations", FRESH, "https://127.0.0.1/", "Invalid"),
        ])
        lookup = {
            A: b'<link rel="alternate" type="application/rss+xml" title="Comments feed" href="/comments/feed/">'
               b'<link rel="alternate" type="application/atom+xml" href="/atlas-feed"/>',
            B: b'<meta name="generator" content="WordPress 7.0">',
            A + "atlas-feed": feed_snapshot([
                ("GTA VI Headphones Locations", A + "headphones?utm_source=feed", FRESH),
                ("GTA VI Headphones Locations", A + "headphones", FRESH),
                ("GTA 6 Collectible Locations", A + "collectibles", OLD),
                ("GTA 6 Collectible Locations", "https://other.example/", FRESH),
                ("GTA 6 Rumored Gloves Locations", A + "rumor", FRESH),
                ("GTA 6 Collectible Locations", "https://wrong-port.example:8443/", FRESH),
            ]),
            B + "?s=GTA+6&feed=rss2": feed_snapshot([
                ("GTA 6 Bank Vault Locations", B + "banks", OLD),
                ("GTA IV Collectible Locations", B + "old-game", FRESH),
            ]),
        }

        def fetch(url, **opts):
            calls.append(url)
            if url.startswith("https://news.google.com"):
                if index_down:
                    raise TimeoutError("An index response contained private diagnostic text.")
                return PublicResponse(url, index)
            if url not in lookup:
                raise ConnectionError("Unexpected endpoint.")
            return PublicResponse(url, lookup[url])

        return fetch, calls

    def test_discovers_new_sites_ranks_coverage_and_quarantines_unrelated_items(self):
        fetch, calls = self.fixture()
        sources, reports = discover_resources([], now=NOW, fetcher=fetch)
        feed_a, feed_b = [row for row in sources if row["sourceType"] == "feed"]
        self.assertEqual((feed_a["score"], feed_b["score"]), (7, 2))
        self.assertEqual(feed_a["feedUrl"], A + "atlas-feed")
        self.assertTrue(feed_a["qualified"])
        self.assertTrue(feed_a["id"].startswith("auto-"))
        self.assertEqual(feed_a["provenance"]["publisher"], A)
        self.assertTrue(feed_a["lastQualifiedAt"])
        self.assertEqual([row["source"] for row in reports], [
            A + "headphones", A + "collectibles", B + "banks",
        ])
        self.assertTrue(all(row.get("sourceId") and row.get("discoveredVia") for row in reports))
        self.assertFalse(any(site in url for url in calls
                             for site in ("gamesradar", "gtaboom", "rumor.example", "127.0.0.1", "comments/feed")))
        self.assertEqual(sum(url.startswith("https://news.google.com") for url in calls), 3)

    def test_retains_qualified_feeds_during_search_outage(self):
        normal, _ = self.fixture()
        previous, _ = discover_resources([], now=NOW, fetcher=normal)
        down, calls = self.fixture(index_down=True)
        rows, reports = discover_resources([], now=NOW, previous=previous, fetcher=down)
        self.assertIn(A + "atlas-feed", calls)
        self.assertNotIn(A, calls)
        self.assertEqual(len(reports), 3)
        self.assertEqual(sum(row["status"] == "error" for row in rows), 3)

    def test_mission_query_discovers_own_publisher_walkthrough(self):
        from urllib.parse import parse_qs, urlsplit

        def fetch(url, **unused):
            if url.startswith("https://news.google.com"):
                query = parse_qs(urlsplit(url).query)["q"][0]
                rows = [("GTA VI Moonlight Shift Walkthrough", FRESH, A, "Example")] if '"story mission"' in query else []
                return PublicResponse(url, index_snapshot(rows))
            if url == A:
                return PublicResponse(url, b'<link rel="alternate" type="application/rss+xml" href="/missions">')
            return PublicResponse(url, (
                f"<rss><channel><item><title>GTA VI Moonlight Shift Walkthrough</title>"
                f"<description>Moonlight Shift is a main mission. Follow the signs to meet the foreman.</description>"
                f"<link>{A}moonlight</link><pubDate>{format_datetime(FRESH)}</pubDate></item>"
                "<item><title>GTA VI Full Walkthrough: All Missions</title>"
                f"<description>Find every main mission and side quest.</description><link>{A}all</link>"
                f"<pubDate>{format_datetime(FRESH)}</pubDate></item></channel></rss>"
            ).encode())

        rows, reports = discover_resources([], now=NOW, fetcher=fetch)
        report, = reports
        self.assertEqual(report["category"], "mission")
        self.assertEqual(report["source"], A + "moonlight")
        self.assertEqual(report["confidence"], "lead")
        self.assertEqual(rows[0]["byCategory"], {"mission": 1})
        self.assertNotIn("private diagnostic", str(rows))

    def test_health_for_unreadable_feed(self):
        indexed = index_snapshot([("GTA VI Headphones Locations", FRESH, A, "Games Example")])

        def fetch(url, **_):
            if url.startswith("https://news.google.com"):
                return PublicResponse(url, indexed)
            if url == A:
                return PublicResponse(url, b"<html><title>Site</title></html>")
            return PublicResponse(url, b'<!DOCTYPE rss [<!ENTITY x "sample">]><rss/>')

        rows, reports = discover_resources([], now=NOW, fetcher=fetch)
        self.assertEqual(reports, [])
        failure = next(row for row in rows if row["sourceType"] == "feed")
        self.assertFalse(failure["qualified"])
        self.assertEqual(failure["status"], "error")

    def test_rechecks_homepage_when_a_previously_qualified_feed_moves(self):
        normal, _ = self.fixture()
        previous, _ = discover_resources([], now=NOW, fetcher=normal)
        offline_index, _ = self.fixture(index_down=True)

        def moved(url, **opts):
            if url == A:
                return PublicResponse(url, b'<link rel="alternate" type="application/rss+xml" href="/new-feed">')
            if url == A + "atlas-feed":
                raise ConnectionError("Feed moved.")
            if url == A + "new-feed":
                return PublicResponse(url, feed_snapshot([("GTA 6 Earbuds Locations", A + "earbuds", FRESH)]))
            return offline_index(url, **opts)

        rows, reports = discover_resources([], now=NOW, previous=previous, fetcher=moved)
        source = next(row for row in rows if row.get("homepage") == A)
        self.assertEqual(source["feedUrl"], A + "new-feed")
        self.assertTrue(source["qualified"])
        self.assertIn(A + "earbuds", [row["source"] for row in reports])


class PublicTransportTests(unittest.TestCase):
    def test_reject_unsafe_url_shapes(self):
        for url in (
            "http://example.com/", "https://127.0.0.1/", "https://[::1]/",
            "https://metadata.internal/", "https://user@example.com/",
            "https://example.com:8443/", "https://example.com/\\file",
            "https://example.com/?access_token=synthetic", "https://example.com/?api%5Fkey=synthetic",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    web_url(url)

    def test_recheck_dns_at_same_host_redirect_and_stop_when_it_turns_private(self):
        resolved = iter([("93.184.216.34",), ("127.0.0.1",)])
        requests = []

        def request(url, address, _, __):
            requests.append((url, address))
            return "/next", None

        with self.assertRaisesRegex(ValueError, "DNS answer"):
            fetch_public("https://example.com/start", resolver=lambda *_: next(resolved), requester=request)
        self.assertEqual(requests, [("https://example.com/start", "93.184.216.34")])

    def test_reject_mixed_private_answer_and_nonpublic_redirect(self):
        for unsafe_address in ("10.1.2.3", "169.254.169.254", "100.64.0.1", "::ffff:127.0.0.1", "ff02::1", "fc00::1"):
            with self.subTest(address=unsafe_address):
                with self.assertRaisesRegex(ValueError, "DNS answer"):
                    fetch_public("https://example.com", resolver=lambda *_: ("93.184.216.34", unsafe_address),
                                 requester=lambda *_: self.fail("An unsafe DNS answer reached transport."))
        with self.assertRaises(ValueError):
            fetch_public("https://example.com", resolver=lambda *_: ("93.184.216.34",),
                         requester=lambda *_: ("http://example.com/feed", None))

    def test_redirect_gets_new_pinned_public_address(self):
        calls = []

        def resolve(host, _):
            return {"example.com": ("93.184.216.34",), "others.example": ("1.1.1.1",)}[host]

        def request(url, address, _, __):
            calls.append((url, address))
            if len(calls) == 1:
                return "https://others.example/feed", None
            return None, PublicResponse(url, b"body")

        result = fetch_public("https://example.com/", resolver=resolve, requester=request)
        self.assertEqual(result.body, b"body")
        self.assertEqual(calls, [("https://example.com/", "93.184.216.34"),
                                 ("https://others.example/feed", "1.1.1.1")])

    def test_redirect_loop_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "Redirect loop"):
            fetch_public("https://example.com/loop", resolver=lambda *_: ("93.184.216.34",),
                         requester=lambda *_: ("/loop", None))


if __name__ == "__main__":
    unittest.main()
