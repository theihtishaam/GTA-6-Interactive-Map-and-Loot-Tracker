# Activity pins and source evidence

The atlas can place all 67 curated game guides. The source-backed overlay contributes 50 positions. The remaining 17 use named community landmarks already linked in the guides.

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
