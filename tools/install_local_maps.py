import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import tempfile
import urllib.request


OFFICIAL_URL = (
    "https://www.rockstargames.com/VI/_next/static/media/"
    "Leonida_Map_Poster.08ir77j-.26ny.jpg"
)
OFFICIAL_HASH = "689554e17d8ce324f8d7c1bf213355c668ed990dbca113864694af07f3b4cc2d"
OFFICIAL_SIZE = (2805, 3840)
GAME_URL = "https://www.powerpyx.com/wp-content/uploads/gta-6-full-world-map.png"
GAME_HASH = "9c31e4ae4af0536a1e6fef3599754e1d2eefcfdf88f3d32093b7958424c85561"
GAME_SIZE = (2676, 3446)
DAY_MANIFEST = Path(__file__).with_name("gtadb-day-tiles.sha256")
PROJECT = Path(__file__).resolve().parents[1]


def install_image(target, description, url, expected_hash, offline):
    if target.exists() or offline:
        source = target.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=25) as response:
            source = response.read(20 * 1024 * 1024 + 1)
    if sha256(source).hexdigest() != expected_hash:
        raise ValueError(f"The {description} does not match the pinned SHA-256.")
    # Matching the pinned full-file hash also verifies the exact format and dimensions
    # checked by the map importer. New players need only the Python standard library.
    if target.exists():
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=target.suffix, delete=False) as temporary:
        temporary.write(source)
        path = Path(temporary.name)
    try:
        path.replace(target)
    finally:
        path.unlink(missing_ok=True)


def install_day(cache, runtime, offline):
    try:
        from .import_gtadb import build_map, fetch, read_tile_hashes
    except ImportError:
        from import_gtadb import build_map, fetch, read_tile_hashes
    if not offline:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda path: fetch(cache, path), read_tile_hashes(DAY_MANIFEST)))
    with tempfile.NamedTemporaryFile(dir=runtime, suffix=".webp", delete=False) as temporary:
        path = Path(temporary.name)
    try:
        build_map(cache, path, manifest=DAY_MANIFEST, ocean=(47, 144, 176))
        path.replace(runtime / "day-map.webp")
    finally:
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Install local-only GTA VI map presentation assets.")
    parser.add_argument("--cache", type=Path, default=PROJECT / ".gtadb-import")
    parser.add_argument("--runtime", type=Path, default=PROJECT / ".atlas")
    parser.add_argument("--offline", action="store_true", help="Reuse locally cached sources.")
    parser.add_argument("--layer", choices=("game", "poster", "day", "all"), default="all")
    args = parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=True)
    if args.layer in ("poster", "all"):
        install_image(args.runtime / "rockstar-map-original.jpg", "Rockstar poster",
                      OFFICIAL_URL, OFFICIAL_HASH, args.offline)
    if args.layer in ("game", "all"):
        install_image(args.runtime / "powerpyx-map-original.png", "PowerPyx in-game map",
                      GAME_URL, GAME_HASH, args.offline)
    if args.layer in ("day", "all"):
        install_day(args.cache, args.runtime, args.offline)


if __name__ == "__main__":
    main()
