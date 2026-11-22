# Public source discovery

The atlas checks a fixed set of public publisher and community feeds. It also runs three anonymous Google News RSS searches for publishers covering gear and collectibles, heists and bounties, and mission walkthroughs. Search results nominate publishers. Only a publisher’s own syndication entries can become automatic reports. [Bounty Watch sources and schedule](API.md) · [Gameplay evidence review](EVIDENCE-REVIEW.md)

## Publisher coverage

| Source | Automatic coverage |
| --- | --- |
| PowerPyx | Targeted RSS searches for individual walkthroughs, bank vaults, collectible cards, electronics stores and equipment. |
| GTA BOOM | The publisher’s RSS feed provides mission and loot descriptions. The separately browsable mission index is a reference. |
| Push Square | The PlayStation guide RSS feed, screened for GTA VI gameplay. |
| Video Games Chronicle | The publisher’s guide feed includes GTA VI safe locations, mission objectives and equipment unlocks. [VGC guide feed](https://www.videogameschronicle.com/category/guide/feed/) |
| Destructoid | Its GTA 6 tag feed includes secrets and collectible unlocks. Entries pass the same gameplay and source evidence checks as the other feeds. [Destructoid GTA 6 feed](https://www.destructoid.com/tag/gta-6/feed/) |
| GTA6 Collectibles Map | RSS entries for collectibles, rewards and related research leads. Derivative or broad guides still need separate in-game evidence before assigning a precise location. |
| Insider Gaming | The targeted GTA 6 loot search feed provides gear and named reward leads. The importer keeps links to the publisher’s own articles. [Insider Gaming loot feed](https://insider-gaming.com/?s=GTA+6+loot&feed=rss2) |
| The VI Field Guide | The unofficial fan guide’s feed provides individual walkthroughs and collectible leads. The importer keeps the article and publisher link. Mission numbers remain the publisher’s numbering. [The VI Field Guide feed](https://vifieldguide.com/feed.xml) |
| Other fixed feeds | GitHub public issues, GTA Forums at gta.how, GTA6.how, GamesRadar+ and PC Gamer. |

[PowerPyx walkthrough search feed](https://www.powerpyx.com/?s=%22GTA+6%22+%22Walkthrough%22&feed=rss2) · [GTA BOOM feed](https://www.gtaboom.com/feed.xml) · [Push Square guide feed](https://www.pushsquare.com/feeds/guides) · [GTA6 Collectibles Map feed](https://gta6collectiblesmap.com/feed.xml)

## How a mission becomes a report

A mission entry needs an individual walkthrough headline and explicit mission metadata or publisher-supplied gameplay objectives. Grouped guides, full story walkthroughs, release schedules, preorder posts and rumors stay out of the individual mission count. The atlas keeps the publisher name and article link. It extracts chapter, character, prerequisite and starting location only when the feed states them.

A named start can receive an approximate pin when it matches a game-named venue in the atlas. A district or city name alone stays a text location. Mentioning a destination in a mission objective provides no evidence of its start. An explicit correction or patch notice that refers to an eligible gameplay claim sends that claim into evidence review. The source link and original claim remain available for checking.

Different articles may cover the same mission. Source-health counts are distinct accepted links per feed. After canonical URL deduplication, an article still remains distinct from a different publisher’s account. An independent source link can corroborate a claim when the evidence review criteria are met.

Sports & games discovery matches gameplay terms such as pool opponents, billiards, golf courses, gym locations, arcade games and named minigames. It screens out swimming, money and prize pools. Multi-topic feeds need an explicit GTA VI headline so a reference to GTA VI in an unrelated article’s excerpt cannot qualify it.

## Ranking and refresh

- An accepted article published within 72 hours earns five points. An older eligible article earns two. The latest qualifying publication breaks ties, then the publisher hostname.
- Each run checks up to eight additional publisher sites and returns up to six ranked candidates, alongside three search-index statuses. Previously qualified feeds get rechecked when search indexes fail. Publishers already covered by the fixed list are skipped.
- For an additional publisher, the atlas can inspect an advertised RSS or Atom link and try a bounded GTA VI WordPress search feed. Publisher records include the source, provenance, number of feed entries, accepted reports and category counts.
- The atlas reads a bounded number of records and avoids loading each article page to gain more results. Coverage can change between scans as feeds update.

## Public reading and confirmed limits

Dynamic publisher reads use HTTPS GET. The client validates the public destination for each request and redirect, caps time, size and candidate counts, and processes feed text without executing page scripts. The discovery requests use anonymous public endpoints. They do not import local account state or send authenticated query URLs.

The November 21, 2026 validation confirmed usable RSS from PowerPyx, GTA BOOM, Push Square and GTA6 Collectibles Map. Some feeds returned no qualifying reports. For example, Push Square’s guide feed responded but most GTA VI entries in that sample were announcement or guide-index material. Its independently published Key Lento walkthrough remains a useful browsable reference. The gta.how syndication feed timed out during the same live test. [Push Square Key Lento walkthrough](https://www.pushsquare.com/guides/gta-6-key-lento-collectibles-and-secrets-walkthrough)

The final validation read 10 entries from the dedicated PowerPyx walkthrough feed and accepted all 10 as individual missions. GTA BOOM returned 30 entries, with 11 missions, one collectible article and one reward article passing. GTA6 Collectibles Map returned 35 entries and five accepted articles. Across the fixed and additional feeds the atlas accepted 41 unique source links, including 23 mission articles. One of those mission articles named a starting venue that received an approximate pin. Video Games Chronicle and eGamers.io yielded three qualifying links in the additional-publisher search. These are results of one bounded scan. A mission may have multiple published accounts.

## November 22 validation

The November 22, 2026 live check returned 10 entries from Insider Gaming and accepted three named reward articles. The VI Field Guide returned 25 and yielded 17 articles, including 14 missions, two collectible guides and one reward guide. The fixed feeds returned 72 distinct accepted links, including two Sports & games articles about arcade games and Tenebrae Lux. Publisher search added 16 links from eGamers.io, KeenGamer and Eurogamer, for 88 distinct links in this sample. The gta.how feed timed out, and the Everything Edinburgh and Happy Gamer candidates returned no readable feed. Sample counts describe articles, which may cover the same game activity. [Insider Gaming loot feed](https://insider-gaming.com/?s=GTA+6+loot&feed=rss2) · [The VI Field Guide feed](https://vifieldguide.com/feed.xml)

## Browse beyond the feeds

- **Story missions and side jobs.** Publisher indexes include walkthroughs that may have moved out of the latest RSS window. [PowerPyx full walkthrough index](https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/) · [GTA BOOM mission guide index](https://www.gtaboom.com/gta-6-missions-walkthroughs) · [PC Gamer mission list](https://www.pcgamer.com/games/grand-theft-auto/gta-6-mission-list/)
- **Gear and collectibles.** Dedicated guides give steps and prerequisites that a feed excerpt may omit. [PowerPyx equipment guide](https://www.powerpyx.com/gta-6-all-equipment/) · [PowerPyx meditation guide](https://www.powerpyx.com/gta-6-all-meditation-spot-locations/) · [PC Gamer’s secret playlist guide](https://www.pcgamer.com/games/grand-theft-auto/gta-6-unique-playlists/)
- **Bounties and corrections.** Use the independent Bounty Watch schedule and its manual community links. Check publisher corrections and Rockstar’s announcements before treating a patch claim as confirmed. A zero-result scan describes the checked feeds at that time. [Rockstar GTA VI Newswire](https://www.rockstargames.com/newswire?tag=vi) · [Bounty Watch API](API.md)

## Verification

Run the offline source tests from the project root.

```sh
python -B -m unittest discover -s tests -p test_resource_discovery.py
python -B -m unittest discover -s tests -p test_discovery_api.py
```

The following prints the live additional-publisher sample with positions disabled.

```sh
python -c "from resource_discovery import discover_resources; sources, reports = discover_resources([]); print([(s['name'], s['status'], s.get('byCategory')) for s in sources]); print([r['source'] for r in reports])"
```
