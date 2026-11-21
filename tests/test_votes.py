import json
import tempfile
import unittest
import uuid
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen
from community_votes import VoteService
from votes import handle_read, handle_write, shared_origin


class BallotTests(unittest.TestCase):
    def test_edit_clear_and_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            key = "guide-one"
            a, b = str(uuid.uuid4()), str(uuid.uuid4())
            def cast(who, direction):
                return handle_write(folder, {"id": key, "player": who, "vote": direction})
            self.assertEqual(handle_read(folder, key), {"up": 0, "down": 0, "mine": 0})
            cast(a, 1)
            cast(a, 1)
            self.assertEqual(cast(b, -1), {"up": 1, "down": 1, "mine": -1})
            self.assertEqual(cast(b, 1), {"up": 2, "down": 0, "mine": 1})
            self.assertEqual(cast(a, 0), {"up": 1, "down": 0, "mine": 0})
            with self.assertRaises(ValueError):
                cast(a, True)

    def test_shared_service_and_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "community.json"
            config.write_text('{"origin":"https://votes.example.org"}')
            self.assertEqual(shared_origin(folder), "https://votes.example.org")
            config.write_text('{"origin":"https://bad.example/unsafe"}')
            self.assertEqual(shared_origin(folder), "")
            origin = "http://127.0.0.1:8765"
            with VoteService(("127.0.0.1", 0), folder, [origin]) as service:
                worker = Thread(target=service.serve_forever)
                worker.start()
                try:
                    vote = {"player": str(uuid.uuid4()), "id": "guide-one", "vote": 1}
                    url = f"http://127.0.0.1:{service.server_port}/api/votes"
                    req = Request(url, data=json.dumps(vote).encode(), headers={"Origin":origin,"Content-Type":"application/json"})
                    with urlopen(req) as res:
                        self.assertEqual(res.headers["Access-Control-Allow-Origin"],origin)
                        self.assertEqual(json.load(res), {"up":1,"down":0,"mine":1})
                finally:
                    service.shutdown()
                    worker.join()

