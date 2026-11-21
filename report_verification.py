"""Conservative, local review of already collected GTA VI gameplay reports."""

from collections import defaultdict
from dataclasses import dataclass
from math import hypot
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

GAME_WIDTH = 13_824
GAME_HEIGHT = 19_456
GRID_AGREEMENT = 50
GRID_DISAGREEMENT = 250
MAX_SOURCES = 8

KNOWN_CATEGORIES = frozenset({
    "mission", "heist", "bounty", "reward", "earbuds", "gloves", "bag", "collectible", "landmark",
})
# Remove generic words so two headlines that only say "new GTA 6 bounty"
# cannot support the same claim merely by sharing a venue or neighborhood.
STOP_WORDS = frozenset("""
a about after again also am an and are as at be been before being by can chapter
check claim complete completed confirmed could did do does during each find finding
first for found from game get gets got gta grand guide has have he her here how i in
into is it its know last latest location locations look map me my near new now of
on one only or our out patch patched player players play possible report reward
rewards says she should some spot spots take that the their them there they this
through to unlock unlocked update use v vi was we were what when where which who
will with world would you your all auto theft
earbud earbuds headphone headphones earphone earphones glove gloves bag bags backpack
backpacks collectible collectibles card cards heist heists robberies robbery bounty bounties
landmark landmarks target targets equipment payout cash loot
""".split())
ALIASES = {
    "youtubeshorts.com": "youtube.com",
    "youtu.be": "youtube.com",
    "redd.it": "reddit.com",
    "redditmedia.com": "reddit.com",
    "twitter.com": "x.com",
}
COMMON_SECOND_LEVEL = frozenset({"ac", "co", "com", "edu", "gov", "net", "org"})
MULTI_LOCATION = re.compile(
    r"\b(?:all|every|each|complete list of)\b.{0,64}\b"
    r"(?:locations?|stores?|sets?|cards?|jobs?|targets?|spawns?|collectibles?)\b|"
    r"\b(?:[2-9]|[1-9]\d+)\s+(?:locations?|stores?|targets?|spawns?)\b",
    re.I,
)
NON_AFFIRMATIVE = re.compile(
    r"\b(?:anyone (?:found|seen|know)|does (?:this|it) (?:work|exist|spawn)|"
    r"any idea|can(?:not|'t|’t) (?:find|confirm)|could(?: not|n't|n’t) (?:find|confirm)|"
    r"hav(?:e not|en't|en’t) (?:found|seen|confirmed)|unconfirmed|hypothetical|"
    r"rumou?r(?:ed|s)?|speculat\w*|wish ?list|might (?:spawn|unlock|drop))\b", re.I,
)
POSITIVE_EVIDENCE = re.compile(
    r"\b(?:found|collected|received|obtained|picked up|spawns?|appears?|drops?|unlocks?|"
    r"completed|captured|finished|purchased?|bought|available|go to|check the|interact with|"
    r"select|look for|on (?:a|the) (?:shelf|table|counter|balcony)|inside the)\b",
    re.I,
)
REPOST = re.compile(
    r"\b(?:repost(?:ed)? (?:from|of)|mirrored from|taken from|copied from|"
    r"reupload(?:ed)?|cross-?post(?:ed)?|syndicated from)\b", re.I,
)
ATTRIBUTION = re.compile(r"\b(?:according to|as reported by|reported by|via|h/t|credit to)\s+", re.I)
URL_IN_TEXT = re.compile(r"https?://[^\s<>\[\]{}'\"]+", re.I)
RETRACTED = re.compile(
    r"\b(?:i (?:retract|withdraw) (?:this|my)|(?:this|the|original|my) (?:claim|post|report) "
    r"(?:was |is |has been )?(?:retracted|withdrawn)|(?:posted|shared|gave) (?:the )?wrong (?:pin|location|coordinates?))\b",
    re.I,
)
CHANGED = re.compile(
    r"\b(?:no longer (?:works?|spawns?|appears?|drops?|unlocks?|pays? out)|"
    r"(?:loot|reward|drop|spawn|bounty|pickup|item|mission|route|location|steps) "
    r"(?:was |is |has been )?(?:patched out|removed|broken)|"
    r"(?:this|it) (?:was |is |has been )patched(?: out| in| with| on|(?=[.!?,]|$))|"
    r"(?:this|the) (?:method|route|unlock|mission) (?:is )?broken|"
    r"(?:latest|last|new) (?:patch|update) (?:broke|removed|disabled|moved) (?:this|the|it)|"
    r"(?:pin|coordinates?|location) (?:is |are |were )?(?:wrong|incorrect|out of date))\b",
    re.I,
)
PRESENT_TENSE_NEGATION = re.compile(r"\b(?:not|never|isn['’]t|wasn['’]t)\s+(?:been\s+)?(?:patched|broken|removed)\b", re.I)
QUESTION_START = re.compile(r"^(?:is|are|does|do|can|have|has|did|will|could|anyone|anybody)\b", re.I)
SINGLE_OBJECT = re.compile(r"\b(?:unique|one-time|single|only|final)\b", re.I)
VARIANT = re.compile(
    r"(?<!\w)(?:#\s*(\d+)|(?:part|stage|tier|branch|variant|chapter)\s+(\d+|one|two|three|four|five)|"
    r"(red|blue|purple|bronze|silver|gold)\s+(?:variant|edition)|"
    r"(low|medium|high)\s+security)\b", re.I,
)
OBJECT_TYPES = (
    ("card", re.compile(r"\b(?:trading cards?|collectible cards?|cards?)\b", re.I)),
    ("poster", re.compile(r"\bposters?\b", re.I)),
    ("meditation", re.compile(r"\bmeditat(?:e|es|ion|ions|ing)\b", re.I)),
    ("sculpture", re.compile(r"\b(?:sculptures?|statues?)\b", re.I)),
    ("playlist", re.compile(r"\bplaylists?\b", re.I)),
)


def text(value, limit=1200):
    return value[:limit].strip() if isinstance(value, str) else ""


def host_family(host):
    labels = host.lower().rstrip(".").removeprefix("www.").split(".")
    width = 3 if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in COMMON_SECOND_LEVEL else 2
    domain = ".".join(labels[-width:])
    return ALIASES.get(domain, domain)


def normalized_link(value):
    if (not isinstance(value, str) or len(value) > 2000
            or any(ch.isspace() or ord(ch) < 32 for ch in value)):
        return "", ""
    try:
        parsed = urlsplit(value)
        domain = parsed.hostname
        if (parsed.scheme != "https" or not domain or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", domain)
                or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443)):
            return "", ""
    except ValueError:
        return "", ""
    query = urlencode(sorted((key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                             if not key.lower().startswith("utm_") and key.lower() not in {"ref", "fbclid", "gclid"}))
    # GTADB encodes its landmark identity in the fragment, other hosted pages don't.
    fragment = parsed.fragment if host_family(domain) == "gtadb.org" else ""
    return urlunsplit(("https", domain.lower().removeprefix("www."), parsed.path.rstrip("/") or "/",
                       query, fragment)), host_family(domain)


def title_terms(title):
    return frozenset(word for word in re.findall(r"\b[^\W_]+\b", title.casefold())
                     if len(word) >= 3 and not word.isnumeric() and word not in STOP_WORDS)


def normalized_words(value):
    return " ".join(re.findall(r"[^\W_]+", value.casefold()))


def has_question_only(title, excerpt):
    # Cautious handling of posts asking where a reward is.
    if "?" not in title:
        return False
    if QUESTION_START.search(title) or title.lower().startswith(("where ", "how ", "when ")):
        return not re.search(r"\b(?:i|we) (?:found|obtained|unlocked|completed|received|collected)\b", excerpt, re.I)
    return len(normalized_words(excerpt)) < 45


def typed_point(row):
    point = row.get("x"), row.get("y")
    return point if all(type(axis) in (int, float) and 0 <= axis <= 1 for axis in point) else None


def explicit_grid(row):
    # In the current importer, reported positions come from an explicit ATLAS_GTA6_GRID claim.
    return (row.get("confidence") == "reported" or row.get("precision") == "reported-grid") and typed_point(row) is not None


def markers(title):
    return tuple(sorted(match.group().casefold() for match in VARIANT.finditer(title)))


@dataclass(frozen=True)
class Evidence:
    category: str
    title: str
    terms: frozenset[str]
    venue: str
    region: str
    url: str
    display_url: str
    host: str
    name: str
    excerpt: str
    digest: str
    origin_links: frozenset[str]
    variant: tuple[str, ...]
    object_types: frozenset[str]
    point: tuple[float, float] | None
    is_grid: bool
    broad: bool
    affirmative: bool
    issue: str | None


def make_evidence(row):
    category = text(row.get("category"), 30)
    title = text(row.get("title"), 220)
    excerpt = text(row.get("_extract")) or text(row.get("verificationExcerpt")) or text(row.get("details"))
    combined = f"{title}. {excerpt}"
    url, host = normalized_link(row.get("source"))
    name = text(row.get("sourceName") or row.get("sourceLabel"), 100) or host or "Source report"
    evidence_links = list(URL_IN_TEXT.findall(excerpt))
    location = row.get("locationSource")
    if isinstance(location, str):
        evidence_links.append(location)
    origin_links = frozenset(
        link for raw in evidence_links
        if (value := normalized_link(raw.rstrip("),.;")))[1] not in ("", "gtadb.org")
        and (link := value[0]) != url
    )
    issue = None
    statements = (sentence for sentence in re.split(r"(?<=[.!?])\s+", combined)
                  if not sentence.rstrip(".").endswith("?"))
    stale_text = PRESENT_TENSE_NEGATION.sub("", " ".join(statements))
    if RETRACTED.search(stale_text):
        issue = "The source reports a retraction or correction."
    elif CHANGED.search(stale_text):
        issue = "The source says the reported gameplay or location may have changed. Check the evidence."
    venue_id = text(row.get("landmarkId"), 120)
    venue = ("id:" + venue_id) if venue_id else ""
    # A region name is useful conflict context, but only a catalogue ID is a venue anchor.
    region = normalized_words(text(row.get("region"), 120))
    broad = bool(MULTI_LOCATION.search(title))
    affirmative = (len(normalized_words(excerpt)) >= 40 and bool(POSITIVE_EVIDENCE.search(excerpt))
                   and not NON_AFFIRMATIVE.search(combined)
                   and not has_question_only(title, excerpt) and not REPOST.search(combined))
    return Evidence(category, title, title_terms(title), venue, region, url, row["source"] if url else "", host, name,
                    normalized_words(excerpt), text(row.get("sourceDigest"), 100), origin_links, markers(title),
                    frozenset(kind for kind, pattern in OBJECT_TYPES if pattern.search(title)),
                    typed_point(row), explicit_grid(row), broad, affirmative, issue)


def references_other(current, other):
    if other.url in current.origin_links:
        return True
    # Attribution without a URL still makes this source derivative.
    publisher = other.host.split(".")[0]
    name = normalized_words(other.name).split()
    brand = {publisher}
    if name:
        brand.add(name[0])
        brand.add(" ".join(name[:2]))
    return any(current.excerpt[match.end():].startswith(word + " ") or current.excerpt[match.end():] == word
               for match in ATTRIBUTION.finditer(current.excerpt) for word in brand if len(word) >= 3)


def independent(a, b):
    if not a.host or not b.host or a.host == b.host or a.url == b.url:
        return False
    if a.digest and a.digest == b.digest:
        return False
    if any(REPOST.search(f"{fact.title} {fact.excerpt}") for fact in (a, b)):
        return False
    if a.origin_links & b.origin_links or references_other(a, b) or references_other(b, a):
        return False
    if a.excerpt and a.excerpt == b.excerpt:
        return False
    # Excerpts are clipped by the importer, so a copied introduction can appear with different tails.
    shortest, longest = sorted((a.excerpt, b.excerpt), key=len)
    if len(shortest) >= 60 and (longest.startswith(shortest) or shortest[:80] == longest[:80]):
        return False
    return True


def same_subject(a, b):
    if a.broad or b.broad or a.variant != b.variant:
        return False
    if a.object_types and b.object_types and a.object_types != b.object_types:
        return False
    common = a.terms & b.terms
    return len(common) >= 2 and len(common) * 3 >= len(a.terms | b.terms) * 2


def game_distance(a, b):
    return hypot((a[0] - b[0]) * GAME_WIDTH, (a[1] - b[1]) * GAME_HEIGHT)


def pair_result(a, b):
    if not same_subject(a, b) or not independent(a, b):
        return None
    same_venue = bool(a.venue and a.venue == b.venue)
    # Never collapse reports for two separately named venues just because a common item is present.
    different_venues = bool(a.venue and b.venue and a.venue != b.venue)
    if different_venues:
        return None
    both_grids = a.is_grid and b.is_grid
    distance = game_distance(a.point, b.point) if both_grids else None
    same_area = a.region == b.region and a.region not in ("", "unresolved", "leonida")
    unique_subject = a.terms == b.terms and any(SINGLE_OBJECT.search(e.title) for e in (a, b))

    if distance is not None and distance >= GRID_DISAGREEMENT and (same_venue or same_area or unique_subject):
        if a.affirmative and b.affirmative:
            return "conflict"
    same_grid = distance is not None and distance <= GRID_AGREEMENT
    if not (same_venue or same_grid):
        return None
    if (a.issue and b.affirmative) or (b.issue and a.affirmative):
        return "questioned"
    if a.affirmative and b.affirmative and not a.issue and not b.issue:
        return "grid" if same_grid else "venue"
    return None


def evidence_links(facts):
    links = {}
    for fact in facts:
        if fact.url and fact.url not in links:
            links[fact.url] = {"name": fact.name, "url": fact.display_url}
            if len(links) >= MAX_SOURCES:
                break
    return list(links.values())


def review_reports(reports):
    """Annotate copies of collected reports. Keep the input evidence for re-review."""
    rows = list(reports)
    facts = [make_evidence(row) for row in rows]
    groups = defaultdict(list)
    for i, fact in enumerate(facts):
        if fact.category in KNOWN_CATEGORIES and not fact.broad and len(fact.terms) >= 2:
            groups[fact.category].append(i)
    agreeing = defaultdict(list)
    challenged = defaultdict(list)
    for indices in groups.values():
        for offset, left in enumerate(indices):
            for right in indices[offset + 1:]:
                relation = pair_result(facts[left], facts[right])
                if relation in ("conflict", "questioned"):
                    challenged[left].append((right, relation))
                    challenged[right].append((left, relation))
                elif relation in ("grid", "venue"):
                    agreeing[left].append((right, relation))
                    agreeing[right].append((left, relation))

    verified = []
    for i, (row, fact) in enumerate(zip(rows, facts)):
        copy = dict(row)
        if fact.issue or challenged[i]:
            relations = challenged[i]
            conflicts = [facts[j] for j, relation in relations if relation == "conflict"]
            reason = (
                "Independent reports disagree about the game grid location. The pin is hidden pending review."
                if conflicts else fact.issue or "Another source questions this report. The pin is hidden pending review."
            )
            sources = evidence_links([fact, *conflicts, *(facts[j] for j, _ in relations)])
            status, label = "review", "Needs review"
            copy.update(x=None, y=None)
        elif agreeing[i]:
            status, label = "corroborated", "Corroborated"
            reason = (
                "Independent sources report closely matching grid positions for this activity."
                if any(relation == "grid" for _, relation in agreeing[i])
                else "Independent sources report the same activity at this venue. The pickup point remains approximate."
            )
            sources = evidence_links([fact, *(facts[j] for j, _ in agreeing[i])])
        else:
            status, label = "single-source", "Single-source report"
            reason = "No independent report with matching, specific location evidence has been found in the loaded reports."
            if fact.broad:
                reason = "This source covers multiple locations or activities. Review each location separately."
            sources = evidence_links([fact])
        copy["verification"] = {"status": status, "label": label, "reason": reason, "sources": sources}
        verified.append(copy)
    return verified
