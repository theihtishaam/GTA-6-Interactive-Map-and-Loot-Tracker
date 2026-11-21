"""Discover and rank new public GTA VI feeds through bounded, anonymous search."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
from http import client
from ipaddress import ip_address
from queue import Empty, Queue
import re
import socket
import ssl
from threading import BoundedSemaphore, Thread, Timer
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

from discovery import (
    GAME, LAUNCH, NOISE, OLDER_GAME, SOURCES, USER_AGENT, Source,
    iso_date, make_report, parse_feed, plain,
)

DNS_SLOTS = BoundedSemaphore(12)
TLS = ssl.create_default_context()
MAX_CANDIDATES = 8
MAX_URL_SIZE = 2000
INDEX_TOPICS = (
    '("collectibles" OR "headphones" OR "earbuds" OR "duffel bag")',
    '("bank vaults" OR "heists" OR "bounties" OR "gloves" OR "loot")',
    '("mission walkthrough" OR "story mission" OR "side mission" OR "walkthrough")',
)
INDEX_BASE = "https://news.google.com/rss/search?"
HOSTNAME = re.compile(r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")
PRIVATE_PARAMETERS = {
    "token", "access_token", "auth", "api_key", "apikey", "secret", "client_secret",
    "key", "password", "signature", "sig", "x-amz-credential", "x-amz-security-token", "x-amz-signature",
}
TOPIC = re.compile(
    r"\b(?:bank\w*|bount\w*|collect\w*|headphones?|earbuds?|duffel|"
    r"heist\w*|loot|reward\w*|gloves?|equipment|secret\w*|treasure|mission\w*|walkthroughs?)\b",
    re.I,
)
NETWORK_FAILURE = (OSError, ValueError, client.HTTPException, ElementTree.ParseError)


@dataclass(frozen=True)
class PublicResponse:
    url: str
    body: bytes
    content_type: str = ""


def site_key(url):
    return urlsplit(url).hostname.removeprefix("www.")


FIXED_SITES = {site_key(source.url) for source in SOURCES}


def web_url(value):
    if (
        not isinstance(value, str) or not value.isascii() or len(value) > MAX_URL_SIZE or "\\" in value
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError("Invalid public destination.")
    url = urlsplit(value)
    host = url.hostname or ""
    if (
        url.scheme != "https" or url.port not in (None, 443) or url.username is not None
        or not HOSTNAME.fullmatch(host) or host.endswith((".local", ".localhost", ".internal", ".onion"))
        or any(key.lower() in PRIVATE_PARAMETERS for key, _ in parse_qsl(url.query, keep_blank_values=True))
    ):
        raise ValueError("Only public HTTPS hostnames are supported.")
    return urlunsplit(("https", host, url.path or "/", url.query, ""))


def is_public_address(value):
    address = ip_address(value)
    return (
        address.is_global and not address.is_multicast and not address.is_reserved
        and not getattr(address, "ipv4_mapped", None)
        and not getattr(address, "sixtofour", None)
        and not getattr(address, "teredo", None)
        and not str(address).startswith("64:ff9b:")
    )


def remaining(deadline):
    seconds = deadline - monotonic()
    if seconds <= 0:
        raise TimeoutError("Public request exceeded its deadline.")
    return seconds


def dns_addresses(host, deadline):
    seconds = min(remaining(deadline), 3)
    if not DNS_SLOTS.acquire(timeout=seconds):
        raise TimeoutError("DNS capacity exhausted.")
    result = Queue(maxsize=1)

    def resolve():
        try:
            records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
            result.put(tuple(dict.fromkeys(record[4][0] for record in records)))
        except OSError as exc:
            result.put(exc)
        finally:
            DNS_SLOTS.release()

    Thread(target=resolve, daemon=True).start()
    try:
        value = result.get(timeout=min(remaining(deadline), 3))
    except Empty:
        raise TimeoutError("DNS lookup exceeded its deadline.") from None
    if isinstance(value, Exception):
        raise value
    return value


class PinnedConnection(client.HTTPSConnection):
    def __init__(self, host, address, deadline):
        super().__init__(host, port=443, context=TLS, timeout=remaining(deadline))
        self.address = address

    def connect(self):
        address = ip_address(self.address)
        sock = socket.socket(socket.AF_INET if address.version == 4 else socket.AF_INET6)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.address, 443))
            if ip_address(sock.getpeername()[0]) != address:
                raise ValueError("Peer address changed.")
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def stop_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def request_once(url, address, deadline, max_size):
    parts = urlsplit(url)
    target = parts.path + ("?" + parts.query if parts.query else "")
    with_connection = PinnedConnection(parts.hostname, address, deadline)
    timer = None
    try:
        with_connection.connect()
        timer = Timer(remaining(deadline), stop_socket, args=(with_connection.sock,))
        timer.daemon = True
        timer.start()
        with_connection.request("GET", target, headers={
            "User-Agent": USER_AGENT, "Connection": "close", "Accept-Encoding": "identity",
            "Accept": "application/rss+xml, application/atom+xml, text/html, application/xml",
        })
        with with_connection.getresponse() as response:
            if response.status in {301, 302, 303, 307, 308}:
                return response.getheader("Location"), None
            if response.status != 200:
                raise ValueError(f"Publisher returned HTTP {response.status}.")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Unsupported content encoding.")
            size = response.getheader("Content-Length")
            if size and int(size) > max_size:
                raise ValueError("Response exceeded the size limit.")
            body = bytearray()
            while len(body) <= max_size:
                remaining(deadline)
                chunk = response.read1(min(32_768, max_size + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
            if len(body) > max_size:
                raise ValueError("Response exceeded the size limit.")
            return None, PublicResponse(url, bytes(body), response.getheader("Content-Type", ""))
    finally:
        if timer:
            timer.cancel()
        with_connection.close()


def fetch_public(url, *, timeout=5, max_size=1_250_000, resolver=dns_addresses, requester=request_once):
    """Read a bounded public response with fresh DNS validation for every hop."""
    endpoint = web_url(url)
    deadline = monotonic() + timeout
    visited = set()
    for _ in range(4):
        if endpoint in visited:
            raise ValueError("Redirect loop.")
        visited.add(endpoint)
        host = urlsplit(endpoint).hostname
        addresses = tuple(resolver(host, deadline))
        if not addresses or not all(is_public_address(address) for address in addresses):
            raise ValueError("DNS answer contained an unsupported destination.")
        # Prefer IPv4 when available because many desktop networks lack working IPv6.
        address = min(addresses, key=lambda value: ip_address(value).version)
        location, result = requester(endpoint, address, deadline, max_size)
        if result is not None:
            return result
        if not location:
            raise ValueError("Redirect missing a public destination.")
        endpoint = web_url(urljoin(endpoint, location))
    raise ValueError("Redirect limit reached.")


class FeedLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.wordpress = False

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        rel = (fields.get("rel") or "").lower().split()
        if tag == "link" and "https://api.w.org/" in rel:
            self.wordpress = True
        if tag == "meta" and (fields.get("name") or "").lower() == "generator":
            self.wordpress |= "wordpress" in (fields.get("content") or "").lower()
        if (tag == "link" and "alternate" in rel and fields.get("href")
                and "comments" not in (fields.get("title") or "").lower()
                and (fields.get("type") or "").split(";")[0].strip().lower()
                in {"application/rss+xml", "application/atom+xml", "application/rdf+xml"}):
            self.links.append(fields["href"])


@dataclass
class Candidate:
    homepage: str
    name: str
    discovered_from: str
    newest: datetime | None = None
    hits: int = 0
    feed_url: str | None = None
    last_qualified_at: str | None = None

    @property
    def id(self):
        return "auto-" + sha256(site_key(self.homepage).encode()).hexdigest()[:16]

    def health(self, now):
        return {
            **Source(self.id, self.name, self.feed_url or self.homepage).health(),
            "sourceType": "feed", "homepage": self.homepage, "feedUrl": self.feed_url,
            "discoveredFrom": self.discovered_from,
            "provenance": {"index": self.discovered_from, "publisher": self.homepage},
            "checkedAt": now.isoformat(), "qualified": False, "score": 0,
            "rankReason": "No usable feed checked.", "lastQualifiedAt": self.last_qualified_at,
        }


def index_url(topic):
    return INDEX_BASE + urlencode({
        "q": f'("GTA 6" OR "GTA VI") {topic} after:{LAUNCH.date().isoformat()}',
        "hl": "en-US", "gl": "US", "ceid": "US:en",
    })


def index_candidates(snapshot, endpoint, now):
    raw = snapshot.body
    if b"\0" in raw or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I):
        raise ValueError("Unsupported discovery index declaration.")
    root = ElementTree.fromstring(raw)
    if root.tag != "rss":
        raise ValueError("Unrecognized discovery index.")
    for item in root.findall("./channel/item")[:80]:
        title = plain(item.findtext("title"))
        published = iso_date(item.findtext("pubDate"))
        publisher = item.find("source")
        if (
            publisher is None or not published or not LAUNCH <= published <= now
            or not GAME.search(title) or not TOPIC.search(title) or NOISE.search(title)
            or OLDER_GAME.search(title)
        ):
            continue
        try:
            homepage = web_url(publisher.get("url"))
        except ValueError:
            continue
        home = urlsplit(homepage)
        homepage = urlunsplit((home.scheme, home.netloc, "/", "", ""))
        if site_key(homepage) not in FIXED_SITES | {"news.google.com", "google.com"}:
            yield Candidate(homepage, plain(publisher.text)[:100] or home.hostname,
                            endpoint, published, 1), title


def previous_candidates(previous, index_urls):
    for row in previous:
        if not isinstance(row, dict) or row.get("sourceType") != "feed":
            continue
        try:
            homepage = web_url(row.get("homepage"))
            feed = web_url(row.get("feedUrl"))
        except ValueError:
            continue
        last_qualified = iso_date(row.get("lastQualifiedAt"))
        provenance = row.get("discoveredFrom")
        if not last_qualified or provenance not in index_urls or site_key(homepage) in FIXED_SITES:
            continue
        candidate = Candidate(homepage, plain(row.get("name"))[:100], provenance,
                              feed_url=feed, last_qualified_at=last_qualified.isoformat())
        if candidate.id == row.get("id"):
            yield candidate


def inspect_index(endpoint, number, fetcher, now):
    health = {
        **Source(f"auto-index-{number}", "Public news search " + str(number), endpoint).health(),
        "sourceType": "index", "checkedAt": now.isoformat(),
    }
    try:
        candidates = list(index_candidates(fetcher(endpoint, timeout=5), endpoint, now))
        health.update(status="ok", seen=len(candidates), matched=0)
        return health, candidates
    except NETWORK_FAILURE:
        health.update(status="error", error="Public discovery index did not return usable results.")
        return health, []


def feed_links(homepage, fetcher, deadline):
    snapshot = fetcher(homepage, timeout=min(4, remaining(deadline)), max_size=1_000_000)
    parser = FeedLinks()
    parser.feed(snapshot.body.decode("utf-8", errors="replace"))
    links = []
    if parser.wordpress:
        links.append("/?" + urlencode({"s": "GTA 6", "feed": "rss2"}))
    links.extend(parser.links)
    if not links:
        links.extend(("/feed/", "/rss.xml"))
    found = []
    for link in links:
        try:
            url = web_url(urljoin(snapshot.url, link))
        except ValueError:
            continue
        if url not in found:
            found.append(url)
        if len(found) >= 2:
            break
    return found


def inspect_candidate(candidate, fetcher, landmarks, now):
    health = candidate.health(now)
    deadline = monotonic() + 11
    feeds = [candidate.feed_url] if candidate.feed_url else []
    if not feeds:
        try:
            feeds = feed_links(candidate.homepage, fetcher, deadline)
        except NETWORK_FAILURE:
            feeds = [urljoin(candidate.homepage, "/feed/")]
    if not feeds:
        health.update(status="error", error="No public RSS or Atom link was found.")
        return health, []

    best = None
    for url in feeds:
        try:
            response = fetcher(url, timeout=min(4, remaining(deadline)), max_size=1_250_000)
            if b"\0" in response.body:
                raise ValueError("Unsupported feed encoding.")
            items = parse_feed(response.body)
            site = Source(candidate.id, candidate.name, candidate.homepage)
            accepted = {}
            for item in items:
                if not item[2]:
                    continue
                published = iso_date(item[3])
                if not published or published > now:
                    continue
                try:
                    resolved = web_url(urljoin(response.url, item[2]))
                except ValueError:
                    continue
                if not resolved or site_key(resolved) != site_key(candidate.homepage):
                    continue
                report = make_report(site, (*item[:2], resolved, *item[3:]), landmarks)
                if report:
                    report.update(sourceId=site.id, discoveredVia=candidate.discovered_from)
                    prior = accepted.get(report["source"])
                    if not prior or report["publishedAt"] > prior["publishedAt"]:
                        accepted[report["source"]] = report
            reports = list(accepted.values())
            fresh = sum(iso_date(report["publishedAt"]) >= now - timedelta(hours=72) for report in reports)
            older = len(reports) - fresh
            score = 5 * fresh + 2 * older
            if best is None or score > best[0]:
                best = (score, fresh, older, len(items), response.url, reports)
        except NETWORK_FAILURE:
            if url == candidate.feed_url:
                try:
                    feeds.extend(feed for feed in feed_links(candidate.homepage, fetcher, deadline)
                                 if feed != candidate.feed_url)
                except NETWORK_FAILURE:
                    pass
            continue
    if best is None:
        health.update(status="error", error="No readable public RSS or Atom feed responded.")
        return health, []

    score, fresh, older, seen, feed_url, reports = best
    newest = max((report["publishedAt"] for report in reports), default=None)
    health.update(
        status="ok", seen=seen, matched=len(reports), url=feed_url, feedUrl=feed_url,
        byCategory=dict(Counter(row["category"] for row in reports)),
        score=score, qualified=bool(reports), latestMatchAt=newest,
        lastQualifiedAt=now.isoformat() if reports else candidate.last_qualified_at,
        rankReason=f"{fresh} accepted in 72 hours × 5 + {older} older accepted × 2."
        if reports else "No entries passed the GTA VI report gate.",
    )
    return health, reports


def discover_resources(landmarks, *, previous=(), now=None, limit=6, fetcher=fetch_public):
    """Return ranked source health rows and deduplicated, gate-approved reports."""
    now = now or datetime.now(timezone.utc)
    limit = max(1, min(limit, MAX_CANDIDATES))
    endpoints = tuple(index_url(topic) for topic in INDEX_TOPICS)
    with ThreadPoolExecutor(max_workers=len(endpoints)) as executor:
        index_results = list(executor.map(
            lambda pair: inspect_index(pair[1], pair[0], fetcher, now), enumerate(endpoints, 1),
        ))
    candidates = {}
    for _, result in index_results:
        for candidate, title in result:
            key = site_key(candidate.homepage)
            if key not in candidates:
                candidates[key] = (candidate, {title})
                continue
            previous_candidate, titles = candidates[key]
            titles.add(title)
            previous_candidate.hits = len(titles)
            previous_candidate.newest = max(previous_candidate.newest, candidate.newest)

    retained = sorted(previous_candidates(previous, endpoints), key=lambda row: row.last_qualified_at, reverse=True)
    shortlist = sorted((row for row, _ in candidates.values()), key=lambda row: (
        row.hits, row.newest, row.homepage,
    ), reverse=True)
    checks = {}
    for row in (*retained[:max(1, limit // 2)], *shortlist, *retained):
        checks.setdefault(site_key(row.homepage), row)
        if len(checks) >= min(MAX_CANDIDATES, limit + 2):
            break
    if checks:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(
                lambda row: inspect_candidate(row, fetcher, landmarks, now), checks.values(),
            ))
    else:
        results = []
    results.sort(key=lambda item: (
        -item[0]["score"],
        -iso_date(item[0]["latestMatchAt"]).timestamp() if item[0].get("latestMatchAt") else 0,
        item[0]["homepage"],
    ))
    selected = results[:limit]
    health_rows = [health for health, _ in selected] + [health for health, _ in index_results]
    reports = {}
    for _, approved in selected:
        for report in approved:
            reports.setdefault(report["source"], report)
    return health_rows, list(reports.values())
