# Player guide coverage

Reviewed November 21, 2026. The bundled guides combine gameplay walkthroughs, in-game map screenshots and community venue positions. A job or shop marker shows the location selected in the game's map index. A mission marker takes you to the activity's starting point or contact. A venue pin takes you to a building or place. Check the guide for the room, prerequisite or objective that awards the item.

| Category | Entries | Job or shop marker | Mission or contact | Venue or landmark | What a player can track |
| --- | ---: | ---: | ---: | ---: | --- |
| Heists and jobs | 31 | 29 | 1 | 1 | 22 bank jobs, seven payday jobs, Vicki’s Delights job and Yasmani’s vault introduction |
| Earbuds | 15 | 15 | 0 | 0 | Named electronics retailers to check in the Style index. Stock and price depend on the shop. |
| Bags | 1 | 0 | 1 | 0 | The Chapter 1 story unlock for the duffel bag |
| Collectibles | 12 | 0 | 1 | 11 | Cards, magazines, a watch, a sculpture scan and a summit meditation |
| Rewards | 8 | 0 | 2 | 6 | Treasure diving, a trophy, race medals and edition-specific rewards |
| Bounties | 0 | 0 | 0 | 0 | Awaiting a named GTA VI activity with evidence |
| Gloves | 0 | 0 | 0 | 0 | Awaiting a documented GTA VI equipment unlock or shop purchase |

All 67 guides have a map position, covering 63 distinct coordinates. The seven payday jobs and 22 bank jobs each have a separate marker and progress entry. Some Ocean Beach banks share their brand and district. Use the source marker, branch type and reported take to tell them apart. [Bank jobs](https://www.powerpyx.com/gta-6-all-bank-jobs-locations-bank-vaults/) · [Bank types and payouts](https://games.gg/grand-theft-auto-vi/guides/all-bank-locations-gta-6/) · [Payday jobs](https://www.powerpyx.com/gta-6-all-payday-loans-jobs-locations/)

## How the evidence was used

- Each guide has its own gameplay source. Seventeen positions come from a named GTADB venue. Fifty guide rows use registered screenshots with the source image, selected pixel and alignment statistics. These include 44 job or shop markers, five mission or contact entries and the shop landmark for Marquise's card. The Kingpin Bowling watch and trophy share the same mission start and have separate checklists. [Guide coordinates](../public/guide-positions.json) · [Marquise's card](https://www.powerpyx.com/gta-6-los-santos-panic-collectible-card-set-locations/) · [GTADB map sources](https://github.com/rolux/gtadb.org)
- Rockstar confirms that both protagonists can use audio equipment on foot. GamesRadar+ describes buying and equipping it, and PowerPyx lists the electronics vendors. The Hamlet Zekes Gadgets entry uses the branch’s in-game screenshot. A similarly named community landmark exists in Rockridge. [Rockstar audio announcement](https://www.rockstargames.com/newswire/article/o3982oa93a23k4/the-music-of-grand-theft-auto-vi-in-game-radio-stations) · [GamesRadar+ equipment walkthrough](https://www.gamesradar.com/games/grand-theft-auto/gta-6-headphones-music-radio-podcasts-how-to-use/) · [Electronics shop list](https://www.powerpyx.com/gta-6-all-electronics-stores-locations/) · [Branch districts](https://www.gta-xtreme.com/gta-6/locations/electronics-stores)
- The bag is acquired during a story mission in Key Lento. Its guide points the player to the in-game mission marker. [Equipment unlocks](https://www.powerpyx.com/gta-6-all-equipment/) · [Lab Fees walkthrough](https://www.powerpyx.com/gta-6-lab-fees-collect-brians-rent-walkthrough/)
- The Delights job and Kingpin Bowling watch have specific Chapter 2 prerequisites. The former also specifies when the player receives payment. [Afternoon Delight](https://www.powerpyx.com/gta-6-afternoon-delight-rob-vickis-boss-walkthrough/) · [Kingpin Bowling](https://www.powerpyx.com/gta-6-hit-kingpin-bowling-walkthrough/)
- Individual written collectibles and cards are independently tickable, including ones that share a building. Edition-specific apparel and garage entries identify the required edition. [Key Lento field guide](https://www.pushsquare.com/guides/gta-6-key-lento-collectibles-and-secrets-walkthrough) · [Reading collectibles](https://www.powerpyx.com/gta-6-all-magazines-books-comics-locations/) · [Delights Dancers cards](https://www.powerpyx.com/gta-6-delights-dancers-collectible-card-set-locations/) · [Ultimate Edition guide](https://www.pcgamer.com/games/grand-theft-auto/gta-6-ultimate-edition-bonuses/)
- Searches for GTA VI bounty targets returned Rockstar’s earlier GTA Online bail business and unrelated community prize contests. The player who reported looking for gloves reached Chapter 2 and found no store stocking them. Neither observation establishes that the game has zero such items. [Rockstar’s Bottom Dollar announcement](https://www.rockstargames.com/newswire/article/51195a98k31273/gta-online-bottom-dollar-bounties-out-now) · [Player glove search](https://www.reddit.com/r/GTA/comments/1y0rtdg/no_gloves/)

The source authors played or documented the game. This project's independent checks cover the cited information, the map joins and the companion's behavior. Console save data and physical collectible positions were outside those checks.

## Repeating the player checks

Run `python tests/player_guides_test.py` to verify the guide records, their sources and their joins to public map positions. Run `node tests/player_routing.mjs` to exercise geographic routes with the same solver the interface uses.

With Google Chrome and Python Playwright installed, run `python tests/player_walkthrough.py`. The walkthrough starts an isolated local server and uses temporary storage and a fresh browser context at each viewport. It opens an earbud guide, changes and removes a helpfulness vote, sets a starting position, marks the guide complete and checks GPS directions to Delights. It tests the summit's direct bearing, a road route to the duffel bag mission start and the empty bounty category. It also downloads and restores a journal backup, verifies the filtered CSV and saves a six-hour schedule with model inference disabled. The desktop viewport is 1440 × 900 and the narrow viewport is 390 × 844.

Add `--screenshots test-results/player` for local visual evidence. Add `--installed-layers` after downloading the optional reference maps to exercise each one. All test data stays in a temporary directory except the screenshots explicitly requested on the command line.
