# Advanced setup and features

## npm launcher

The npm launcher requires Node.js 22 or newer. Run it directly with npx or install it globally.

```sh
npx gta6-loot-map
npx gta6-loot-map status
npx gta6-loot-map stop
```

```sh
npm install -g gta6-loot-map
gta6-loot-map
gta6-loot-map status
gta6-loot-map stop
```

The npm launcher stores runtime files and cached data in a per-user application folder outside the installed package. It checks for Python and can install a verified private runtime on Windows, macOS and Linux. After stopping, run the installed command to restart. [Portable runtime details](PORTABLE-RUNTIME.md) · [Windows ZIP walkthrough](../README.md#windows-zip-alternative)

## ZIP and source launch options

The Windows launchers use a supported Python already installed or set up a checksum-verified portable Python in the local app folder. Run the equivalent Python command from the project folder on Windows, macOS or Linux with Python 3.10 or newer. Use `py` on Windows if that is the command your system provides.

```sh
python3 app.py
python3 app.py --bundled-only
python3 app.py --no-open
python3 app.py --status
python3 app.py --stop
```

The default launch checks optional pinned copies of the published game map and Rockstar poster for local use, with the bundled community map available if a download fails. The `--bundled-only` flag skips optional map downloads. Discovery still attempts its scheduled checks when a network is available. The `--no-open` flag keeps the server running without opening the browser. `--port PORT` sets a specific loopback port. For the normal launch you can use the URL printed in the terminal if the usual port is occupied.

On Windows, optionally register the local discovery app to start after sign-in without opening the browser. The second command removes that configuration.

```powershell
.\tools\WindowsStartup.ps1
.\tools\WindowsStartup.ps1 -Remove
```

The Windows downloader checks the SHA-256 published for its selected x64, ARM64 or 32-bit portable runtime before extracting it. The runtime stays in the app folder. Players who want the optional screenshot-matching libraries can use a normal Python installation and install the optional packages with that interpreter. [Python 3.14.10 Windows download checksums](https://www.python.org/downloads/release/python-31410/)

## Map, journal and exports

- Use **Landmarks** to filter buildings by type or **All layers** to search everything. You can search by name, region, source ID or building type. Press **/** to focus search. To select an item from overlapping pins, click the stack and choose from the list.
- In **Map appearance**, change the map layer, cartographic color treatment, interface palette and marker glow. The available UI palettes are **Vice Neon**, **Ocean Drive** and **Field Gold**. Reduced-motion settings keep a static highlight.
- The **Export center** builds a single-file printable HTML field pack with an embedded community map, optional route, checklist, steps and evidence links. Export the current filters, all activities, bounties, completed entries, personal pins or the entire atlas. CSV includes game-grid coordinates. Loot JSON retains the coordinate frame and provenance.
- In an entry, use **Share a field card** to save one location with a neighborhood map and its instructions. The route is included only when selected. A journal backup includes personal pins, progress and routes. Importing merges pins and completion records and restores routes from the backup.

## Optional positioning

Use the map or enter your game-grid X/Y in **Route planner**. For nearby stops, use **My position → Nearby activities**.

A solid route follows a connected trace of the road artwork. Dashed ends connect a marker to the traced roads. A disconnected road, offshore point or inaccessible terrain yields a labeled direct bearing. Turn cues follow the shape of the trace. The route cannot establish lane restrictions, locked interiors or mission barriers. [Route method and checks](NAVIGATION.md)

**Locate from screenshot** aligns a GTA VI pause-map image on your computer. Select your player arrow on the preview. Install the optional matching libraries into the Python interpreter that actually launches the server and use the registered in-game map for best results.

```sh
python3 -m pip install numpy opencv-python-headless
```

**Follow local coordinate feed** takes updates from an existing local integration. It polls an open, visible browser tab when enabled. Continuous tracking needs an external coordinate source. Reaching a route stop within the configured 12-unit map radius advances the itinerary when following the feed. [Position and screenshot API](API.md)

## Discovery and optional models

General discovery and Bounty Watch retain source links, filter unrelated claims, deduplicate results and report each feed’s last outcome. Broad reports may remain unlocated. The guide and map versions are independent of the discovery cache. A missed scheduled check runs at the next launch. [Source and publisher discovery](RESOURCE-DISCOVERY.md) · [Bounty coverage and controls](API.md) · [Report a location](https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker/issues/new?template=location.md)

The default no-model mode uses zero inference credits. Optional hosted inference choices include **Ollama Cloud**, which meters cloud tokens, and **OpenRouter → openrouter/free** with provider quotas. Local Ollama, OpenCode Console and compatible custom endpoints are also supported. An enabled provider receives at most one new or changed eligible public report per general discovery refresh. Server validation requires a literal source quote for extracted guidance. It derives a suggested venue position through the catalogue. Remote keys are held in process memory until restart. [Provider examples and limits](MODELS.md)

## Votes

Yes/No votes represent player feedback. Selecting the same answer again withdraws it. GitHub reactions, when available, appear as separate source feedback. Local votes are stored in SQLite. To share totals, an operator can run the included service on an existing HTTPS host.

```sh
python3 community_votes.py --port 8766
```

Reverse-proxy only the vote endpoint to that loopback port. Set the HTTPS origin in `public/community.json` on participating atlas copies. Pass the repeatable `--origin` option to trust additional atlas origins. Ballot IDs are anonymous browser identifiers. Clearing browser storage creates a new ID, so totals are advisory. No public voting service is configured by default.

## Development

The server and browser modules require no npm build, external tile service or hosted database. For optional map images, install Pillow and run the pinned map installer. Private runtime data lives in `.atlas/`.

```sh
python3 -m pip install Pillow
python3 tools/install_local_maps.py
python3 -m unittest discover -s tests -p "test_*.py"
python3 tests/player_guides_test.py
node tests/player_routing.mjs
```

The optional browser checks use Playwright and a fresh browser context. GPS registration checks need NumPy and OpenCV. [Developer API](API.md) · [Research and implementation notes](RESEARCH-AND-PLAN.md) · [Map data and rights](MAP-DATA.md) · [Barlow Condensed font license](../public/fonts/OFL.txt)
