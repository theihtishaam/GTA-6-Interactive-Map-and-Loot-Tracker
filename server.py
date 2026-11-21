"""Loopback-only HTTP server and persistent community discovery schedule."""

import json
import mimetypes
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Condition, Thread
from urllib.parse import parse_qs, unquote, urlsplit

from bounty_watch import BOUNTY_SOURCES, discover_bounties, merge_bounty_reports
from discovery import SOURCES, discover, iso_date, load_landmarks
from gps import GpsUnavailable, LOCATE_BODY_LIMIT, ScreenshotLocator, frame_coordinates
from providers import Provider, add_source_steps, configure, list_models
from media_cache import MediaCache
import votes

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
PORT = 8765
BODY_LIMIT = 4096
REPORT_LIMIT = 600
INTERVALS = (6, 12, 24)
CSP = (
    "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; connect-src 'self'"
)
MIME_TYPES = {".mjs": "text/javascript", ".js": "text/javascript", ".webp": "image/webp"}
MAP_ASSETS = {
    "/official-map.jpg": "rockstar-map-original.jpg",
    "/game-map.png": "powerpyx-map-original.png",
    "/day-map.webp": "day-map.webp",
    "/night-map.webp": "night-map.webp",
}


def utcnow():
    return datetime.now(timezone.utc)


class Atlas:
    def __init__(self, cache=ROOT / ".atlas" / "state.json", public=PUBLIC, discovery=discover,
                 bounty_discovery=discover_bounties):
        self.cache = cache
        self.public = public
        self.discovery = discovery
        self.bounty_discovery = bounty_discovery
        self.change = Condition()
        self.running = False
        self.requested = False
        self.stopping = False
        self.interval = 24
        self.reports = []
        self.sources = [source.health() for source in SOURCES]
        self.last_run = None
        self.provider = Provider()
        self.provider_status = None
        self.cache_error = None
        self.player_position = None
        self.locator = ScreenshotLocator(self.public, self.cache.parent)
        self.media = MediaCache(self.cache.parent / "evidence-images", self.public)
        self.bounty_reports = []
        self.bounty_sources = [source.health() for source in BOUNTY_SOURCES]
        self.bounty_interval = 24
        self.bounty_last_run = None
        self.bounty_running = False
        self.bounty_requested = False
        self._load()
        self.next_run = (self.last_run + timedelta(hours=self.interval)) if self.last_run else utcnow()
        self.bounty_next_run = (
            self.bounty_last_run + timedelta(hours=self.bounty_interval) if self.bounty_last_run else utcnow()
        )

    def _load(self):
        try:
            data = json.loads(self.cache.read_text(encoding="utf-8"))
            interval, reports, health = data["interval"], data["reports"], data["sources"]
            if interval not in INTERVALS or not isinstance(reports, list) or not isinstance(health, list):
                raise ValueError
            old_sources = {row["id"]: row for row in health if isinstance(row, dict) and "id" in row}
            self.sources = [old_sources.get(row["id"], row) for row in self.sources]
            self.sources.extend(row for key,row in old_sources.items() if isinstance(key,str) and key.startswith("auto-"))
            self.reports = [
                row for row in reports[:REPORT_LIMIT]
                if isinstance(row, dict) and all(key in row for key in ("id", "title", "publishedAt", "category"))
            ]
            self.interval = interval
            self.last_run = iso_date(data.get("lastRun"))
            self._load_bounty(data.get("bounty"))
            preferences = data.get("providerPreferences")
            if isinstance(preferences, dict):
                # Persist only non-secret fields. Remote inference stays inactive until a key is entered.
                allowed = {k: preferences[k] for k in ("kind", "base", "model", "allowPaid") if k in preferences}
                allowed["enabled"] = preferences.get("enabled", False) and allowed.get("kind") == "ollama-local"
                try:
                    self.provider = configure(allowed)
                except ValueError:
                    self.provider = Provider()
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError):
            self.cache_error = "The previous discovery cache could not be read."

    def _load_bounty(self, data):
        if not isinstance(data, dict):
            return
        interval, rows, health = data.get("interval"), data.get("reports"), data.get("sources")
        if type(interval) is int and interval in INTERVALS:
            self.bounty_interval = interval
        if isinstance(rows, list):
            self.bounty_reports = [
                row for row in rows[:300] if isinstance(row, dict) and isinstance(row.get("id"), str)
                and row.get("category") == "bounty"
            ]
        if isinstance(health, list):
            old = {row["id"]: row for row in health if isinstance(row, dict) and isinstance(row.get("id"), str)}
            self.bounty_sources = [
                {**row, **{key: old[row["id"]].get(key, row[key])
                           for key in ("status", "checkedAt", "seen", "matched", "error")}}
                if row["id"] in old and row["status"] != "manual" else row
                for row in self.bounty_sources
            ]
        self.bounty_last_run = iso_date(data.get("lastRun"))

    def _save(self):
        path = self.cache.with_suffix(".tmp")
        try:
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "interval": self.interval, "reports": self.reports, "sources": self.sources,
                "lastRun": self.last_run.isoformat() if self.last_run else None,
                "bounty": {"interval": self.bounty_interval, "reports": self.bounty_reports,
                           "sources": self.bounty_sources,
                           "lastRun": self.bounty_last_run.isoformat() if self.bounty_last_run else None},
                "providerPreferences": {"kind": self.provider.kind, "model": self.provider.model,
                                        "base": self.provider.base, "enabled": self.provider.enabled,
                                        "allowPaid": self.provider.allow_paid},
            }, ensure_ascii=False), encoding="utf-8")
            path.replace(self.cache)
            self.cache_error = None
        except OSError:
            self.cache_error = "The discovery cache could not be saved."

    def state(self):
        with self.change:
            return {
                "version": "0.1.0",
                "reports": self.reports, "sources": self.sources, "interval": self.interval,
                "running": self.running or self.requested,
                "lastRun": self.last_run.isoformat() if self.last_run else None,
                "nextRun": self.next_run.isoformat(),
                "provider": self.provider.public(self.provider_status),
                "cacheError": self.cache_error,
                "bounty": self.bounty_state(),
            }

    def bounty_state(self):
        with self.change:
            return {
                "reports": self.bounty_reports, "sources": self.bounty_sources,
                "interval": self.bounty_interval, "running": self.bounty_running or self.bounty_requested,
                "lastRun": self.bounty_last_run.isoformat() if self.bounty_last_run else None,
                "nextRun": self.bounty_next_run.isoformat(), "cacheError": self.cache_error,
            }

    def position(self):
        with self.change:
            return self.player_position

    def set_position(self, values):
        position = frame_coordinates(values, self.public)
        with self.change:
            self.player_position = position
            return position

    def settings(self, values):
        interval = values.get("interval")
        if type(interval) is not int or interval not in INTERVALS:
            raise ValueError("Refresh interval must be 6, 12, or 24 hours.")
        with self.change:
            self.interval = interval
            if self.last_run:
                self.next_run = self.last_run + timedelta(hours=interval)
            self._save()
            self.change.notify_all()
            return self.state()

    def bounty_settings(self, values):
        interval = values.get("interval")
        if type(interval) is not int or interval not in INTERVALS:
            raise ValueError("Bounty Watch interval must be 6, 12, or 24 hours.")
        with self.change:
            self.bounty_interval = interval
            if self.bounty_last_run:
                self.bounty_next_run = self.bounty_last_run + timedelta(hours=interval)
            self._save()
            self.change.notify_all()
            return self.bounty_state()

    def set_provider(self, values):
        with self.change:
            self.provider = configure(values, self.provider)
            self.provider_status = None
            self._save()
            return self.state()

    def model_list(self, values):
        with self.change:
            config = configure(values, self.provider, probe=True)
        return list_models(config)

    def refresh(self):
        with self.change:
            if not self.running:
                self.requested = True
            self.change.notify_all()
            return self.state()

    def bounty_refresh(self):
        with self.change:
            if not self.bounty_running:
                self.bounty_requested = True
            self.change.notify_all()
            return self.bounty_state()

    def worker(self):
        while True:
            with self.change:
                while not self.stopping and not self.requested and self.next_run > utcnow():
                    seconds = (self.next_run - utcnow()).total_seconds()
                    self.change.wait(max(0, min(60, seconds)))
                if self.stopping:
                    return
                self.requested = False
                self.running = True
                config = self.provider
                known_versions = {row["id"]: row.get("sourceDigest") for row in self.reports}

            try:
                landmarks = load_landmarks(self.public / "landmarks.json")
                sources, reports = self.discovery(landmarks)
                if self.discovery is discover:
                    from resource_discovery import discover_resources
                    previous = [s for s in self.sources if s["id"].startswith("auto-")]
                    try:
                        found, extra = discover_resources(landmarks, previous=previous)
                        sources = [*sources, *found]
                        reports = [*reports, *extra]
                    except (ValueError, OSError, RuntimeError):
                        sources = [*sources, *[{**s, "status":"error", "error":"Source search unavailable."} for s in previous]]
                candidates = [row for row in reports if row.get("_extract") and
                              (row["id"] not in known_versions or known_versions[row["id"]] != row.get("sourceDigest"))]
                status = None
                if config.active and candidates:
                    status = add_source_steps(config, candidates[0], landmarks=landmarks)
                for row in reports:
                    row.pop("_extract", None)
                with self.change:
                    self._merge(reports)
                    self.sources = sources
                    if self.provider is config and status:
                        self.provider_status = status
                if self.discovery is discover:
                    try:
                        self.media.sync(reports)
                    except (OSError, ValueError):
                        pass
            except Exception:
                # Recover the scheduler, without printing remote text or provider credentials.
                with self.change:
                    self.sources = [
                        {**source.health(), "status": "error", "checkedAt": utcnow().isoformat(),
                         "error": "The discovery run could not complete."}
                        for source in SOURCES
                    ]
            finally:
                with self.change:
                    self.last_run = utcnow()
                    self.next_run = self.last_run + timedelta(hours=self.interval)
                    self.running = False
                    self._save()

    def _merge(self, reports):
        by_url = {row["id"]: row for row in self.reports}
        for row in reports:
            earlier = by_url.get(row["id"])
            if earlier and row.get("sourceDigest") == earlier.get("sourceDigest"):
                if not row["steps"]:
                    row["steps"] = earlier.get("steps", [])
                if not row.get("landmarkId") and earlier.get("evidenceNote") and earlier.get("landmarkId"):
                    for key in ("x", "y", "region", "landmarkId", "confidence", "locationSource", "evidenceNote"):
                        row[key] = earlier.get(key)
            by_url[row["id"]] = row
        ordered = sorted(by_url.values(), key=lambda row: row["publishedAt"] or "", reverse=True)
        self.reports = ordered[:REPORT_LIMIT]

    def bounty_worker(self):
        while True:
            with self.change:
                while not self.stopping and not self.bounty_requested and self.bounty_next_run > utcnow():
                    seconds = (self.bounty_next_run - utcnow()).total_seconds()
                    self.change.wait(max(0, min(60, seconds)))
                if self.stopping:
                    return
                self.bounty_requested = False
                self.bounty_running = True
            try:
                sources, reports = self.bounty_discovery(load_landmarks(self.public / "landmarks.json"))
                with self.change:
                    self.bounty_reports = merge_bounty_reports(self.bounty_reports, reports)
                    self.bounty_sources = sources
            except Exception:
                with self.change:
                    self.bounty_sources = [
                        row if row["status"] == "manual" else {**row, "status": "error",
                            "checkedAt": utcnow().isoformat(), "error": "Bounty Watch could not complete the run."}
                        for source in BOUNTY_SOURCES if (row := source.health())
                    ]
            finally:
                with self.change:
                    self.bounty_last_run = utcnow()
                    self.bounty_next_run = self.bounty_last_run + timedelta(hours=self.bounty_interval)
                    self.bounty_running = False
                    self._save()

    def stop(self):
        with self.change:
            self.stopping = True
            self.change.notify_all()

    def load_media(self, values):
        entry = values.get("entry")
        if not isinstance(entry,str) or len(entry) > 128:
            raise ValueError("Choose a map entry.")
        cached = self.media.describe(entry)
        if not cached:
            with self.change:
                rows = [*self.reports, *self.bounty_reports]
            self.media.sync(rows, limit=1, only=entry)
            cached = self.media.describe(entry)
        return {"media": cached}


class Handler(BaseHTTPRequestHandler):
    server_version = "LeonidaAtlas"
    sys_version = ""

    @property
    def atlas(self):
        return self.server.atlas

    def setup(self):
        super().setup()
        self.connection.settimeout(8)

    def log_message(self, format, *args):
        pass

    def _headers(self, status, content_type, size):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        shared_origin = votes.shared_origin(self.atlas.public)
        self.send_header("Content-Security-Policy", CSP + (" " + shared_origin if shared_origin else ""))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Connection", "close")
        self.end_headers()

    def _json(self, status, value):
        content = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(content))
        if self.command != "HEAD":
            self.wfile.write(content)

    def _trusted(self):
        hosts = self.headers.get_all("Host", [])
        port = self.server.server_port
        if len(hosts) != 1 or hosts[0].lower() not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return False
        origins = self.headers.get_all("Origin", [])
        site = self.headers.get("Sec-Fetch-Site")
        if site in ("cross-site", "same-site"):
            return False
        return origins in ([], [f"http://{hosts[0].lower()}"])

    def _path(self):
        try:
            url = urlsplit(self.path)
            if not url.scheme and not url.netloc and self.path.startswith("/"):
                return unquote(url.path, errors="strict")
        except ValueError:
            pass
        return ""

    def do_GET(self):
        if not self._trusted():
            self._json(HTTPStatus.FORBIDDEN, {"error": "This request must come from the local atlas."})
            return
        path = self._path()
        if path == "/api/state":
            self._json(HTTPStatus.OK, self.atlas.state())
        elif path == "/api/bounty/state":
            self._json(HTTPStatus.OK, self.atlas.bounty_state())
        elif path == "/api/media":
            entry = parse_qs(urlsplit(self.path).query).get("entry", [""])[0]
            self._json(HTTPStatus.OK, {"media": self.atlas.media.describe(entry)})
        elif path.startswith("/media/"):
            item = self.atlas.media.filepath(path[7:])
            if not item:
                self._json(HTTPStatus.NOT_FOUND, {"error":"Image unavailable."})
                return
            try:
                data = item[0].read_bytes()
            except OSError:
                self._json(HTTPStatus.NOT_FOUND, {"error":"Image unavailable."})
                return
            self._headers(HTTPStatus.OK, item[1], len(data))
            if self.command == "GET":
                self.wfile.write(data)
        elif path == "/api/position":
            self._json(HTTPStatus.OK, self.atlas.position())
        elif path == "/api/votes":
            try:
                query = parse_qs(urlsplit(self.path).query, max_num_fields=12)
                value = votes.handle_read(self.atlas.cache.parent, query.get("id", [""])[0],
                                          self.headers.get("X-Atlas-Player", ""))
                self._json(HTTPStatus.OK, value)
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        elif not path or path.startswith("/api/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
        else:
            self._static(path)

    do_HEAD = do_GET

    def _static(self, name):
        root = self.atlas.public.resolve()
        try:
            file = (root / (name.lstrip("/") or "index.html")).resolve()
            if not file.is_relative_to(root) or name.startswith("//"):
                raise FileNotFoundError
            if name in MAP_ASSETS and not file.is_file():
                asset_dir = self.atlas.cache.parent.resolve()
                file = (asset_dir / MAP_ASSETS[name]).resolve()
                if not file.is_relative_to(asset_dir):
                    raise FileNotFoundError
            asset = file.open("rb")
        except (OSError, ValueError):
            self._json(HTTPStatus.NOT_FOUND, {"error": "File not found."})
            return
        with asset:
            content_type = MIME_TYPES.get(file.suffix) or mimetypes.guess_type(file)[0]
            self._headers(HTTPStatus.OK, content_type or "application/octet-stream", file.stat().st_size)
            if self.command == "GET":
                while block := asset.read(128 * 1024):
                    self.wfile.write(block)

    def _request_json(self, limit=BODY_LIMIT):
        if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
            raise ValueError("Send an application/json request.")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdecimal() or len(lengths[0]) > 8:
            raise ValueError("Send a JSON object with a valid Content-Length.")
        size = int(lengths[0])
        if not 0 < size <= limit:
            raise ValueError(f"Send a JSON object of at most {limit} bytes.")
        try:
            body = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Send a valid JSON object.") from exc
        if not isinstance(body, dict):
            raise ValueError("Send a JSON object.")
        return body

    def do_POST(self):
        if not self._trusted():
            self._json(HTTPStatus.FORBIDDEN, {"error": "This request must come from the local atlas."})
            return
        path = self._path()
        routes = {
            "/api/media": self.atlas.load_media,
            "/api/settings": self.atlas.settings, "/api/provider": self.atlas.set_provider,
            "/api/provider/models": self.atlas.model_list, "/api/refresh": lambda _: self.atlas.refresh(),
            "/api/votes": lambda payload: votes.handle_write(self.atlas.cache.parent, payload),
            "/api/locate": self.atlas.locator.locate,
            "/api/position": self.atlas.set_position,
            "/api/bounty/settings": self.atlas.bounty_settings,
            "/api/bounty/refresh": lambda _: self.atlas.bounty_refresh(),
        }
        if path not in routes:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return
        try:
            output = routes[path](self._request_json(LOCATE_BODY_LIMIT if path == "/api/locate" else BODY_LIMIT))
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except TimeoutError:
            self._json(HTTPStatus.REQUEST_TIMEOUT, {"error": "The request timed out."})
        except GpsUnavailable as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
        except RuntimeError as exc:
            self._json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        else:
            self._json(HTTPStatus.ACCEPTED if path in ("/api/refresh", "/api/bounty/refresh") else HTTPStatus.OK,
                       output)


class LocalServer(ThreadingHTTPServer):
    def __init__(self, atlas, port=PORT):
        self.atlas = atlas
        super().__init__(("127.0.0.1", port), Handler)

    def handle_error(self, request, client_address):
        # Client disconnects and malformed requests do not need a traceback.
        pass


def main():
    atlas = Atlas()
    with LocalServer(atlas) as server:
        worker = Thread(target=atlas.worker, daemon=True, name="atlas-discovery")
        bounty_worker = Thread(target=atlas.bounty_worker, daemon=True, name="atlas-bounty-watch")
        worker.start()
        bounty_worker.start()
        print(f"Leonida Loot Atlas: http://127.0.0.1:{PORT}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            atlas.stop()
            worker.join(timeout=2)
            bounty_worker.join(timeout=2)


if __name__ == "__main__":
    main()
