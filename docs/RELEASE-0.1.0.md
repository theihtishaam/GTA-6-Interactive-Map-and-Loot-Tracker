# GTA 6 Loot Map 0.1.0

Release date: November 21, 2026. By theihtishaam (The Ihtisham).

## First session

1. Start the atlas and open **Player manual**. The starter chapters link to real equipment, unlock requirements and guide sources. The manual’s optional story reveal lets you choose when to see a reward spoiler.
2. On **World map**, select **My position** and click where your character is standing. Filter to an activity or collectible. Each located result shows a direct distance from your character. Open a pin for its compass direction.
3. Choose **Route here**. The GPS card shows the next stop, itinerary estimate and a driving cue. Follow solid road traces and use the dashed approaches as bearings. Move your character point when you travel. **My position → Nearby activities** lists unfinished activities by distance.
4. Open the supporting evidence and check whether the pin marks an exact game marker, a building, a mission start or an approximate area. **Load source image** can cache a supported illustration for another offline visit. Mark the entry complete or edit a personal pin with your own observations.
5. In **Field journal → Export center**, choose a scope and format. HTML embeds the licensed community map, markers and optional route into one printable offline file. CSV works in a spreadsheet. JSON includes evidence and coordinate metadata. A journal backup restores editable progress and personal pins.

## Discovery and evidence

Two independent clocks cover all activities and targeted bounty reports. Both run every 24 hours by default and support 6- and 12-hour intervals. Automatic discovery searches public indexes for new sites, finds their RSS or Atom feeds, and scores current qualifying reports. The coverage panel exposes candidate sources, ranking reasons and search provenance. If a source gives no supported position, the discovery remains searchable and keeps its source link. [Source-discovery design](RESOURCE-DISCOVERY.md)

The targeted watch searches public posts, issues, channel feeds and publisher feeds. It also links to manual searches on Reddit, X, GTAForums.com, Rockstar Discord and Newswire. Readers can contribute a location or correction through the repository. A public search can cover only the material the platform exposes. The bundled collection covers all ten meditation sites with 18 actions, alongside 66 other guides. [Bounty Watch API and coverage](API.md) · [Meditation coordinate audit](COLLECTIBLES.md)

## Images and operating costs

A guide with registered image evidence keeps a link to its original screenshot. For approved publishers and dynamically qualified feeds, the local image cache can use a matching illustration or the publisher's article preview. A preview describes the article. A registered map marker has separate coordinate and precision evidence. Both preserve a link to the publisher. Image collection is bounded to six candidate entries per general run, 3.5 MB per image and 32 MB of cached images. Publisher images stay in the local runtime directory. Only the attributed community map is embedded into exported field packs. [Open Graph image metadata](https://ogp.me/) · [Data credits](MAP-DATA.md)

A fresh installation performs zero AI inference. The optional model processes at most one new or changed report per general scan. The Ollama Cloud selector lists available text models and shows its extraction suggestion. Hosted Ollama generation is metered. OpenRouter's free router, local Ollama and the built-in no-model option support different cost and hardware needs. [Provider research](MODELS.md) · [Ollama pricing](https://ollama.com/pricing) · [OpenRouter free router](https://openrouter.ai/openrouter/free)

## Observed coverage

The release-day general scan retained eleven qualifying public reports. Two dynamically discovered publishers, GTA BOOM and eGamers.io, each supplied one. The targeted scan reviewed 83 records across six responding automatic sources and found zero eligible bounty reports. A seventh feed timed out. These observations are a snapshot, not a guarantee of future source availability. The 76 curated activity records and 3,663 positioned landmarks are available independently of discovery. [Map and navigation verification](VERIFICATION.md) · [Discovery validation](RESOURCE-DISCOVERY.md)

The public title uses the search terms “GTA 6 interactive map” and “loot tracker” to describe the tool directly. The choice follows observed wording on existing game-map sites and Google’s title guidance. Search volume and future ranking were not measured. [GTA Base map](https://www.gtabase.com/gta-6/map/) · [Google title guidance](https://developers.google.com/search/docs/appearance/title-link)

