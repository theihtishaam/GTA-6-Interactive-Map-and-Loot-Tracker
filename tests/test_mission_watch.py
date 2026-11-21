"""Offline checks for mission index additions using synthetic, public-shaped pages."""
from unittest import TestCase

from mission_watch import INDEX, discover_index


class MissionWatchTests(TestCase):
    def setUp(self):
        self.links = [f"https://www.powerpyx.com/gta-6-sample-{i}-walkthrough/" for i in range(15)]
        rows = "".join(f'<li><a href="{url}">Sample Mission {i}</a></li>' for i,url in enumerate(self.links))
        noise = '<li><a href="https://example.org/offsite">Outside</a></li>'
        self.index = (f'<ol>{noise}</ol><div class="entry-content"><h2>Chapter 1</h2><ol>{rows}{noise}</ol></div>').encode()
        self.calls = []
        self.venue = {"id":"one","title":"Example Port","category":"landmark","nameOrigin":"game",
                      "type":"pier","region":"Test City","x":.2,"y":.3}

    def fetch(self,url,**kwargs):
        self.calls.append(url)
        if url == INDEX:
            return self.index
        return (b'<meta property="article:published_time" content="2026-11-19T10:00:00Z">'
                b'<div class="entry-content"><ul><li>Starting Location: Example Port</li>'
                b'<li>Chapter: 2</li><li>Can Be Started By: Lucia</li><li>Reward: Example jacket</li></ul></div>')

    def test_checks_whole_index_only_reads_unseen_detail(self):
        known = [{"source":url} for url in self.links[:-1]]
        health, reports = discover_index(known, [], [self.venue], self.fetch)
        self.assertEqual((health["seen"],health["matched"]), (15,1))
        self.assertEqual(self.calls,[INDEX,self.links[-1]])
        r = reports[0]
        self.assertEqual((r["category"],r["chapter"],r["character"],r["x"],r["y"]),("mission",2,"Lucia",.2,.3))
        self.calls.clear()
        self.assertFalse(discover_index(known,reports,[self.venue],self.fetch)[1])
        self.assertEqual(self.calls,[INDEX])

    def test_quota_and_publication_dates(self):
        health, reports = discover_index([], [], [], self.fetch)
        self.assertEqual(len(self.calls),5)
        self.assertEqual(len(reports),4)
        self.assertTrue(all(r["x"] is None for r in reports))
        health, reports = discover_index([], [], [], lambda u,**kw: self.index if u == INDEX else b"missing")
        self.assertFalse(reports)
        self.assertIn("could not be validated",health["error"])
        health, reports = discover_index([],[],[],lambda *a,**kw:b"<html>service outage</html>")
        self.assertEqual(health["status"],"error")
