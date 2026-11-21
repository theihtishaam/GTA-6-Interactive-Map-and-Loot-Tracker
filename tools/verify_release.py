"""Test the extracted source release with the Python standard library only."""
import argparse
from pathlib import Path
from subprocess import run
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SMOKE = """
import json
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
        files = ['/','/map.webp','/roads.json','/app.mjs','/field-manual.mjs','/export-center.mjs','/settings.mjs','/map-upgrade.css','/source-view.mjs']
        if '--maps' in sys.argv: files += ['/official-map.jpg','/game-map.png']
        for path in files:
            assert opener.open(Request(origin+path,method='HEAD'),timeout=8).status == 200,path
        rows = {r['id']:r for r in get('/guides.json')}
        for id_, values in get('/guide-positions.json').items(): rows[id_].update(values)
        for r in get('/collectible-guides.json'): rows[r['id']] = r
        assert len(rows) == 76 and all(0 <= r['x'] <= 1 and 0 <= r['y'] <= 1 for r in rows.values())
        assert len(get('/landmarks.json')) == 3663
        assert get('/api/state')['version'] == '0.1.0'
        assert get('/api/bounty/state')['interval'] == 24
        print('Clean archive served 76 positioned guides, 3,663 landmarks, 0.1.0 API and all selected map layers.')
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
        command = [sys.executable, "-S", "-c", SMOKE] + (["--maps"] if args.maps else [])
        run(command, cwd=Path(folder) / "Leonida-Loot-Atlas", check=True, timeout=105)


if __name__ == "__main__":
    main()

