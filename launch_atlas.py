"""Start a local atlas or reopen the one that is already running."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import sys
from threading import Thread
from urllib.request import ProxyHandler, build_opener
import webbrowser

from server import Atlas, LocalServer, PORT, ROOT
from tools.install_local_maps import (
    GAME_HASH, GAME_URL, OFFICIAL_HASH, OFFICIAL_URL, install_image,
)

URL = f"http://127.0.0.1:{PORT}/"


def existing_atlas():
    try:
        with build_opener(ProxyHandler({})).open(URL + "map-meta.json", timeout=1) as response:
            metadata = json.load(response)
        return metadata["coordinateFrame"]["name"] == "GTADB GTA VI planar game frame"
    except (OSError, ValueError, KeyError, TypeError):
        return False


def prepare_local_maps():
    directory = ROOT / ".atlas"
    directory.mkdir(exist_ok=True)
    plans = [
        (directory / "powerpyx-map-original.png", "in-game map", GAME_URL, GAME_HASH),
        (directory / "rockstar-map-original.jpg", "Rockstar poster", OFFICIAL_URL, OFFICIAL_HASH),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [(p[1], pool.submit(install_image, *p, False)) for p in plans if not p[0].is_file()]
        for name, task in tasks:
            try:
                task.result()
            except (ValueError, OSError) as exc:
                print(f"Could not install {name}: {exc}. The included community map is available.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-open", action="store_true", help="Run the server without opening a browser.")
    parser.add_argument("--bundled-only", action="store_true", help="Skip optional map downloads.")
    args = parser.parse_args()
    if not args.bundled_only:
        prepare_local_maps()
    if existing_atlas():
        print("Atlas is running at " + URL, flush=True)
        if not args.no_open:
            webbrowser.open(URL)
        return
    atlas = Atlas()
    try:
        server = LocalServer(atlas)
    except OSError:
        raise SystemExit(f"Port {PORT} is busy. Close the service using it and launch the atlas again.")
    with server:
        thread = Thread(target=atlas.worker, daemon=True)
        bounty_thread = Thread(target=atlas.bounty_worker, daemon=True, name="atlas-bounty-watch")
        thread.start()
        bounty_thread.start()
        if not args.no_open:
            webbrowser.open(URL)
        print("GTA 6 Loot Map by theihtishaam is running at " + URL + "\nKeep this server running for automatic updates. Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            atlas.stop()
            thread.join(timeout=2)
            bounty_thread.join(timeout=2)


if __name__ == "__main__":
    main()

