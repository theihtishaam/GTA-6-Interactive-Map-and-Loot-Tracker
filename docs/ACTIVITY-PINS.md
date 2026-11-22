# Activity pins and source evidence

The atlas can place all 75 base guides. The source-backed overlay contributes 50 positions. The other 25 use named community landmarks, including eight [sports and games guides](NEW-GUIDES.md).

| Overlay precision | Guides | What the marker locates |
| --- | ---: | --- |
| Map marker | 44 | The selected branch or store in the published in-game menu |
| Mission marker | 5 | The unlocking mission, activity start, or quest contact |
| Landmark | 1 | Kenton’s shop in the Marquise Bernard card walkthrough |

## Published sources

The 44 menu positions cover all 22 bank job and vault branches, 15 electronics stores including Game Horde, and seven payday loan branches. Each activity carries a link to the walkthrough and the specific screenshot in guide-positions.json. The most similarly named branches have distinct pins. [Bank jobs and bank vaults](https://www.powerpyx.com/gta-6-all-bank-jobs-locations-bank-vaults/) · [Electronics stores](https://www.powerpyx.com/gta-6-all-electronics-stores-locations/) · [Payday loan jobs](https://www.powerpyx.com/gta-6-all-payday-loans-jobs-locations/)

The duffel-bag position points to the mission start. The bag equips automatically during the mission. The two Kingpin guides share one mission marker. Kenton’s marker points to the contact who offers diving quests. Yasmani’s marker points to the café for the introduction. These positions identify where players start the associated activity. [Lab Fees](https://www.powerpyx.com/gta-6-lab-fees-collect-brians-rent-walkthrough/) · [Hit Kingpin Bowling](https://www.powerpyx.com/gta-6-hit-kingpin-bowling-walkthrough/) · [Kenton’s sets](https://www.powerpyx.com/gta-6-100-completion-checklist-guide/) · [Yasmani café](https://www.powerpyx.com/gta-6-thats-where-the-money-is-wait-at-the-cafe-walkthrough/)

The Marquise Bernard source shows both a close map of Kenton’s shop and the card on its porch. The pin uses the mapped position at the shop. [Los Santos Panic cards](https://www.powerpyx.com/gta-6-los-santos-panic-collectible-card-set-locations/)

## Image registration

The selected markers are read in 1920 × 1080 game screenshots. SIFT and RANSAC match roads and coastline against the full in-game reference. The published affine in game-map-meta.json converts from that reference to the common atlas frame. The guide overlay stores normalized coordinates in that frame. Each source image is SHA-256 pinned. The verifier uses distinct matches and reserves 20% as held-out controls, measuring their residuals and checking the fitted marker against the distributed position. Residuals measure image alignment and do not establish exact physical entrances or pickup coordinates. The atlas package includes only the derived positions, source links, and verification data. Audit screenshots remain in a local, ignored directory.

The audit reproduced all 50 mapped overlay positions. Each used at least 20 held-out matches. The largest held-out 90th-percentile residual was 2.41 pixels, and the largest difference from a distributed marker was 0.56 pixels in the in-game reference.

    python tools/install_local_maps.py --layer game
    python -m pip install opencv-python-headless numpy
    python tools/verify_activity_positions.py --download
    python -m unittest discover -s tests -p test_activity_positions.py

## Mission starting markers

The separate mission-positions.json overlay registers **82** selected, published PowerPyx mission markers to the common atlas frame. The current 176-entry catalogue has 17 screenshot-aligned starts in Chapter 1, 14 in Chapter 2, 31 in Chapter 3, and 20 in Chapter 4. The Prologue and Chapter 5 have no included screenshot-derived starts. Individual entries carry the walkthrough, screenshot URL and hash, selected source-image pixel and map registration statistics. [Mission walkthrough index](https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/)

The review checks the selected icon and its title or first location interaction against the walkthrough. Phone calls that reveal a physical start are treated differently from missions that begin during the call or transition. A motel room interaction starts Checking Out after the call. Clock Out begins on acceptance during the call and therefore has no mission-start pin. [Checking Out](https://www.powerpyx.com/gta-6-checking-out-move-to-vice-city-walkthrough/) · [Clock Out](https://www.powerpyx.com/gta-6-clock-out-walkthrough/)

Of the 112 current start-image candidates, 16 lacked sufficient registration evidence and 14 were excluded for ambiguous markers, non-map screenshots, grouped activities, or later objectives. The remaining 64 catalogue records have no eligible start image. This includes 31 starts classified as automatic, remote, or unmarked. Existing independently linked venue pins are separate from this count.

At least 19 held-out features support every included alignment. The largest held-out 90th-percentile residual was 2.46 pixels in the pinned in-game reference. The measure describes image alignment. The pin selects the in-game marker; an interior start or trigger may require following the walkthrough after arrival. The distributed files include only derived coordinates and source metadata. Audit images stay in the ignored local cache.

    python tools/install_local_maps.py --layer game
    python -m pip install opencv-python-headless numpy
    python tools/verify_mission_positions.py --download
    python -m unittest discover -s tests -p test_mission_positions.py
