# Public source discovery

The atlas runs two anonymous Google News RSS queries for GTA VI guide topics. Each query identifies publisher websites from the feed’s public publisher metadata. The atlas opens the publisher’s homepage and follows advertised RSS or Atom links. For WordPress sites, it also tries a GTA VI search feed. Search results identify candidates, and only the publishers’ own syndication entries can become reports.

The atlas excludes existing fixed sources, duplicate publishers, off-site article links, older GTA titles, rumors, and items that fail the existing GTA VI report checks. A candidate qualifies when at least one distinct source article passes those checks. Article mentions without a reliable location stay unresolved under the same rules as reports from fixed feeds.

## Ranking and refresh

- An accepted article published within the last 72 hours earns five points. An older eligible article earns two points. The score uses each unique accepted article once. The latest qualifying publication breaks ties, then the publisher hostname.
- Each refresh checks up to eight publisher sites and returns up to six, along with both search index statuses. A shortlist reserves up to half of its normal candidate slots for previously qualifying sources. Those sources are rechecked even when the public search indexes fail.
- Discovery records include the publisher, feed link, index provenance, number of feed entries and accepted reports, score, and time of last qualification. A publisher can respond successfully without qualifying. A failed feed has a diagnostic status and contributes no reports.
- Sources and articles carry stable IDs. The API merges automatic reports from all sources by their canonical article URLs.

## Network safeguards

Public reads use HTTPS GET on port 443. The transport resolves each destination separately, including each redirect and each recheck of a persisted source. It rejects a hostname if any DNS answer is nonpublic. A connection uses a validated numeric address and verifies the public hostname with TLS. The network client sends no login information, cookie headers, proxy credentials, or authenticated query URLs. Time, response size, redirects, candidate hosts, and per-publisher feed checks have quotas. Feed parsing rejects document declarations that could load entities. The atlas does not run scripts from publisher pages.

## Verified example

The live test on November 21, 2026 found two qualifying sources beyond the fixed list. eGamers.io’s WordPress search feed and GTA BOOM’s RSS each returned one accepted collectibles article. Both received five points. Other candidates either returned no qualifying feed entries or could not be read. This records observed coverage for that run. [eGamers.io feed](https://egamers.io/?s=GTA+6&feed=rss2) · [GTA BOOM feed](https://www.gtaboom.com/feed.xml)

The public index can change or be unavailable. Retained feed rechecks and the atlas’s fixed sources cover temporary outages.

Run the offline discovery and transport tests from the project root.

    python -m unittest discover -s tests -p test_resource_discovery.py

To inspect the real public discovery results independently of the app, call discover_resources with an empty landmark list.

    python -c "from resource_discovery import discover_resources; sources, reports = discover_resources([]); print([(s['name'], s['status'], s.get('score')) for s in sources]); print([r['source'] for r in reports])"
