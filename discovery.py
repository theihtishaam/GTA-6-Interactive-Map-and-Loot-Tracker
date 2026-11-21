"""Bounded anonymous discovery from public APIs and syndication feeds."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from xml.etree import ElementTree

USER_AGENT = "GTA6MapLoot/0.1.0 (https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker)"
LAUNCH = datetime(2026, 11, 19, tzinfo=timezone.utc)
REVIEW_EMBARGO = LAUNCH.replace(day=18)
LIMIT = 35
GAME = re.compile(r"\b(?:gta\s*(?:6|vi)|grand theft auto\s*(?:6|vi))\b", re.I)
OLDER_GAME = re.compile(r"\b(?:gta online|gta\s*(?:5|v|iv)|vice city stories)\b", re.I)
NOISE = re.compile(
    r"\b(?:rumou?r\w*|wish\s*list|speculat\w*|fan concept|leak\w*|release date|how to download|"
    r"pc port|cracks?|giveaways?|spoiler policy|patch notes|pre[ -]?order|pre[ -]?load|"
    r"cheats?|datamin\w*|deal(?:s)?|collector['’]s (?:box|edition)|discount(?:s)?)\b",
    re.I,
)
CATEGORIES = [
    ("earbuds", r"earbuds?|earphones?|headphones?|electronics stores?"),
    ("gloves", r"gloves?"),
    ("bag", r"duff(?:el|le)(?: bags?)?|backpacks?"),
    ("bounty", r"bount(?:y|ies)|wanted posters?|bail (?:bonds?|enforcement|office)|most wanted targets?"),
    ("heist", r"heists?|robbery|robberies|bank (?:jobs?|vaults?)|armou?red (?:trucks?|vans?)|"
              r"smash\s*['’]?n['’]?\s*grabs?|jewel(?:l)?ery jobs?"),
    ("collectible", r"collect[ia]bles?|easter eggs?|hidden packages?|flusher tags?|"
                    r"collectible cards?|secret playlists?|treasure (?:dives?|shipwrecks?)|waink scans?"),
    ("reward", r"rewards?|loot|unlocks?|secret stash(?:es)?|all equipment|style rewards?"),
    ("landmark", r"points? of interest|landmarks?"),
]
CATEGORIES = [(name, re.compile(r"\b(?:" + words + r")\b", re.I)) for name, words in CATEGORIES]
ACTION = re.compile(
    r"\b(?:found|discover\w*|unlock\w*|rewards?|loot|locations?|pick ?up|collect\w*|"
    r"get|drops?|guide|obtain\w*|complete\w*|pay\w*|hidden|claim\w*|map|"
    r"buy|bought|purchas\w*|scan\w*|available)\b",
    re.I,
)
LOCATION_ACTION = re.compile(
    r"\b(?:buy|bought|collect\w*|discover\w*|drop\w*|find|found|get|grab|hidden|look|loot|"
    r"obtain\w*|pick\s+up|purchas\w*|reward\w*|scan\w*|sell|start\w*|unlock\w*|"
    r"location|venue)\b",
    re.I,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(ProxyHandler({}), NoRedirect())


def fetch(url, *, headers=None, payload=None, timeout=6, max_size=1_000_000):
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        request_headers["Content-Type"] = "application/json"
    deadline = monotonic() + timeout
    result = bytearray()
    with OPENER.open(Request(url, data=data, headers=request_headers), timeout=timeout) as response:
        while len(result) <= max_size:
            if monotonic() >= deadline:
                raise TimeoutError("Endpoint exceeded the request timeout.")
            chunk = response.read1(min(64 * 1024, max_size + 1 - len(result)))
            if not chunk:
                break
            result.extend(chunk)
    if len(result) > max_size:
        raise ValueError("Response exceeded the size limit.")
    return bytes(result)


def failure_message(exc):
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code} from endpoint."
    if isinstance(exc, (OSError, URLError)):
        return "Network request failed or timed out."
    return "The endpoint returned an unreadable response."


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    url: str
    kind: str = "feed"
    game_specific: bool = False
    launch_guides: bool = False
    feed_urls: tuple[str, ...] = ()

    def health(self):
        return {
            "id": self.id, "name": self.name, "url": self.url, "status": "pending",
            "checkedAt": None, "seen": 0, "matched": 0, "error": None,
        }


SEARCH_QUERY = 'is:issue in:title "GTA VI" created:>=2026-11-19'


def powerpyx_feed(terms):
    return "https://www.powerpyx.com/?" + urlencode({"s": f'"GTA 6" "{terms}"', "feed": "rss2"})


SOURCES = (
    Source("github", "GitHub community issues", "https://github.com/search?" + urlencode({
        "q": SEARCH_QUERY, "type": "issues",
    }), "github"),
    Source("gta-how-forum", "GTA Forums (gta.how)",
           "https://gta.how/syndication.php?limit=15"),
    Source("gta6-how", "GTA6.how guides", "https://gta6.how/rss.xml", game_specific=True),
    Source("gamesradar", "GamesRadar+ RSS", "https://www.gamesradar.com/feeds.xml"),
    Source("powerpyx", "PowerPyx GTA VI guides",
           "https://www.powerpyx.com/guide/gta-6-grand-theft-auto-vi/",
           launch_guides=True, feed_urls=tuple(powerpyx_feed(topic) for topic in (
               "Bank Vault", "Collectible Card", "Electronics Stores", "All Equipment",
           ))),
    Source("pcgamer", "PC Gamer RSS", "https://www.pcgamer.com/feeds.xml", launch_guides=True),
)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored = True
        if tag in ("p", "br", "li", "div"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignored = False
        if tag in ("p", "li", "div"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def plain(value):
    if not isinstance(value, str):
        return ""
    parser = PlainText()
    parser.feed(value[:12_000])
    parser.close()
    return " ".join(unescape("".join(parser.parts)).split())


def iso_date(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            stamp = parsedate_to_datetime(value)
        except (ValueError, OverflowError, TypeError):
            return None
    stamp = stamp.replace(tzinfo=stamp.tzinfo or timezone.utc)
    return stamp.astimezone(timezone.utc)


def public_link(value):
    if not isinstance(value, str) or len(value) > 2_000 or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or not url.hostname or "." not in url.hostname
                or url.username is not None or url.password is not None or url.port not in (None, 443)):
            return None
    except ValueError:
        return None
    query = urlencode([
        (key, value) for key, value in parse_qsl(url.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "ref"}
    ])
    return urlunsplit(("https", url.hostname.lower(), url.path or "/", query, ""))


def parse_feed(raw, *, publisher_guides=False):
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I):
        raise ValueError("Unsupported feed declaration.")
    root = ElementTree.fromstring(raw)
    root_kind = root.tag.rsplit("}", 1)[-1]
    if root_kind not in ("rss", "feed", "RDF"):
        raise ValueError("Unrecognized feed format.")
    items = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        fields = {}
        for element in item:
            name = element.tag.rsplit("}", 1)[-1]
            if name == "link" and element.attrib.get("rel", "alternate") != "alternate":
                continue
            if name == "group":
                # Public YouTube Atom exposes the media description inside media:group.
                description = next((child for child in element if child.tag.rsplit("}", 1)[-1] == "description"), None)
                if description is not None:
                    fields.setdefault("description", "".join(description.itertext()))
            else:
                fields.setdefault(name, element.attrib.get("href") if name == "link" and element.attrib.get("href")
                                  else "".join(element.itertext()))
        full_text = fields.get("encoded") or fields.get("content")
        excerpt = fields.get("summary") or fields.get("description")
        items.append((fields.get("title"), (full_text or excerpt) if publisher_guides else (excerpt or full_text),
                      fields.get("link"),
                      fields.get("published") or fields.get("pubDate") or fields.get("date")
                      or fields.get("updated"), None))
        if len(items) >= LIMIT:
            break
    return items


def search_github(fetcher):
    response = []
    for query in (SEARCH_QUERY, SEARCH_QUERY.replace("GTA VI", "GTA 6")):
        url = "https://api.github.com/search/issues?" + urlencode({
            "q": query, "sort": "created", "order": "desc", "per_page": 15,
        })
        payload = json.loads(fetcher(url, headers={"Accept": "application/vnd.github+json"}))
        rows = payload["items"]
        if not isinstance(rows, list):
            raise ValueError("Invalid items response.")
        response.extend(
            (row.get("title"), row.get("body"), row.get("html_url"), row.get("created_at"),
             row.get("reactions"))
            for row in rows[:15] if isinstance(row, dict) and "pull_request" not in row
        )
    return response


def normalize_venue(value):
    return value.replace("’", "'").replace("–", "-").replace("—", "-")


@lru_cache(maxsize=4096)
def venue_pattern(title):
    return re.compile(
        r"(?:\b(?:at|inside|in|near|outside|under|behind|from|within)\s+(?:the\s+)?"
        r"|\b(?:location|venue):\s*)" + re.escape(normalize_venue(title)) + r"(?![\w'-])",
        re.I,
    )


def source_venue(title, excerpt, landmarks):
    sentences = re.split(r"(?<=[.!?])\s+|(?=\bLocation:)", excerpt)
    evidence = normalize_venue("\n".join([title, *(sentence for sentence in sentences
                                                     if LOCATION_ACTION.search(sentence))]))
    places = [
        place for place in landmarks
        if place.get("nameOrigin", "game") == "game" and venue_pattern(place["title"]).search(evidence)
    ]
    return places[0] if len(places) == 1 else None


def submitted_grid(excerpt):
    # This explicit frame tag distinguishes an atlas game position from ordinary number pairs.
    pairs = re.findall(r"\bATLAS_GTA6_GRID\s*=\s*\(\s*(-?\d{1,5}(?:\.\d+)?)\s*,\s*(-?\d{1,5}(?:\.\d+)?)\s*\)", excerpt, re.I)
    if len(pairs) != 1:
        return None
    x, y = map(float, pairs[0])
    if -10240 <= x <= 3584 and -8960 <= y <= 10496:
        return (x+10240)/13824, (10496-y)/19456
    return None


def make_report(source, item, landmarks):
    title, excerpt, url, published, reactions = item
    title = plain(title)[:180]
    excerpt = plain(excerpt)[:800]
    url = public_link(url)
    published = iso_date(published)
    combined = f"{title} {excerpt}"
    if not (url and title and published and published <= datetime.now(timezone.utc)):
        return None
    # The November 18 exception applies only to firsthand guide publishers and their own articles.
    first_day = REVIEW_EMBARGO if source.launch_guides and urlsplit(url).hostname == urlsplit(source.url).hostname else LAUNCH
    if (published < first_day
            or NOISE.search(title) or OLDER_GAME.search(title)
            or re.search(r"\b(?:could|might|will)\b.*\?", title, re.I)
            or not (source.game_specific or GAME.search(combined))):
        return None
    # The title itself has to identify a discovery topic to avoid incidental keyword mentions.
    category = next((name for name, pattern in CATEGORIES if pattern.search(title)), None)
    if not category or not ACTION.search(combined):
        return None
    # Multi-location guides stay searchable as leads instead of representing the guide with one arbitrary pin.
    multi_venue = re.search(r"\b(?:all|every|each)\b.*\b(?:locations?|stores?|vaults?|sets?)\b", title, re.I)
    place = None if multi_venue else source_venue(title, excerpt, landmarks)
    report = {
        "id": sha256(url.encode()).hexdigest()[:24],
        "title": title, "category": category, "region": place["region"] if place else "Unresolved",
        "x": place["x"] if place else None, "y": place["y"] if place else None,
        "source": url, "sourceName": source.name, "details": excerpt[:160],
        "steps": [], "confidence": "area" if place else "lead",
        "publishedAt": published.isoformat(), "landmarkId": place["id"] if place else None,
        "_extract": excerpt, "sourceDigest": sha256(excerpt.encode()).hexdigest(),
    }
    grid = submitted_grid(excerpt) if source.kind == "github" and not multi_venue else None
    if grid:
        report.update(x=grid[0],y=grid[1],confidence="reported",landmarkId=None,
                      region=place["region"] if place else "Leonida",evidenceNote="The reporter supplied these GTA VI grid coordinates.")
    if (source.kind == "github" and isinstance(reactions, dict)
            and all(type(reactions.get(key)) is int and reactions[key] >= 0 for key in ("+1", "-1"))):
        report["communityVotes"] = {"up": reactions["+1"], "down": reactions["-1"], "url": url}
    return report


def read_source(source, landmarks, fetcher):
    health = source.health()
    health["checkedAt"] = datetime.now(timezone.utc).isoformat()
    try:
        issue = None
        if source.kind == "github":
            items = search_github(fetcher)
        elif source.feed_urls:
            items, issue = read_guide_feeds(source, fetcher)
        else:
            items = parse_feed(fetcher(source.url, timeout=8), publisher_guides=source.launch_guides)
        reports = [report for item in items if (report := make_report(source, item, landmarks))]
    except (OSError, ValueError, KeyError, TypeError, ElementTree.ParseError) as exc:
        health.update(status="error", error=failure_message(exc))
        return health, []
    health.update(status="error" if issue else "ok", seen=len(items), matched=len(reports), error=issue)
    return health, reports


def read_guide_feeds(source, fetcher):
    items = {}
    failures = []
    for url in source.feed_urls:
        try:
            for item in parse_feed(fetcher(url, timeout=5, max_size=1_500_000), publisher_guides=True):
                link = public_link(item[2])
                if link:
                    items.setdefault(link, item)
        except (OSError, ValueError, ElementTree.ParseError) as exc:
            failures.append(failure_message(exc))
    status = f"{len(failures)} of {len(source.feed_urls)} feeds failed. {failures[0]}" if failures else None
    return list(items.values())[:LIMIT], status


def discover(landmarks, fetcher=fetch):
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        futures = [pool.submit(read_source, source, landmarks, fetcher) for source in SOURCES]
        collected = [future.result() for future in futures]
    return [result[0] for result in collected], [report for _, reports in collected for report in reports]


def load_landmarks(path):
    try:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    return [
        row for row in rows
        if isinstance(row, dict) and row.get("category") == "landmark" and public_link(row.get("source"))
        and all(isinstance(row.get(key), str) and row[key].strip() for key in ("id", "title", "region"))
        and all(type(row.get(axis)) in (int, float) and 0 <= row[axis] <= 1 for axis in ("x", "y"))
    ]

