# Leonida Loot Atlas — research and implementation plan

Research date: November 21, 2026. The question driving this build is whether a player can go from a community tip to a useful destination, see what supports it, and remember finishing it.

## 1. Map and spatial reference

Rockstar lists GTA VI for PS5 and Xbox Series X|S and offers a printable Leonida map. The official poster is a valuable reference for a player comparing a location in-game. Its download page does not provide the georeferenced point feed, route graph or open redistribution license this application needs. Link the poster in the interface. [Official game page](https://www.rockstargames.com/VI) · [Rockstar media](https://www.rockstargames.com/VI/media)

GTADB publishes the underlying landmark catalogue and map images with explicit reuse terms. Use a pinned revision of the artwork and catalogue together, retain attribution in the map and exports, and convert positions once into the same north-up image frame. A web client can then pan, zoom and search offline. The upstream maintainer asks consumers to obtain updates from the repository. A map revision change must include a registration check so a shifted image cannot silently displace thousands of existing markers. [GTADB repository](https://github.com/rolux/gtadb.org) · [Data license](https://github.com/rolux/gtadb.org/blob/main/LICENSE-DATA)

## 2. What qualifies as a discovery

A named place establishes geography. A reported reward needs its own evidence. For example, a player guide names several fences, their districts and their unlock missions. Two can share a district and have different unlock conditions. A district cannot identify which building to visit. Keep a separate activity ID for each encounter, its actual unlock steps and its source. A nearby venue may anchor an area lead only when the association is explicit. [PC Gamer’s firsthand fence guide](https://www.pcgamer.com/games/grand-theft-auto/gta-6-fence-locations/)

Keep heists, bounties, rewards, earbuds, gloves, bags and other collectibles separately searchable. Include a category when its catalogue is empty. The interface should tell the player when no sourced entries exist and let them add their own field note. Exclude GTA V, GTA Online and real-world counterpart coordinates from GTA VI reward pins. Avoid a percentage likelihood unless an evaluated dataset supports it.

## 3. Player workflow

Start with the map and a searchable index. Group nearby landmarks at wide zooms, give activities their own icons, and open the same detail view from search results or a map pin. Show the available steps, attribution and location precision. Separate completed entries from remaining ones using stable IDs, and support a JSON backup of records, progress, personal positions and routes. CSV gives players a simple filtered list. Map and checklist actions should have a keyboard path.

An external web app needs a player-supplied in-game starting point. Provide placement by click or by known map entry. Let the player choose a destination and add stops to follow visible roads or a discovered trail. Document the distinction between a map route and game telemetry. Public GIS experiments describe road topology and turn restrictions, but their geometry, reuse rights and alignment require separate verification before importing them. [Leonida GIS project](https://github.com/wpenistone/leonida_gis)

## 4. Refresh and persistence

Make the scheduler part of the local server so it works when the tab is closed. Default to 24 hours and offer 6 hours and manual refresh. Fetch a small bounded set from public communities, classify deterministic matches first, retain a source URL and deduplicate. Preserve the last usable cache when a source is unavailable. Surface each source’s last attempt, errors and matched count so an empty feed can be distinguished from an unavailable one. Recalculate the next check after a cadence change. No operating-system task or mandatory cloud hosting is needed.

## 5. Providers and cost

Prioritize direct Ollama Cloud access. Its native chat endpoint supports bearer authentication, and local Ollama offers a compatible native interface without an account for installed local models. Ollama Cloud’s current documentation says structured outputs are unavailable there. Request compact text, validate the answer, and discard unsupported claims. Never treat model-proposed coordinates as evidence. Ollama Cloud quotas and available models depend on the account and can change. [Cloud](https://docs.ollama.com/cloud) · [Authentication](https://docs.ollama.com/api/authentication) · [Chat API](https://docs.ollama.com/api/chat)

OpenRouter exposes an explicit free router. OpenCode Console states its free-tier chat models require the OpenCode client. Offer compatible external access subject to the provider’s rules, describe potential charges at configuration time, and do not automatically substitute a paid model. The startup configuration performs zero model calls. Use optional enrichment only for a small number of new reports. [OpenRouter free router](https://openrouter.ai/openrouter/free) · [OpenCode model terms](https://opencode.ai/docs/console/models/)

## 6. Delivery and verification sequence

1. Pin the licensed map, reproduce its registration, count usable landmarks and document coverage.
2. Research named activities, verify the cited gameplay evidence, and join only substantiated venues.
3. Build the offline atlas and journal, then exercise search, filters, detail views, position placement, navigation and exports with models disabled.
4. Integrate source refresh, bounded optional model enrichment and provider failure reporting. Test malformed outputs, offline operation, duplicate updates and cadence changes.
5. Ask an independent player reviewer to try real tasks at desktop and narrow widths. Resolve observed usability problems. Report which providers, sources and gameplay claims received live verification.

## Coverage after release

Treat new guides as versioned additions. For collectibles, record the item, precise place or area, prerequisite, interaction and reward separately. For bounties, require a GTA VI mission or activity identifier and check that the source is describing this game's mode. For recurring events, include start and end evidence before introducing time-based availability. A complete loot census needs an authoritative denominator or independently reconciled playthrough records. A count of imported landmarks cannot measure that.

## Implemented map and GPS revisions

The default local view uses the actual in-game map published by PowerPyx. An affine transform registers the community coordinate frame to it, including a separate held-out test. The launcher also installs the original Rockstar poster for an alternate view. The screenshot locator can match a player-selected pause-map image locally. The route planner can follow coordinates supplied by an external local integration. See the [activity measurements](ACTIVITY-PINS.md), [map registration](MAP-DATA.md), [route evaluation](NAVIGATION.md) and [GPS API](API.md).
