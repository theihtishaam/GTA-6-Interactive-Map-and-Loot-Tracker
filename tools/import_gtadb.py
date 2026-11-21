#!/usr/bin/env python3
"""Build the locally served map and landmark catalogue from pinned GTADB files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import urllib.request

from PIL import Image

REVISION = "d406fea099e1df2bce42fd6b87eed04bce646629"
ROOT_URL = f"https://raw.githubusercontent.com/rolux/gtadb.org/{REVISION}"
REPOSITORY = f"https://github.com/rolux/gtadb.org/tree/{REVISION}"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LANDMARK_HASH = "e251f3e6ad89834959340d5408c51118f68b36c3d9c7801cfa34bcc745993ae8"
TILE_SET = "yanis,18"
LEVEL = 3
TILE_SIZE = 256
WORLD_HALF = 16384
UNITS_PER_PIXEL = 4
CROP = (1536, 1472, 4992, 6336)
LEFT, TOP, RIGHT, BOTTOM = CROP
WIDTH, HEIGHT = RIGHT - LEFT, BOTTOM - TOP
MIN_X, MAX_X = LEFT * UNITS_PER_PIXEL - WORLD_HALF, RIGHT * UNITS_PER_PIXEL - WORLD_HALF
MAX_Y, MIN_Y = WORLD_HALF - TOP * UNITS_PER_PIXEL, WORLD_HALF - BOTTOM * UNITS_PER_PIXEL
OCEAN = (44, 103, 164)
ATTRIBUTION = "YANIS and the GTA VI Mapping Community · gtadb.org and all contributors"
TILE_MANIFEST = Path(__file__).with_name("gtadb-tiles.sha256")
FEATURE_TYPES = {
    "construction", "events", "government", "hotel", "industrial", "landmark",
    "leisure", "natural", "office", "public", "residential", "restaurant",
    "retail", "transportation", "utilities",
}


def tile_files():
    # Intersect the crop with the upstream level 3 tile footprint.
    for row in range(max(TOP // TILE_SIZE, 5), min((BOTTOM - 1) // TILE_SIZE, 24) + 1):
        for column in range(max(LEFT // TILE_SIZE, 5), min((RIGHT - 1) // TILE_SIZE, 25) + 1):
            yield row, column, f"maps/tiles/6/{TILE_SET}/{LEVEL}/{LEVEL},{row},{column}.jpg"


def fetch(cache, path):
    target = cache / path
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(f"{ROOT_URL}/{path}", timeout=30) as response:
            payload = response.read()
        target.write_bytes(payload)
    return target


def read_tile_hashes(manifest):
    return {
        path: hash_value for hash_value, path in (
            line.split("  ", 1) for line in manifest.read_text(encoding="ascii").splitlines()
        )
    }


def build_map(cache, output, manifest=TILE_MANIFEST, ocean=OCEAN):
    raster = Image.new("RGB", (WIDTH, HEIGHT), ocean)
    for path, hash_value in read_tile_hashes(manifest).items():
        _, row, column = map(int, Path(path).stem.split(","))
        tile_path = cache / path
        if sha256(tile_path.read_bytes()).hexdigest() != hash_value:
            raise ValueError(f"Unexpected tile checksum at {path}")
        with Image.open(tile_path) as tile:
            if tile.size != (TILE_SIZE, TILE_SIZE):
                raise ValueError(f"Unexpected tile dimensions at {path}")
            raster.paste(tile, (column * TILE_SIZE - LEFT, row * TILE_SIZE - TOP))
    raster.save(output, "WEBP", quality=88, method=6)


def project(x, y):
    return (x - MIN_X) / (MAX_X - MIN_X), (MAX_Y - y) / (MAX_Y - MIN_Y)


def build_landmarks(rows):
    for landmark_id, row in rows.items():
        source_name, coordinates, _, counterpart, _, _, tags, _, _ = row
        if not coordinates:
            continue
        name, *area = [part.strip() for part in source_name.split(",")]
        counterpart = counterpart.strip()
        feature_type = next((tag for tag in tags if tag in FEATURE_TYPES), "landmark")
        details = [f"GTADB entry {landmark_id}."]
        if name not in ("", "?"):
            title, name_origin = name, "game"
        elif counterpart:
            title, name_origin = counterpart.split(",", 1)[0].strip() or counterpart, "counterpart"
            details.append("The displayed name is the real-world counterpart.")
        else:
            type_label = {
                "residential": "residential building",
                "industrial": "industrial site",
                "retail": "retail location",
                "natural": "natural feature",
            }.get(feature_type, feature_type)
            title, name_origin = f"Unnamed {type_label} · {landmark_id}", "placeholder"
            details.append("GTADB has no in-game name or identified real-world counterpart for this location.")
        region = ", ".join(area) if area else "Leonida"
        x, y = project(*coordinates)
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError(f"{landmark_id} falls outside the crop")
        if counterpart:
            details.append(f"Community-linked real-world counterpart: {counterpart}.")
        community_status = [tag for tag in tags if tag in {"closed", "demolished", "unconfirmed"}]
        if community_status:
            details.append(f"GTADB flags: {', '.join(community_status)}.")
        yield {
            "id": f"gtadb-{landmark_id}", "title": title, "category": "landmark",
            "region": region, "x": round(x, 8), "y": round(y, 8),
            "source": f"https://map.gtadb.org/#VI,{landmark_id}", "details": " ".join(details),
            "steps": [], "confidence": "community", "type": feature_type,
            "nameOrigin": name_origin, "sourceTags": tags,
        }


def save_json(path, value, indent=None):
    path.write_text(json.dumps(value, indent=indent, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".gtadb-import"))
    parser.add_argument("--output", type=Path, default=Path("public"))
    parser.add_argument("--offline", action="store_true", help="Read only the pinned files in the cache")
    args = parser.parse_args()

    landmark_path = "map/data/6/landmarks.json"
    if not args.offline:
        paths = [landmark_path, *(path for _, _, path in tile_files())]
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda path: fetch(args.cache, path), paths))

    landmark_data = (args.cache / landmark_path).read_bytes()
    if sha256(landmark_data).hexdigest() != LANDMARK_HASH:
        raise ValueError("The landmark snapshot does not match the pinned SHA-256.")
    rows = json.loads(landmark_data)
    landmarks = list(build_landmarks(rows))
    args.output.mkdir(parents=True, exist_ok=True)
    build_map(args.cache, args.output / "map.webp")
    save_json(args.output / "landmarks.json", landmarks)
    save_json(args.output / "map-meta.json", {
        "image": "/map.webp",
        "width": WIDTH,
        "height": HEIGHT,
        "revision": REVISION,
        "source": REPOSITORY,
        "attribution": ATTRIBUTION,
        "license": "CC BY 4.0",
        "licenseUrl": LICENSE_URL,
        "tileSet": TILE_SET,
        "tileLevel": LEVEL,
        "landmarkCount": len(landmarks),
        "sourceLandmarkCount": len(rows),
        "coordinateFrame": {
            "name": "GTADB GTA VI planar game frame",
            "pixelOrigin": "top-left",
            "normalizedX": "east",
            "normalizedY": "south",
            "cropPixels": list(CROP),
            "minX": MIN_X, "maxX": MAX_X, "minY": MIN_Y, "maxY": MAX_Y,
            "gameUnitsPerPixel": UNITS_PER_PIXEL,
        },
    }, indent=2)


if __name__ == "__main__":
    main()
