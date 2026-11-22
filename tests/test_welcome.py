from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from server import Atlas


class WelcomeTest(unittest.TestCase):
    def test_two_tabs_and_restart_share_one_welcome(self):
        with TemporaryDirectory() as folder:
            cache = Path(folder) / "state.json"
            app = Atlas(cache=cache)
            app.settings({"interval": 12})
            app = Atlas(cache=cache)
            self.assertTrue(app.state()["welcomePending"])
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(app.claim_welcome, [{}, {}]))
            self.assertCountEqual(results, [{"show": True}, {"show": False}])
            self.assertFalse(Atlas(cache=cache).state()["welcomePending"])

    def test_existing_install_keeps_its_settings_and_skips_the_welcome(self):
        with TemporaryDirectory() as folder:
            cache = Path(folder) / "state.json"
            cache.write_text(json.dumps({"interval": 6, "sources": [], "reports": []}))
            app = Atlas(cache=cache)
            self.assertEqual(app.claim_welcome({}), {"show": False})
            self.assertEqual(app.interval, 6)
