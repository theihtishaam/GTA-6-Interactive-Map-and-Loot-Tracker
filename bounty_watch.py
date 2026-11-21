"""Anonymous, bounded GTA VI bounty coverage for the Bounty Watch."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

from discovery import GAME, OLDER_GAME, failure_message, fetch, make_report, parse_feed, plain, powerpyx_feed

TOPIC = re.compile(r"\b(?:bount(?:y|ies)|bail (?:bonds?|enforcement|office)|wanted posters?|most wanted targets?)\b", re.I)
UNRELATED = re.compile(
    r"\b(?:bug bount(?:y|ies)|bugcrowd|hackerone|CVE|giveaway|do(?:xing|xxing)|crypto|fortnite|"
    r"red dead(?: redemption)?|bounty chocolate|contest|real[- ]world|real[- ]life|role[- ]?play|"
    r"FiveM|mod(?:s|ded)|leak(?:ed|s)?|wish ?list|fan concept|speculat\w*|rumou?r\w*|"
    r"what if|prediction(?:s)?|my theory|alleged\w*|unverified|AI[- ]generated|"
    r"if Rockstar (?:adds|announces)|hope (?:Rockstar|they) (?:adds?|announce)|"
    r"could (?:eventually|someday))\b", re.I,
)
NO_FINDING = re.compile(
    r"\b(?:no (?:confirmed |actual |in-game )?(?:bount(?:y|ies)|wanted posters?)|never found|"
    r"(?:haven['’]t|hasn['’]t|couldn['’]t|can['’]t|didn['’]t) (?:find|confirm|locate|complete|unlock)"
    r"|not (?:yet )?(?:available|announced|confirmed|found)|not (?:currently )?in the game|"
    r"(?:bount(?:y|ies)|wanted posters?) (?:aren['’]t|don['’]t exist)|no evidence|no official word)\b", re.I,
)
GAME_CONTEXT = re.compile(r"\b(?:Leonida|Vice City|Jason|Lucia|chapter|mission|in[- ]game|pay(?:out|\s*\$)|"
                          r"map marker|wanted poster|bail office|bail bonds|target)\b", re.I)
OUTCOME = re.compile(
    r"\b(?:found|located|discovered|picked up|captured|caught|turned in|brought (?:back|in)|"
    r"handed (?:in|over)|delivered|arrested|completed|unlocked|paid|received|earned|"
    r"rewarded)\b", re.I,
)
PROCESS = re.compile(
    r"\b(?:collect|capture|arrest|turn in|hand in|track|deliver|claim|bring|unlocks?|"
    r"starts?|activates?|pays?|reward(?:ed)?|payout|chapter\s+\d+)\b", re.I,
)
HOW_TO = re.compile(r"\b(?:locations?|guide|walkthrough|where to find|how to (?:complete|capture|unlock)|"
                    r"all .*targets?)\b", re.I)
QUESTION_START = re.compile(r"^\s*(?:are |is |has |have |does |did |can |where (?:are|is|can) |"
                            r"anyone |any |anybody |will |could |do )", re.I)
TARGET_TERMS = ("bounty", "wanted poster")


def make_url(base, query):
    return base + "?" + urlencode(query)


@dataclass(frozen=True)
class BountySource:
    id: str
    name: str
    platform: str
    url: str
    coverage: str
    kind: str
    endpoints: tuple[str, ...] = ()
    launch_guides: bool = False
    game_specific: bool = False

    def health(self):
        return {
            "id": self.id, "name": self.name, "platform": self.platform, "url": self.url,
            "coverage": self.coverage, "status": "manual" if self.kind == "manual" else "pending",
            "checkedAt": None, "seen": 0, "matched": 0, "error": None,
        }


GITHUB_QUERY = tuple(
    f'is:issue "{game}" "{topic}" created:>=2026-11-19' for game, topic in
    zip(("GTA VI", "GTA 6"), TARGET_TERMS)
)
BSKY_TERMS = ('"GTA 6" bounty', '"GTA VI" "wanted poster"')
YOUTUBE = "https://www.youtube.com/feeds/videos.xml"
BOUNTY_SOURCES = (
    BountySource("bounty-github", "GitHub public issues", "GitHub",
                 make_url("https://github.com/search", {"q": GITHUB_QUERY[0], "type": "issues"}),
                 "Two GTA VI bounty and wanted-poster searches across public issues.", "github",
                 tuple(make_url("https://api.github.com/search/issues", {
                     "q": query, "sort": "created", "order": "desc", "per_page": 15,
                 }) for query in GITHUB_QUERY)),
    BountySource("bounty-bluesky", "Bluesky public search", "Bluesky",
                 make_url("https://bsky.app/search", {"q": BSKY_TERMS[0]}),
                 "Two public game-specific searches for bounties and wanted posters.", "bluesky",
                 tuple(make_url("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts", {
                     "q": query, "limit": 15, "sort": "latest",
                 }) for query in BSKY_TERMS)),
    BountySource("bounty-lemmy", "Lemmy.world posts", "Lemmy",
                 make_url("https://lemmy.world/search", {"q": "GTA 6 bounty"}),
                 "Anonymous search of public posts indexed by the Lemmy.world instance.", "lemmy",
                 (make_url("https://lemmy.world/api/v3/search", {
                     "q": "GTA 6 bounty", "type_": "Posts", "limit": 15,
                 }),)),
    BountySource("bounty-mastodon", "Mastodon #GTA6", "Mastodon",
                 "https://mastodon.social/tags/gta6",
                 "Public #GTA6 hashtag feed on mastodon.social, filtered for bounty findings.", "mastodon",
                 ("https://mastodon.social/tags/gta6.rss",)),
    BountySource("bounty-video", "GTA Series Videos and IGN", "YouTube",
                 "https://www.youtube.com/@GTASeriesVideos",
                 "Recent public channel titles and feed descriptions. Video contents and comments are outside feed coverage.",
                 "youtube", tuple(make_url(YOUTUBE, {"channel_id": channel}) for channel in (
                     "UCuWcjpKbIDAbZfHoru1toFg", "UCKy1dAqELo0zrOtPkf0eTMw",
                 ))),
    BountySource("bounty-powerpyx", "PowerPyx GTA VI guides", "PowerPyx",
                 "https://www.powerpyx.com/guide/gta-6-grand-theft-auto-vi/",
                 "Firsthand GTA VI guide search feeds for bounty hunting and wanted posters.", "publisher",
                 tuple(powerpyx_feed(term) for term in ("bounty hunting", "wanted poster")), True),
    BountySource("bounty-forum", "GTA Forums at gta.how", "GTA Forums",
                 "https://gta.how/syndication.php?limit=15",
                 "Recent public thread syndication feed filtered for GTA VI bounty findings.", "forum",
                 ("https://gta.how/syndication.php?limit=15",)),
    BountySource("bounty-reddit", "Reddit r/GTA6 search", "Reddit",
                 make_url("https://www.reddit.com/r/GTA6/search/", {"q": "bounty hunting", "restrict_sr": "1"}),
                 "Open the community search manually. Automated feed access failed verification.", "manual"),
    BountySource("bounty-x", "X community search", "X",
                 make_url("https://x.com/search", {"q": '"GTA 6" "bounty hunting"', "f": "live"}),
                 "Open the search manually. The atlas does not sign in or poll X.", "manual"),
    BountySource("bounty-gtaforums", "GTAForums GTA VI board", "GTAForums.com",
                 "https://gtaforums.com/forum/396-gta-vi/",
                 "Browse the GTA VI board manually. Use its search for bounty contracts or wanted posters.", "manual"),
    BountySource("bounty-discord", "Rockstar Games Discord", "Discord",
                 "https://discord.gg/rockstargames",
                 "Rockstar's official invite. Search the server manually if you have access.", "manual"),
    BountySource("bounty-rockstar", "Rockstar GTA VI Newswire", "Rockstar",
                 "https://www.rockstargames.com/newswire?tag=vi",
                 "Manual cross-check for Rockstar announcements.", "manual"),
)


def social_item(text, url, date, title=""):
    text = text if isinstance(text, str) else ""
    choices = re.split(r"[\r\n]+|(?<=[.!?])\s+", text[:2000])
    title = title or next((line for line in choices if TOPIC.search(line)), text)
    return title[:180], text, url, date, None


def list_response(raw, key):
    body = json.loads(raw)
    rows = body[key]
    if not isinstance(rows, list):
        raise ValueError("Unexpected search response.")
    return rows[:15]


def parse_search(raw, kind):
    if kind == "github":
        return [(row.get("title"), row.get("body"), row.get("html_url"), row.get("created_at"), row.get("reactions"))
                for row in list_response(raw, "items") if isinstance(row, dict) and "pull_request" not in row]
    if kind == "bluesky":
        result = []
        for row in list_response(raw, "posts"):
            if not isinstance(row, dict) or not isinstance(row.get("record"), dict):
                continue
            record = row["record"]
            uri = row.get("uri")
            match = re.fullmatch(r"at://(did:[a-z]+:[A-Za-z0-9:._%-]+)/app\.bsky\.feed\.post/([A-Za-z0-9_-]+)", uri or "") if isinstance(uri, str) else None
            if match:
                url = f"https://bsky.app/profile/{match.group(1)}/post/{match.group(2)}"
                result.append(social_item(record.get("text"), url, record.get("createdAt")))
        return result
    rows = []
    for row in list_response(raw, "posts"):
        post = row.get("post") if isinstance(row, dict) else None
        if isinstance(post, dict):
            rows.append((post.get("name"), post.get("body"), post.get("ap_id"), post.get("published"), None))
    return rows


def bounty_report(source, item, landmarks):
    raw_title, raw_excerpt, url, date, _ = item
    title, excerpt = plain(raw_title)[:180], plain(raw_excerpt)[:1400]
    combined = f"{title}. {excerpt}"
    if not (TOPIC.search(combined) and GAME.search(combined) and GAME_CONTEXT.search(combined)):
        return None
    if OLDER_GAME.search(combined) or UNRELATED.search(combined) or NO_FINDING.search(combined):
        return None
    if not TOPIC.search(title):
        return None
    # Require a claim or an actionable documented result. A matching search title is only a lead to review.
    sentences = [line for line in re.split(r"(?<=[.!?])\s+", combined) if line and not line.rstrip(".").endswith("?")
                 and not QUESTION_START.match(line)]
    claims = [line for line in sentences if OUTCOME.search(line) and TOPIC.search(line)]
    if not claims and not (HOW_TO.search(title) and "?" not in title and len(excerpt) >= 65
                           and any(PROCESS.search(line) and GAME_CONTEXT.search(line) for line in sentences[1:])):
        return None
    # Avoid metadata-only blurbs that say a video/article discusses bounties without showing a find.
    if not claims and source.kind == "youtube":
        return None
    report = make_report(source, item, landmarks)
    if report is None:
        return None
    report["category"] = "bounty"
    report["platform"] = source.platform
    report["watchStatus"] = "source claim"
    report.pop("_extract", None)
    # Exact substantive copies may appear across networks. Keep provenance for each linked copy.
    echo = " ".join(re.findall(r"\w+", excerpt.casefold()))
    if len(echo) > 110:
        report["claimKey"] = sha256(echo.encode()).hexdigest()[:24]
    return report


def read_bounty_source(source, landmarks, fetcher):
    health = source.health()
    if source.kind == "manual":
        return health, []
    health["checkedAt"] = datetime.now(timezone.utc).isoformat()
    seen = {}
    failures = []
    for endpoint in source.endpoints:
        try:
            headers = {"Accept": "application/vnd.github+json"} if source.kind == "github" else None
            response = fetcher(endpoint, headers=headers, timeout=6, max_size=1_250_000)
            if source.kind in ("github", "bluesky", "lemmy"):
                rows = parse_search(response, source.kind)
            else:
                rows = parse_feed(response, publisher_guides=source.launch_guides)[:20]
            for item in rows:
                link = item[2]
                if isinstance(link, str):
                    if source.kind == "lemmy" and urlsplit(link).scheme != "https":
                        continue
                    seen.setdefault(link, item)
        except (OSError, ValueError, KeyError, TypeError, ElementTree.ParseError) as exc:
            failures.append(failure_message(exc))
    matches = [report for item in seen.values() if (report := bounty_report(source, item, landmarks))]
    health.update(status="error" if failures else "ok", seen=len(seen), matched=len(matches), error=(
        f"{len(failures)} of {len(source.endpoints)} endpoints failed. {failures[0]}" if failures else None
    ))
    return health, matches


def discover_bounties(landmarks, fetcher=fetch):
    with ThreadPoolExecutor(max_workers=7) as pool:
        jobs = [pool.submit(read_bounty_source, source, landmarks, fetcher) for source in BOUNTY_SOURCES]
        results = [job.result() for job in jobs]
    return [health for health, _ in results], [report for _, rows in results for report in rows]


def merge_bounty_reports(cached, incoming, limit=300):
    by_id = {row["id"]: row for row in cached}
    signatures = {row["claimKey"]: row["id"] for row in cached if row.get("claimKey")}
    for row in incoming:
        stable = by_id.get(row["id"])
        identical_id = signatures.get(row.get("claimKey"))
        identical = by_id.get(identical_id) if identical_id else None
        if stable is None and identical is not None:
            links = list(identical.get("relatedSources", []))
            if row["source"] != identical["source"] and all(link["url"] != row["source"] for link in links):
                links.append({"name": row["sourceName"], "platform": row["platform"], "url": row["source"]})
            by_id[identical_id] = {**identical, "relatedSources": links[:8]}
            continue
        if stable and stable.get("claimKey") and stable.get("claimKey") == row.get("claimKey"):
            row = {**row, "relatedSources": stable.get("relatedSources", [])}
        elif stable and signatures.get(stable.get("claimKey")) == stable["id"]:
            del signatures[stable["claimKey"]]
        by_id[row["id"]] = row
        if row.get("claimKey"):
            signatures[row["claimKey"]] = row["id"]
    return sorted(by_id.values(), key=lambda row: row.get("publishedAt") or "", reverse=True)[:limit]
