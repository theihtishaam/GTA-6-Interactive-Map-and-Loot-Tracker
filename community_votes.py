"""Optional shared atlas voting endpoint. Run behind your own HTTPS reverse proxy."""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from votes import handle_read, handle_write


class VoteService(ThreadingHTTPServer):
    def __init__(self, address, directory, origins):
        self.directory = directory
        self.origins = set(origins)
        self.limit_lock = Lock()
        self.windows = {}
        super().__init__(address, VoteHandler)

    def accept_write(self, player):
        minute = int(time.monotonic() // 60)
        with self.limit_lock:
            if minute not in self.windows:
                self.windows = {minute: {}}
            counts = self.windows[minute]
            if counts.get(player, 0) >= 30 or len(counts) >= 12000:
                return False
            counts[player] = counts.get(player, 0) + 1
            return True


class VoteHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, status, value=None):
        raw = json.dumps(value).encode() if value is not None else b""
        self.send_response(status)
        origin = self.headers.get("Origin", "")
        if origin in self.server.origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Atlas-Player")
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def serve_vote(self):
        if urlsplit(self.path).path != "/api/votes":
            return self.respond(404, {"error": "Unknown resource."})
        if self.headers.get("Origin") not in self.server.origins:
            return self.respond(403, {"error": "Atlas origin is not enabled here."})
        try:
            if self.command == "OPTIONS":
                return self.respond(204)
            if self.command == "GET":
                query = parse_qs(urlsplit(self.path).query, max_num_fields=4)
                value = handle_read(self.server.directory, query.get("id", [""])[0], self.headers.get("X-Atlas-Player", ""))
            else:
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Send a JSON object.")
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 2048:
                    raise ValueError("Invalid ballot size.")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or not isinstance(body.get("player"), str):
                    raise ValueError("Invalid ballot.")
                if not self.server.accept_write(body["player"]):
                    return self.respond(429, {"error": "Please wait before voting again."})
                value = handle_write(self.server.directory, body)
        except (ValueError, TypeError):
            return self.respond(400, {"error": "Invalid ballot request."})
        self.respond(200, value)

    do_GET = do_POST = do_OPTIONS = serve_vote


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--origin", action="append",
                        default=["http://127.0.0.1:8765", "http://localhost:8765"])
    parser.add_argument("--data", type=Path, default=Path(".atlas/shared-votes"))
    args = parser.parse_args()
    with VoteService(("127.0.0.1", args.port), args.data, args.origin) as service:
        print(f"Shared votes on loopback port {args.port}.", flush=True)
        service.serve_forever()

