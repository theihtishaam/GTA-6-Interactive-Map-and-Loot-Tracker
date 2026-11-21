"""Bounded anonymous discovery from public APIs and syndication feeds."""

from collections import Counter
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

USER_AGENT = "GTA6MapLoot/0.1.3 (https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker)"
LAUNCH = datetime(2026, 11, 19, tzinfo=timezone.utc)
REVIEW_EMBARGO = LAUNCH.replace(day=18)
LIMIT = 35
GAME = re.compile(r"\b(?:gta\s*(?:6|vi)|grand theft auto\s*(?:6|vi))\b", re.I)
OLDER_GAME = re.compile(r"\b(?:gta online|gta\s*(?:5|v|iv)|vice city stories)\b", re.I)
NOISE = re.compile(
    r"\b(?:rumou?r\w*|wish\s*list|speculat\w*|fan concept|leak\w*|release date|how to download|"
    r"pc port|cracks?|giveaways?|spoiler policy|patch notes|pre[ -]?order|pre[ -]?load|"
    r"cheats?|datamin\w*|deal(?:s)?|collector['’]s (?:box|edition)|discount(?:s)?|"
    r"release times?|review bombing|game awards|bug bount(?:y|ies))\b",
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
    ("reward", r"rewards?|loot|unlocks?|secret (?:cash )?stash(?:es)?|hidden (?:cash|money)|"
               r"all equipment|style rewards?|open the safe|free (?:early-game )?weapons?"),
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
MISSION_HEADLINE = re.compile(r"\bwalkthrough\b|\bhow to (?:complete|finish|start)\b", re.I)
MISSION_BODY = re.compile(
    r"\b(?:main (?:story )?mission|optional mission|side mission|main quest|side quest|"
    r"chapter\s+[1-9]\s+(?:mission|job)|(?:this|the|your) mission)\b|\bstarting location\s*:",
    re.I,
)
MISSION_TASK = re.compile(
    r"\b(?:bring|choose|collect|complete|escape|find|finish|follow|get|head|help|"
    r"look for|meet|pick up|reach|return|start|take|visit|walk|wait)\b",
    re.I,
)
MISSION_ROUNDUP = re.compile(
    r"\b(?:full (?:story )?walkthrough|all (?:\d+ )?(?:main |story |side )?(?:missions|guides|quests)|"
    r"(?:mission|quest) list|story (?:mode guide|walkthrough)|missions and walkthroughs|"
    r"every (?:main |story |side )?(?:mission|quest)|(?:both|two|three) (?:chapter\s+\d+\s+)?"
    r"(?:missions|quests)|chapters? explained|how long)\b|"
    r"100%\s+completion (?:checklist|guide)",
    re.I,
)
NON_MISSION_WALKTHROUGH = re.compile(
    r"\b(?:collectibles? and secrets|collectibles?\s*&\s*secrets|collectible locations|"
    r"card (?:sets?|locations?)|review|tips and tricks|inventory|gear guide|farming)\b", re.I,
)
START_FIELD = re.compile(
    r"\bstarting location:\s*(.{1,110}?)(?=\s+(?:chapter|quest giver|requirement|"
    r"can be started by|reward|quest description|objectives)\s*:|[.;]|$)",
    re.I,
)
START_STATEMENT = re.compile(r"\bstart(?:s|ing)?\s+(?:at|inside|in|near)\s+[^.!?]{2,100}", re.I)
CHAPTER = re.compile(r"\bchapter\s*:\s*(?:chapter\s*)?([1-9])\b|\bchapter\s+([1-9])\s+mission\b", re.I)
CHARACTER = re.compile(r"\bcan be started by:\s*(Jason(?:\s*/\s*Lucia)?|Lucia(?:\s*/\s*Jason)?)\b", re.I)
PREREQUISITE = re.compile(r"\brequirements?:\s*(.{1,160}?)(?=\s+(?:can be started by|reward|quest description|"
                          r"objectives|starting location)\s*:|$)", re.I)


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
    coverage: str = ""

    def health(self):
        return {
            "id": self.id, "name": self.name, "url": self.url, "status": "pending",
            "checkedAt": None, "seen": 0, "matched": 0, "error": None,
            "coverage": self.coverage, "byCategory": {},
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
    Source("powerpyx-missions", "PowerPyx mission walkthroughs", powerpyx_feed("Walkthrough"), launch_guides=True,
           coverage="Search feed for GTA 6 walkthroughs. Named mission starts are used where the feed provides them."),
    Source("gtaboom", "GTA BOOM guides", "https://www.gtaboom.com/feed.xml", launch_guides=True,
           coverage="Publisher RSS for mission walkthroughs, collectibles and other leads."),
    Source("pushsquare", "Push Square guides", "https://www.pushsquare.com/feeds/guides", launch_guides=True,
           coverage="Published PlayStation guides, screened for GTA VI gameplay."),
    Source("collectibles-map", "GTA6 Collectibles Map articles", "https://gta6collectiblesmap.com/feed.xml",
           game_specific=True, coverage="Specialist collectible and reward articles. Broad and derivative coverage stays a lead."),
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


def mission_name(title):
    part = re.search(r"\bwalkthrough\s*\(\s*part\s+\d+\s+of\s+\d+\s*\)\s*:\s*(.+)$", title, re.I)
    if part:
        return part[1].strip()
    name = re.sub(r"^\s*(?:guide\s*:\s*)?(?:GTA\s*(?:6|VI)|Grand Theft Auto VI)\s*[:–—-]?\s*", "", title, flags=re.I)
    name = re.split(r"\bwalkthrough\b", name, maxsplit=1, flags=re.I)[0].strip(" :–—-")
    name = re.sub(r"^how to (?:complete|finish|start)\s+|\s+in GTA\s*(?:6|VI)$", "", name, flags=re.I)
    return name.strip(" :–—-") if len(name.strip()) >= 3 else ""


def individual_mission(source, title, excerpt, url):
    if (not MISSION_HEADLINE.search(title) or MISSION_ROUNDUP.search(title)
            or MISSION_ROUNDUP.search(excerpt[:180]) and re.search(r"\b(?:both|two|three)\b", excerpt[:100], re.I)
            or NON_MISSION_WALKTHROUGH.search(title) or not mission_name(title)
            or len(excerpt) < 45):
        return False
    if MISSION_BODY.search(excerpt) and MISSION_TASK.search(excerpt):
        return True
    # This publisher puts the mission format in the canonical article slug
    # while supplying a short, objective-focused description in its feed.
    parsed = urlsplit(url)
    return (source.id == "gtaboom" and parsed.hostname == "www.gtaboom.com"
            and bool(re.fullmatch(r"/gta-6-[a-z0-9-]+-walkthrough-[a-f0-9]{4}/?", parsed.path))
            and bool(MISSION_TASK.search(excerpt)))


def mission_context(title, excerpt, landmarks):
    fields = {"missionName": mission_name(title)}
    chapter = CHAPTER.search(excerpt)
    character = CHARACTER.search(excerpt)
    prereq = PREREQUISITE.search(excerpt)
    if chapter:
        fields["chapter"] = int(chapter[1] or chapter[2])
    if character:
        fields["character"] = character[1]
    if prereq:
        fields["prerequisite"] = prereq[1].strip()[:145]
    start = START_FIELD.search(excerpt)
    if start:
        label = start[1].strip()
        fields["startingLocation"] = label
        # Region names and route destinations in objectives must not be picked as the starting venue.
        venue = label.rsplit(">", 1)[-1].strip()
        matches = [place for place in landmarks if place.get("nameOrigin", "game") == "game"
                   and place.get("type") not in ("natural", "region", "district")
                   and normalize_venue(place["title"]).casefold() == normalize_venue(venue).casefold()]
        return fields, matches[0] if len(matches) == 1 else None
    statement = START_STATEMENT.search(excerpt)
    place = source_venue("", statement[0], landmarks) if statement else None
    return fields, place


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
    # Generic mission indexes stay on the publisher's site rather than becoming individual activities.
    if MISSION_ROUNDUP.search(title):
        return None
    mission = individual_mission(source, title, excerpt, url)
    category = "mission" if mission else next((name for name, pattern in CATEGORIES if pattern.search(title)), None)
    if not category or (not mission and not ACTION.search(combined)):
        return None
    # Multi-location guides stay searchable as leads instead of representing the guide with one arbitrary pin.
    multi_venue = re.search(
        r"\b(?:all|every|each)\b.*\b(?:locations?|stores?|vaults?|sets?|collectibles?)\b|"
        r"\b(?:[2-9]|[1-9]\d+|two|three|four|five|six|seven|eight|nine|ten)\s+(?:early\s+)?"
        r"(?:pickups?|stashes|positions?|locations?)\b", title, re.I,
    )
    mission_fields, place = mission_context(title, excerpt, landmarks) if mission else (
        {}, None if multi_venue else source_venue(title, excerpt, landmarks)
    )
    report = {
        "id": sha256(url.encode()).hexdigest()[:24],
        "title": title, "category": category,
        "region": place["region"] if place else mission_fields.get("startingLocation", "Unresolved"),
        "x": place["x"] if place else None, "y": place["y"] if place else None,
        "source": url, "sourceName": source.name, "details": excerpt[:160],
        "steps": [], "confidence": "area" if place else "lead",
        "publishedAt": published.isoformat(), "landmarkId": place["id"] if place else None,
        "_extract": excerpt, "sourceDigest": sha256(excerpt.encode()).hexdigest(), **mission_fields,
    }
    if mission and place:
        report["evidenceNote"] = "The guide names this starting venue. The exact mission prompt may be nearby."
    if place and place.get("source"):
        report["locationSource"] = place["source"]
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
        reports = {}
        for item in items:
            report = make_report(source, item, landmarks)
            if report:
                prior = reports.get(report["id"])
                if prior is None or report["publishedAt"] > prior["publishedAt"]:
                    reports[report["id"]] = report
    except (OSError, ValueError, KeyError, TypeError, ElementTree.ParseError) as exc:
        health.update(status="error", error=failure_message(exc))
        return health, []
    health.update(status="error" if issue else "ok", seen=len(items), matched=len(reports), error=issue,
                  byCategory=dict(Counter(row["category"] for row in reports.values())))
    return health, list(reports.values())


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
    unique = {}
    for _, reports in collected:
        for report in reports:
            unique.setdefault(report["id"], report)
    return [result[0] for result in collected], list(unique.values())


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

