# Navigation coverage

Choose a known place and select **Set as my position**, or place a starting point in Route planner. Pick a destination and select **Route here**. Solid segments follow connected road strokes in the community map. Dashed segments join the chosen points to those roads. When the points have no connected road trace, the planner labels the dashed leg as a direct bearing.

The starting position comes from the player or an optional local coordinate feed. Route planner includes manual placement, grid entry and a local screenshot locator. Following a live position requires a separate integration that supplies game coordinates to the local server. The game itself can guide you through lanes, closed roads, one-way streets and grade-separated crossings. The source is a flat map, so a bridge can appear to intersect the road below it. Thin or obscured streets can be missing. The map cannot establish whether a gate, driveway or building entrance is accessible during your mission.

## Building the road graph

The workflow reads the bundled YANIS v18 map at its original 3456 × 4864 resolution. It identifies light road strokes, removes broad bright fills and closes gaps of a few pixels. It then downsamples to 1728 × 2432, retaining thin lines, and traces their centerlines. The mask excludes the interior runway areas at VCIA and Mile Zero. Short isolated marks are discarded to reduce text and building artifacts. The output contains 12,645 vertices and 13,724 undirected edges in a 311 kB file. It loads locally on the first requested route.

Map imagery and derived cartography are attributed to YANIS, GTADB and the GTA VI Mapping Community under CC BY 4.0. The game map layers use the same atlas road graph, transformed into the selected layer's display coordinates. [Map source and registration](MAP-DATA.md) · [Pinned GTADB source](https://github.com/rolux/gtadb.org/tree/d406fea099e1df2bce42fd6b87eed04bce646629) · [Data license](https://creativecommons.org/licenses/by/4.0/)

To reproduce the graph with Python, install Pillow, NumPy, SciPy and scikit-image. Run `python tools/build_roads.py` from the repository root. To validate the distributed graph with Node, run `node tests/player_routing.mjs`.

## What was checked

Sixty-two of the 63 distinct guide locations in the November 21 gameplay catalogue snap to one connected road network with the browser's 16-pixel search radius. That permits 1,891 of 1,953 distinct location pairs to route. The earlier graph connected 140 pairs on the same test. The sample includes the 44 job or shop map markers, the mission contacts and the venue anchors. These counts measure connectedness for this catalogue. They give no estimate of turn-by-turn accuracy or of game-wide road coverage.

The routes below were drawn over both the YANIS map and the registered GTADB Day street map. Visual checks covered intercity links, water crossings and city approaches. GTADB Day served as an independent rendering of the area. Only the distributed YANIS map is needed to rebuild the graph.

| Start | Destination | Browser solver |
| --- | --- | --- |
| Game Horde, Port Gellhorn | ShoreFront, Downtown Vice City | Connected |
| The Rusty Anchor, Key Lento | Boone Speedway, Hamlet | Connected |
| Ambrosia Raceway Park | Gellhorn International Raceway | Connected |
| Stock 305, Stockyard | Paradise Garage, Watson Bay | Connected |
| Delights, Port Gellhorn | Game Horde, Port Gellhorn | Connected |
| Fleeca, Key Lento | Shorefront, Ambrosia | Connected between in-game markers |
| Quick Buck, Hamlet | Lombank vault, Downtown | Connected between in-game markers |
| Shorefront, Downtown | Shorefront, Rockridge | Connected between in-game markers |
| Kingpin Bowling, Port Gellhorn | Lab Fees, Key Lento | Connected between mission starts |
| Yasmani's café | Kenton's dive shop | Connected between mission contacts |
| Quick Buck, Hamlet | Marquise card, Key Lento | Connected to the shop where the guide places the card |
| Game Horde, Port Gellhorn | Mount Kalaga summit meditation | Direct bearing |

The summit, open sea and sampled interior runway points stay outside street guidance. In-game driving verification is still outstanding.
