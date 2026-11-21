import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from media_cache import MediaCache, article_allowed, image_type


class TestMediaCache(TestCase):
    def test_source_image_article_preview_offline_and_size_bounds(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            page = "https://www.powerpyx.com/gta-6-sample/"
            image = "https://www.powerpyx.com/wp-content/uploads/test.jpg"
            rows = [{"id":"test-photo", "source":page, "sourceImage":image},
                    {"id":"article", "source":page},
                    {"id":"unsafe", "source":page,"sourceImage":"https://127.0.0.1/test.jpg"}]
            (root / "guides.json").write_text(json.dumps(rows))
            (root / "guide-positions.json").write_text("{}")
            calls = []
            def fetch(url, **options):
                calls.append(url)
                self.assertLessEqual(options["max_size"], 3_500_000)
                if url == page:
                    return ('<meta property="og:image" content="' + image + '">').encode()
                self.assertEqual(url, image)
                return bytes.fromhex("ffd8ffe000104a4649460001ffd9")
            cache = MediaCache(root / "media", root, fetch)
            cache.sync([])
            a, b = cache.describe("test-photo"), cache.describe("article")
            self.assertEqual(a["path"],b["path"])
            self.assertEqual(a["caption"],"Source screenshot")
            self.assertEqual(b["caption"],"Article preview")
            self.assertIsNone(cache.describe("unsafe"))
            self.assertIsNone(cache.filepath("../guides.json"))
            self.assertTrue(cache.filepath(a["path"][7:])[0].is_file())
            self.assertIsNone(cache.filepath("0"*64+".svg"))
            reopened = MediaCache(root / "media", root, lambda *a, **k:self.fail("unexpected refetch"))
            reopened.sync([])
            self.assertEqual(a,reopened.describe("test-photo"))
    def test_public_eligibility(self):
        self.assertFalse(article_allowed({"source":"https://example.org/post"}))
        self.assertTrue(article_allowed({"source":"https://example.org/post", "sourceId":"auto-abc","discoveredVia":"https://news.google.com/"}))
        self.assertFalse(article_allowed({"source":"http://localhost/post", "sourceId":"auto-abc","discoveredVia":"https://news.google.com/"}))
        with self.assertRaises(ValueError): image_type(b"<html>not an image</html>")

