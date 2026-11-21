# Community map data and credits

**GTA VI Map Tiles (CC BY 4.0)** by YANIS, the GTA VI Mapping Community, gtadb.org and all contributors. **GTA VI Landmarks Data (CC BY 4.0)** by gtadb.org and all contributors. Copyright © 2025–2026 GTADB.ORG and contributors. [GTADB map](https://map.gtadb.org) · [Source and contributor history](https://github.com/rolux/gtadb.org/tree/d406fea099e1df2bce42fd6b87eed04bce646629) · [Upstream license declaration](https://github.com/rolux/gtadb.org/blob/d406fea099e1df2bce42fd6b87eed04bce646629/LICENSE-DATA) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

The atlas uses YANIS v18 community cartography. Geography and point placements are community estimates. The upstream catalogue includes unconfirmed entries, historical features, and names matched to real-world counterparts by community contributors.

## Map registration and adaptations

- Mosaicked 280 pinned level 3 YANIS v18 JPEG tiles, cropped to the full visible geography and adjacent ocean, and encoded WebP at 3456 × 4864. The crop excludes the right-side reference panel with video stills. The atlas includes no separately supplied landmark photos.
- The 8192 × 8192 source grid uses (column × 256, row × 256) tile offsets at four game units per pixel. The north-up game origin (0, 0) sits at the full grid's center. The crop is [1536, 1472, 4992, 6336] in level 3 pixels with exclusive right and bottom edges. The crop spans −10240 to 3584 on the game x axis and −8960 to 10496 on the game y axis.
- Normalized coordinates are x = (gameX + 10240) / 13824 and y = (10496 − gameY) / 19456. The y axis increases down the image. The import retains all 3,663 records with game coordinates, including 983 records with a source game name, 1,350 displayed by an identified real-world counterpart, and 1,330 unnamed entries labeled by type and source ID. The 91 source records without game coordinates cannot be placed. The import preserves source IDs, names, links, and raw evidence tags. Discovery only matches source game titles for venue alignment. [Source tiles](https://github.com/rolux/gtadb.org/tree/d406fea099e1df2bce42fd6b87eed04bce646629/maps/tiles/6/yanis%2C18/3) · [Tile generation](https://github.com/rolux/gtadb.org/blob/d406fea099e1df2bce42fd6b87eed04bce646629/maps/tiles.py) · [Landmark source](https://github.com/rolux/gtadb.org/blob/d406fea099e1df2bce42fd6b87eed04bce646629/map/data/6/landmarks.json)

The data and adapted map assets are under CC BY 4.0. The atlas is an independent fan project. Grand Theft Auto and associated marks belong to their respective owners.

## Rebuild and verify

Run the following commands from the project root. The import retrieves the pinned static files from GitHub. The atlas serves the prepared assets locally. The importer checks SHA-256 for the source catalogue and each tile.

    python -m pip install Pillow==12.3.0
    python tools/import_gtadb.py
    python -m unittest discover -s tests -p test_gtadb_import.py

The --offline option reuses the .gtadb-import/ cache. The integrity tests verify the distributed dataset and add a full rebuild comparison when the source cache is present.

## Locally installed map layers

Install the optional image layers from their pinned public sources. The installer writes to the ignored .atlas/ runtime directory. The redistributed project contains source links, image dimensions, registration metadata and hashes. It does not bundle the local map images.

    python tools/install_local_maps.py
    python tools/install_local_maps.py --layer game
    python tools/install_local_maps.py --layer poster
    python tools/install_local_maps.py --layer day

- **In-game map.** 2676 × 3446 PNG published by PowerPyx as the full in-game map. The installer retains the exact source image, including title, watermarks and margins. Rockstar Games and PowerPyx retain their respective rights. [PowerPyx source](https://www.powerpyx.com/gta-6-full-world-map-revealed/)
- **Rockstar poster.** 2805 × 3840 JPEG downloaded directly from Rockstar's public static media. The original publisher map includes its frame, legend, roads and labels. The installer preserves the image and does not assign it a reuse license. [Rockstar release announcement](https://www.rockstargames.com/newswire/article/39akk424a9oo53/grand-theft-auto-vi-now-available) · [Rockstar image](https://www.rockstargames.com/VI/_next/static/media/Leonida_Map_Poster.08ir77j-.26ny.jpg)
- **GTADB Day.** 3456 × 4864 registered composite of 280 level 3 tiles from the pinned GTADB Day set. The Day and YANIS crops use the same upstream frame. Upstream includes Day in its general data-license declaration and labels this layer “official” in the tile generator. The exact original artwork provenance is unclear, so installation is local. [Day tiles](https://github.com/rolux/gtadb.org/tree/d406fea099e1df2bce42fd6b87eed04bce646629/maps/tiles/6/day) · [Tile generator](https://github.com/rolux/gtadb.org/blob/d406fea099e1df2bce42fd6b87eed04bce646629/maps/tiles.py)

Affines in game-map-meta.json and official-map-meta.json map community raster pixels to original image pixels. The fit uses road and coastline image features across northern, central and southern Leonida. OpenCV SIFT matches are split with a fixed random seed into 75% training and 25% held-out candidates. RANSAC rejects implausible train pairs. Held-out pairs count as accepted within two comparison pixels at the common comparison height of 1500 px. For each original map, reported residuals are in its native image pixels and use the accepted held-out pairs. Registration measures the fit between imagery layers. Individual community landmark placements can still differ from their locations in the game.

| Map | Accepted held-out pairs | Median error | 90th percentile error |
| --- | ---: | ---: | ---: |
| In-game map | 115 of 126 | 0.93 px | 2.26 px |
| Rockstar poster | 183 of 185 | 0.41 px | 1.11 px |

The optional registration diagnostic needs OpenCV and NumPy. Run it from the repository root after installing the maps.

    python -m pip install opencv-python-headless numpy
    python tools/verify_map_registration.py

