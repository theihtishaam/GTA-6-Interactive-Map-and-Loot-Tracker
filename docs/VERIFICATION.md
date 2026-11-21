# Verification — November 21, 2026

## Version 0.1.0

The expanded catalog has 76 unique activity guides at 71 positions and 3,663 positioned landmarks. The road graph connects 2,145 of 2,485 pairs of distinct guide positions. Sites outside a connected trace use a direct bearing. The ten-site meditation set was independently registered against source imagery. [Collectible evidence](COLLECTIBLES.md)

The integrated Python suite passed 52 tests, with five additional guide-integrity checks. Separate browser runs covered map interaction, model selection, the manual, checklists, exports, voting and GPS. Both installed-game and bundled-community map runs placed a player 432 m north of a target, moved them 120 m west of it, and verified the corresponding distance and direction on desktop and 390- and 320-pixel screens. The extracted release ran on standard-library Python, installed the two pinned original reference maps, and served its full 76-guide catalog. [Release notes](RELEASE-0.1.0.md)

## Original map and guide baseline

| Feature | Observed result |
| --- | --- |
| Map data | The import reconciled all 3,663 positioned records from a pinned 3,754-record source. The other 91 had no game position. The default locally installed layer is the in-game map. |
| Activities | All 67 curated guides have positions, covering 63 distinct places. The 50-position evidence overlay has 44 in-game shop or job markers, five mission/contact markers and one landmark anchor. Another 17 guides use named venue pins. |
| Alignment | The activity-position audit reproduced all 50 points within 0.56 reference-image pixels. The worst held-out 90th-percentile registration residual was 2.41 pixels. This measures image matching. A venue anchor still cannot establish an exact pickup inside the building. |
| Routing | The graph connected 1,891 of 1,953 pairs of distinct curated guide locations. Eleven sample route checks and four unsupported-destination checks passed. Mount Kalaga's summit correctly fell back to a bearing. |
| Player walkthrough | Fresh Chrome sessions at 1440 × 900 and 390 × 844 passed search, filtered pins, four map layers, dark style, details, votes, completion persistence, connected and disconnected routes, backup/restore, CSV export and refresh cadence changes. |
| GPS | A disposable Edge session matched a cropped game map and set a position through the image picker, then received a coordinate through the local feed. A separate benchmark recovered all 44 known published game-menu markers within one atlas pixel with the installed in-game and Day reference maps. Day-only matching accepted two of six sampled screenshots. |
| Automated tests | 28 Python API, map-data, discovery, provider, voting, GPS and registration tests passed. Five guide-integrity checks and the JavaScript routing regression checks also passed. |
| Live discovery | Five of six public sources replied on the observed run. The forum at gta.how timed out. Eight PowerPyx reports and one PC Gamer report passed the filters. These were recorded as leads with source links. The run established no new unique map position. |
| Model connections | Anonymous metadata calls to Ollama Cloud and OpenRouter succeeded and included the selected example models. Native Ollama and compatible chat request formats were tested with fixtures. Private-key inference and a locally installed Ollama model were outside the live tests. |
| Votes | Temporary SQLite and HTTP tests covered adding, replacing and withdrawing votes, calculating separate totals, and the optional shared endpoint. Local votes are scoped to an atlas installation unless an operator configures a shared service. |
| Windows startup | The local server launched successfully. The optional Windows startup helper created and removed a test shortcut in a temporary project folder. Its target and arguments were checked. |

The sources document the mapped game activities. The player review exercised the companion app. Actual console driving, mission completion against a console save, and a complete census of every collectible remain unverified.

[Map sources](MAP-DATA.md) · [Activity evidence](ACTIVITY-PINS.md) · [Navigation review](NAVIGATION.md) · [Player review](PLAYER.md)

