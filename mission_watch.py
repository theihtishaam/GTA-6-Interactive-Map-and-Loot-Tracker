"""Watch the published mission index for walkthroughs a bundled release has not covered."""
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import urljoin

from discovery import Source, fetch, iso_date, mission_context, plain

INDEX = "https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/"
SOURCE = Source("mission-index", "PowerPyx mission index changes", INDEX)
ARTICLE = re.compile(r"https://www\.powerpyx\.com/gta-6-[a-z0-9-]+-walkthrough/")
DETAIL_FIELDS = {"Starting Location", "Starting Area", "Chapter", "Requirement", "Requirements",
                 "Quest Giver", "Can Be Started By", "Reward"}


class MissionPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.content = 0
        self.ordered = 0
        self.item = None
        self.anchor = None
        self.url = None
        self.published = None
        self.links = {}
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("property") == "article:published_time":
            self.published = iso_date(a.get("content"))
        if tag == "div" and (self.content or "entry-content" in (a.get("class") or "").split()):
            self.content += 1
        if not self.content:
            return
        if tag == "ol":
            self.ordered += 1
        if tag == "li":
            self.item = []
        if tag == "a" and self.ordered and self.item is not None:
            url = urljoin(INDEX, a.get("href") or "")
            if ARTICLE.fullmatch(url):
                self.url, self.anchor = url, []

    def handle_data(self, data):
        if self.item is not None:
            self.item.append(data)
        if self.anchor is not None:
            self.anchor.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            name = " ".join("".join(self.anchor).split())[:180]
            if name:
                self.links[self.url] = name
            self.url = self.anchor = None
        if tag == "li" and self.item is not None:
            key, _, value = " ".join("".join(self.item).split()).partition(":")
            if key in DETAIL_FIELDS and value.strip():
                self.fields.setdefault(key, value.strip()[:220])
            self.item = None
        if tag == "ol":
            self.ordered = max(0, self.ordered - 1)
        if tag == "div" and self.content:
            self.content -= 1


def read_page(url, fetcher):
    page = MissionPage()
    page.feed(fetcher(url, max_size=1_500_000, timeout=7).decode("utf-8", errors="replace"))
    page.close()
    return page


def discover_index(bundled, previous, landmarks, fetcher=fetch, budget=4):
    now = datetime.now(timezone.utc)
    health = {**SOURCE.health(), "checkedAt":now.isoformat(),
              "coverage":"Checks the complete walkthrough index and up to four new mission pages per run."}
    rows = []
    try:
        index = read_page(INDEX, fetcher)
        if len(index.links) < 10:
            raise ValueError("Unrecognized mission index")
        known = {r.get("source") for r in bundled}
        # A successful direct read remains eligible for ordinary publisher corrections through its feed.
        known.update(r.get("source") for r in previous if r.get("category") == "mission" and r.get("indexChecked"))
        unseen = [(url,name) for url,name in index.links.items() if url not in known]
        # Rotate even through persistent unavailable pages so a broken link cannot block later discoveries.
        window = int(now.timestamp() // (6 * 3600))
        if len(unseen) > budget:
            shift = (window * budget) % len(unseen)
            unseen = unseen[shift:] + unseen[:shift]
        failures = 0
        for url, label in unseen[:budget]:
            try:
                page = read_page(url, fetcher)
                f = page.fields
                if not f or not page.published or not datetime(2026,11,18,tzinfo=timezone.utc) <= page.published <= now:
                    raise ValueError("Missing mission details")
                title = re.sub(r"^(Optional\s*[-–—]\s*)|^\[[^\]]+\]\s*", "", label).split(" (")[0].strip()
                if not title:
                    continue
                area = f.get("Starting Location") or f.get("Starting Area")
                description = " ".join(k + ": " + v + "." for k,v in f.items())[:800]
                _, place = mission_context(title, "Starting Location: " + (area or "") + ". ", landmarks)
                row = {"id":sha256(url.encode()).hexdigest()[:24], "title":title, "missionName":title,
                       "category":"mission", "source":url, "sourceName":"PowerPyx", "indexChecked":True,
                       "publishedAt":page.published.isoformat(), "startingLocation":area,
                       "region":place["region"] if place else area or "Unresolved",
                       "x":place["x"] if place else None, "y":place["y"] if place else None,
                       "landmarkId":place["id"] if place else None, "confidence":"area" if place else "lead",
                       "details":plain(description)[:320], "steps":[], "contact":f.get("Quest Giver"),
                       "character":f.get("Can Be Started By"), "prerequisite":f.get("Requirement") or f.get("Requirements"),
                       "sourceDigest":sha256(description.encode()).hexdigest(), "_extract":description}
                if (f.get("Chapter") or "").isdigit():
                    row["chapter"] = int(f["Chapter"])
                rows.append(row)
            except (ValueError, OSError, UnicodeError):
                failures += 1
        health.update(status="ok", seen=len(index.links), matched=len(rows))
        if failures:
            health["error"] = str(failures) + " new walkthrough pages could not be validated."
    except (ValueError, OSError, UnicodeError):
        health.update(status="error", error="The mission index could not be read.")
    return health, rows
