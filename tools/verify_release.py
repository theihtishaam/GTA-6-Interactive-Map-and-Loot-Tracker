"""Test the extracted source release with the Python standard library only."""
import argparse
from pathlib import Path
import re
from subprocess import run
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SMOKE = """
import json
from pathlib import Path
from threading import Thread
from urllib.request import ProxyHandler, Request, build_opener
from server import Atlas, LocalServer
from launch_atlas import prepare_local_maps
import sys

if '--maps' in sys.argv:
    prepare_local_maps()
atlas = Atlas()
with LocalServer(atlas, 0) as server:
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        origin = 'http://127.0.0.1:' + str(server.server_port)
        opener = build_opener(ProxyHandler({}))
        def get(path): return json.load(opener.open(origin+path, timeout=8))
        files = ['/','/map.webp','/roads.json','/app.mjs','/activity-types.mjs','/field-manual.mjs','/export-center.mjs','/settings.mjs','/map-upgrade.css','/source-view.mjs','/missions.mjs','/missions.css','/goals.mjs','/goals.css','/mission-positions.json']
        if '--maps' in sys.argv: files += ['/official-map.jpg','/game-map.png']
        for path in files:
            assert opener.open(Request(origin+path,method='HEAD'),timeout=8).status == 200,path
        rows = {r['id']:r for r in get('/guides.json')}
        for id_, values in get('/guide-positions.json').items(): rows[id_].update(values)
        for r in get('/collectible-guides.json'): rows[r['id']] = r
        assert len(rows) == 84 and all(0 <= r['x'] <= 1 and 0 <= r['y'] <= 1 for r in rows.values())
        assert {r.get('subcategory') for r in rows.values() if r['category']=='leisure'} == {'Pool','Golf','Fitness','Arcade'}
        assert len(get('/landmarks.json')) == 3663
        missions = get('/missions.json')
        ids = {m['id'] for m in missions}
        assert len(ids) == len(missions) and len(missions) >= 150
        assert set(get('/mission-positions.json')) <= ids
        assert get('/api/state')['version'] == Path('VERSION').read_text().strip()
        assert get('/api/bounty/state')['interval'] == 24
        print(f"Clean archive served {len(rows)} positioned activity guides, {len(missions)} mission builds, 3,663 landmarks and all selected map layers.")
    finally:
        server.shutdown()
        worker.join()
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maps", action="store_true", help="Also fetch and serve the two pinned original map sources.")
    args = parser.parse_args()
    archive = ROOT / "release" / "Leonida-Loot-Atlas-source.zip"
    with TemporaryDirectory(prefix="atlas-source-audit-") as folder, ZipFile(archive) as package:
        assert package.testzip() is None
        for name in package.namelist():
            p = Path(name)
            assert not p.is_absolute() and p.parts[0] == "Leonida-Loot-Atlas" and ".." not in p.parts
            assert set(p.parts).isdisjoint({".git",".atlas",".gtadb-import","release","test-results","__pycache__"})
            assert p.suffix.lower() not in {".jpg",".jpeg",".png",".sqlite",".sqlite3",".db",".env"}
        package.extractall(folder)
        project = Path(folder) / "Leonida-Loot-Atlas"
        readme = (project / "README.md").read_text(encoding="utf-8")
        version = (project / "VERSION").read_text(encoding="utf-8").strip()
        image_root = f"https://raw.githubusercontent.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker/v{version}/"
        images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
        badges = re.findall(r"\[!\[([^\]]+)\]\((https://[^)]+)\)\]\((https://[^)]+)\)", readme)
        assert {label: (image, target) for label, image, target in badges} == {
            "Weekly and lifetime npm downloads for GTA 6 Loot Map": (
                "https://raw.githubusercontent.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker/download-stats/.github/badges/npm-downloads.svg",
                "https://www.npmjs.com/package/gta6-loot-map"),
            "GitHub profile of @theihtishaam": (
                "https://img.shields.io/badge/GitHub-%40theihtishaam-24292f?logo=github&logoColor=white",
                "https://github.com/theihtishaam"),
        }
        game_badge = "https://img.shields.io/badge/GTA%206-Leonida-d45485?labelColor=292042"
        assert f"![GTA 6 – Leonida]({game_badge})" in readme.splitlines()
        badge_urls = {url for _, url, _ in badges} | {game_badge}
        artwork = [image for image in images if image not in badge_urls]
        assert len(artwork) >= 8
        for image in artwork:
            assert image.startswith(image_root + "docs/"), image
            assert (project / image.removeprefix(image_root)).is_file(), image
        assert all((project / name).is_file() for name in ("Start Atlas.cmd", "Stop Atlas.cmd", "tools/WindowsLauncher.ps1"))
        run([sys.executable, "-S", "app.py", "--status"], cwd=project, check=True, timeout=12)
        command = [sys.executable, "-S", "-c", SMOKE] + (["--maps"] if args.maps else [])
        run(command, cwd=project, check=True, timeout=105)


if __name__ == "__main__":
    main()

