"""Cache small source-linked gameplay images locally, independently of AI."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from threading import Lock
from time import time
from urllib.parse import urljoin, urlsplit

from resource_discovery import NETWORK_FAILURE, fetch_public, site_key, web_url

ARTICLE_HOSTS = {"www.powerpyx.com", "www.pushsquare.com", "www.gamesradar.com", "www.pcgamer.com"}
IMAGE_HOSTS = ARTICLE_HOSTS | {"images.pushsquare.com", "cdn.mos.cms.futurecdn.net"}
MAX_IMAGE = 3_500_000
MAX_CACHE = 32_000_000
ID = re.compile(r"[a-f0-9]{64}")
EXT = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
GENERIC = re.compile(r"(?:wallpaper|placeholder|default[-_]?image|brand[-_]?logo|favicon)", re.I)
NO_SUBJECT = {"https","uploads","www","location","locations","guide","guides","grand","theft","auto","gta","how","all","map","image","jpg","png","small","webp","walkthrough","screenshot"}


def approved(url, hosts):
    try:
        u = urlsplit(url)
        return u.scheme == "https" and u.hostname in hosts and u.port in (None, 443) and not (u.username or u.password)
    except (TypeError, ValueError):
        return False


def article_allowed(record):
    if approved(record.get("source"), ARTICLE_HOSTS):
        return True
    if str(record.get("sourceId", "")).startswith("auto-") and record.get("discoveredVia"):
        try:
            return bool(web_url(record.get("source")))
        except ValueError:
            pass
    return False


def image_bytes(url, **options):
    return fetch_public(url, **options).body


class PreviewTag(HTMLParser):
    def __init__(self):
        super().__init__()
        self.image = ""
        self.inline = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "img" and len(self.inline) < 60:
            self.inline.append(values.get("data-lazy-src") or values.get("data-src") or values.get("src") or "")
        if tag == "meta" and not self.image:
            if (values.get("property") or values.get("name")) in ("og:image", "twitter:image"):
                self.image = values.get("content") or ""

    def choose(self, page):
        def terms(s):
            return {t.rstrip("s") for t in re.findall("[a-z]{3,}",s.lower()) if t not in NO_SUBJECT}
        subject = terms(urlsplit(page).path)
        candidates = []
        for src in self.inline:
            name = urlsplit(src).path.rsplit("/",1)[-1]
            if re.search(r"gta[-_]?6",name,re.I) and not GENERIC.search(name):
                hits = subject & terms(name)
                if hits:
                    candidates.append((len(hits),src))
        if candidates:
            return max(candidates, key=lambda c:c[0])[1], "Guide illustration"
        return (self.image, "Article preview") if self.image and not GENERIC.search(self.image) else ("", "")


def image_type(raw):
    if raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9"):
        return "jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and raw[12:16] == b"IHDR" and raw[-8:-4] == b"IEND":
        return "png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" and int.from_bytes(raw[4:8], "little") + 8 == len(raw):
        return "webp"
    raise ValueError("The source did not return a supported image.")


def public_media(row):
    return {key: row[key] for key in ("image", "source", "caption", "path")}


class MediaCache:
    def __init__(self, directory, public, fetcher=image_bytes):
        self.directory, self.public, self.fetcher = directory, public, fetcher
        self.lock, self.run_lock = Lock(), Lock()
        self.index_path = directory / "index.json"
        try:
            saved = json.loads(self.index_path.read_text("utf8"))
            self.items = saved if isinstance(saved, dict) else {}
        except (OSError, ValueError):
            self.items = {}

    def catalog(self):
        result = {}
        for file in ("guides.json", "collectible-guides.json"):
            try:
                for row in json.loads((self.public / file).read_text("utf8")):
                    result[row["id"]] = row
            except FileNotFoundError:
                continue
        for id_, position in json.loads((self.public / "guide-positions.json").read_text("utf8")).items():
            if id_ in result and not result[id_].get("sourceImage"):
                result[id_] = {**result[id_], **position}
        return list(result.values())

    def describe(self, id_):
        with self.lock:
            row = self.items.get(id_, {})
            return public_media(row) if row.get("path") and not GENERIC.search(row.get("image","")) else None

    def filepath(self, name):
        digest, dot, ext = name.partition(".")
        if not dot or not ID.fullmatch(digest) or ext not in EXT:
            return None
        return self.directory / name, EXT[ext]

    def _one(self, record):
        page = record.get("locationSource") if record.get("sourceImage") else record.get("source")
        page = page or record.get("source")
        if not article_allowed(record) or not (page == record.get("source") or approved(page, ARTICLE_HOSTS)):
            return None
        image = record.get("sourceImage")
        caption = "Source screenshot"
        try:
            if not image:
                html = self.fetcher(page, timeout=5, max_size=1_500_000)
                parser = PreviewTag()
                parser.feed(html.decode("utf8", "ignore"))
                image, caption = parser.choose(page)
                if not image:
                    raise ValueError("No source image")
                image = urljoin(page, image)
            image = web_url(image)
            if not approved(image, IMAGE_HOSTS) and site_key(image) != site_key(page):
                raise ValueError("Unsupported image host")
            raw = self.fetcher(image, timeout=6, max_size=MAX_IMAGE)
            ext = image_type(raw)
            digest = sha256(raw).hexdigest()
            name = digest + "." + ext
            self.directory.mkdir(parents=True, exist_ok=True)
            with self.lock:
                target = self.directory / name
                if not target.is_file():
                    tmp = self.directory / (digest + ".part")
                    tmp.write_bytes(raw)
                    tmp.replace(target)
            return {"path": "/media/" + name, "image": image, "source": page, "checked": time(),
                    "caption": caption}
        except NETWORK_FAILURE:
            return {"checked": time()}

    def sync(self, reports, limit=6, only=None):
        if not self.run_lock.acquire(blocking=False):
            return
        try:
            catalog = self.catalog()
            rows = list({r["id"]: r for r in [*reports, *catalog]}.values())
            if only is not None:
                rows = [r for r in rows if r["id"] == only]
            now = time()
            with self.lock:
                def eligible(r):
                    old = self.items.get(r["id"], {})
                    if old.get("path") and GENERIC.search(old.get("image","")):
                        return True
                    return not old.get("path") and now - old.get("checked", 0) >= 86400
                queue = [r for r in rows if eligible(r) and article_allowed(r)]
            # Reserve capacity for precise guide screenshots on every pass.
            precise = [r for r in queue if r.get("sourceImage")]
            leads = [r for r in queue if not r.get("sourceImage")]
            chosen = (precise[:max(1,limit//2)] + leads[:max(1,limit//2)])
            seen = {r["id"] for r in chosen}
            chosen.extend(r for r in queue if r["id"] not in seen)
            chosen = chosen[:limit]
            if not chosen: return
            with ThreadPoolExecutor(max_workers=3) as pool:
                results = list(pool.map(self._one, chosen))
            with self.lock:
                for r, value in zip(chosen, results):
                    if value: self.items[r["id"]] = value
                self.directory.mkdir(parents=True, exist_ok=True)
                files = sorted((p for p in self.directory.iterdir() if p.suffix[1:] in EXT),
                               key=lambda p:p.stat().st_mtime)
                size = sum(p.stat().st_size for p in files)
                for p in files:
                    if size <= MAX_CACHE: break
                    size -= p.stat().st_size
                    p.unlink(missing_ok=True)
                    for item in self.items.values():
                        if item.get("path") == "/media/" + p.name:
                            item.pop("path", None)
                self.items = dict(sorted(self.items.items(), key=lambda pair:pair[1].get("checked",0), reverse=True)[:1000])
                tmp = self.index_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.items), encoding="utf8")
                tmp.replace(self.index_path)
        finally:
            self.run_lock.release()

