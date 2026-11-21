# Local API

Start with `python server.py`. Open `http://127.0.0.1:8765`. Requests use local HTTP and JSON. Browser requests must come from the same origin. The server binds to IPv4 loopback.

| Method | Route | JSON body | Success |
| --- | --- | --- | --- |
| GET | /api/state | — | State |
| POST | /api/settings | `{"interval":6}`, `{"interval":12}`, or `{"interval":24}` | State |
| POST | /api/refresh | `{}` | State, with HTTP 202 while the refresh runs |
| GET | /api/bounty/state | — | Bounty Watch state |
| POST | /api/bounty/settings | `{"interval":6}`, `{"interval":12}`, or `{"interval":24}` | Bounty Watch state |
| POST | /api/bounty/refresh | `{}` | Bounty Watch state, with HTTP 202 while the refresh runs |
| POST | /api/provider | See below | State |
| POST | /api/provider/models | `{}` to probe the saved provider. Optional `{kind,model,base,key}` to probe an unsaved selection. | `{models:[string],selectedAvailable:boolean|null}` |
| GET | /api/votes?id=… | Optional `X-Atlas-Player` header | `{up,down,mine}` |
| POST | /api/votes | `{id,player,vote}` | `{up,down,mine}` |
| POST | /api/locate | `{image,pixelX,pixelY}` | `{x,y,matched,inliers,errorPixels}` |
| GET | /api/position | — | `{x,y,updatedAt}` or JSON `null` |
| POST | /api/position | `{x,y}`, `{gameX,gameY}` or `{"clear":true}` | `{x,y,updatedAt}` or JSON `null` |

Errors return `{error:string}`. State includes `reports`, `sources`, `interval` (hours), `running` (boolean), `lastRun`, `nextRun` (UTC ISO 8601 time or null), `provider` and `cacheError` (string or null). Concurrent refresh requests share the run already in progress. A first run starts at server launch if no cached refresh exists. The schedule runs only while the server process is running, including when the browser is closed.

The `bounty` field in general state mirrors `GET /api/bounty/state`. It has its own `reports`, `sources`, `interval`, `running`, `lastRun` and `nextRun`. Both schedules default to 24 hours. Bounty Watch persists its cadence and records separately inside the existing cache. A targeted run leaves the general scan and its schedule alone. Bounty Watch calls no AI provider.

The Watch searches GitHub public issues, Bluesky public posts, Lemmy.world's indexed posts, and PowerPyx guide feeds using bounty and wanted-poster queries. It also screens public channel feeds from GTA Series Videos and IGN, the mastodon.social `#GTA6` feed, and the gta.how forum syndication feed. Video coverage consists of titles and descriptions. No member-only threads, comments, credentials, scraping of private sessions or paid APIs are used. Source rows add `platform` and `coverage` and use the `manual` status for Reddit, X, GTAForums.com, Rockstar Discord and Rockstar Newswire links that the atlas does not poll. `seen` counts distinct records parsed from a platform's bounded requests and `matched` counts reports passing the evidence gate before cross-platform deduplication. A partial endpoint failure is visible on its source row. Existing findings stay in the cache through outages.

Bounty reports add `platform` and `watchStatus` of `source claim`. They require post-launch GTA VI evidence about a result or a concrete guide. Early firsthand publisher guides retain the November 18 exception. The Watch excludes other GTA games, bug bounties and real-world giveaways, predictions, non-findings and questions without an outcome. It deduplicates source URLs and exact substantive copies, retaining related source links in `relatedSources`. A zero result means that the checked sources produced no eligible finding during that run. Coverage is finite and concentrated on English game and bounty terms.

Reports use `{id,title,category,region,x,y,source,sourceName,details,steps,confidence,publishedAt,landmarkId}`. `category` is one of heist, bounty, reward, earbuds, gloves, bag, collectible or landmark. `source` is the public link. `x` and `y` are normalized map coordinates or null. `confidence` is `lead` for an unresolved source or `area` for a match to a documented landmark. Area matches mark the landmark's coordinates as an approximation. `landmarkId` and `publishedAt` are nullable. Source health uses `{id,name,url,status,checkedAt,seen,matched,error}`, where status is `pending`, `ok`, or `error`. Seen counts parsed records and matched counts eligible records before deduplication. Failed sources leave the accumulated cache in place.

GitHub report records include `communityVotes:{up,down,url}` when the source returns valid thumbs-up and thumbs-down counts. The votes API counts entries cast through the atlas.

Screenshot positioning is optional. Install OpenCV with `python -m pip install opencv-python-headless` and install a registered local reference with `python tools/install_local_maps.py --layer game` or `--layer day`. The application can otherwise run on the Python standard library. Send a bare base64 JPEG up to 950 KB with a longest edge at most 1200 px, a shortest edge of at least 240 px, and the selected arrow coordinates in image pixels. The entire JSON body is capped at 1.3 MB. The server never stores or forwards the image. It aligns feature points from the visible map to the installed reference and transforms the selected point into canonical coordinates. `matched` counts distinct candidate matches, `inliers` counts geometric matches, and `errorPixels` is the 90th-percentile registration residual for held-out inliers, in canonical atlas pixels. That residual does not measure how accurately an arrow was selected. Empty images, unrelated images, competing alignments, and clicks far from reliable controls fail with 400. Unavailable OpenCV, missing reference layers, and a matcher already processing another screenshot return 503.

The position API accepts normalized atlas coordinates with x east and y south, or signed values from the game coordinate frame in `public/map-meta.json` with gameX east and gameY north. Position updates are explicit and remain in memory until replaced, cleared, or the server stops. `updatedAt` is server UTC time. The feed has no native console or game connection.

Use the In-game reference for actual pause-map screenshots. With both registered references available, the matcher returned 44 of 44 published PowerPyx pause-map markers within one atlas pixel of their registered guide positions after resizing screenshots to 1200 px. In a smaller Day-only check it returned two of six markers and rejected the other four. These checks use known guide markers, so they do not establish coverage across all player screenshots, zoom levels, menu overlays or display settings.

The anonymous source registry contains GitHub public issues plus GTA Forums at gta.how, GTA6.how, GamesRadar+, PowerPyx, and PC Gamer syndication feeds. The PowerPyx poll uses four bounded topic feeds for bank vaults, collectible cards, electronics stores, and equipment. Discovery considers entries dated November 19, 2026 onward. Same-domain coverage from PowerPyx and PC Gamer is also eligible on November 18, when their firsthand launch guides began publishing. GTA VI reward or location terminology must appear in the title, with a plausible discovery or acquisition signal in the title or excerpt. Feed readers never follow result links automatically. Coverage depends on what publishers and community members expose through these endpoints.

A report gets an approximate pin only when the headline or an acquisition-related sentence explicitly names a single matching atlas venue. Ambiguous references and collection guides that cover multiple locations remain unpinned.

Provider settings accept `{kind,model,base,key,enabled,allowPaid}`. The kind is one of `none`, `ollama-cloud`, `ollama-local`, `openrouter`, `opencode`, or `custom`. `enabled` defaults to false when omitted. The app uses at most one extraction request per refresh, sending only a bounded excerpt of a new or changed public lead. Quote matching limits any returned steps to text directly present in the source. The provider cannot set coordinates, add reports, write files, or issue further network requests.

Built-in cloud endpoints are fixed. Ollama Cloud uses bearer authentication and asks for plain JSON text. Ollama Local defaults to `http://127.0.0.1:11434` and accepts a loopback base. OpenRouter defaults to `openrouter/free`. Enable `allowPaid` for Ollama Cloud, metered OpenRouter models, OpenCode Console, or a remote custom endpoint. [OpenCode's free chat models require its own client](https://opencode.ai/docs/console/models/#free-models), so use OpenRouter's free routes or local Ollama for a no-billing alternative. Custom uses an OpenAI-compatible base including its API root (usually ending in `/v1`), with HTTPS for remote servers and HTTP allowed for loopback. Provider metadata probing consumes no inference. Remote metadata endpoints may still require authentication.

Provider state returns `{kind,model,base,enabled,allowPaid,hasKey,active,lastStatus}`. `active` means configured and enabled locally. Model availability requires a provider probe. Non-secret provider preferences persist locally. Keys stay in process memory until restart. Local Ollama enrichment can resume on its own. Cloud providers need a new in-app key after restarting. Omit `key` to keep the current key for the same provider and base, or pass an empty string to clear it. HTTP redirects on provider calls are refused. Provider responses and API errors never include upstream response text or configured keys.

A single-location GitHub issue can include an explicit signed GTA VI grid marker, formatted as ATLAS_GTA6_GRID=(X,Y). The source and both coordinates must pass validation. A published pin is labeled player-reported. Model-assisted area matching requires a unique catalogued game name, an exact quote from the excerpt, and an acquisition or reward relationship. Model-generated numbers are ignored.

## Source images

GET /api/media?entry=ID returns cached image metadata or a null media field. POST /api/media accepts an entry ID and looks up evidence already linked to that entry. The local /media/ endpoint serves content-addressed JPEG, PNG and WebP files. Article previews and specific screenshots have distinct captions.

## Release

GET /api/state includes the application version. The v0.1.0 source inventory, model choice and source ranking are documented in [release notes](RELEASE-0.1.0.md), [model research](MODELS.md) and [resource discovery](RESOURCE-DISCOVERY.md).
