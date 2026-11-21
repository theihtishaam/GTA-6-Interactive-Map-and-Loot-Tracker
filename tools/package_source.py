"""Create a portable source release from the project's public distribution files."""
from pathlib import Path
from shutil import copyfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "README.md", "LICENSE", "PRODUCT.md", "VERSION", "package.json", ".gitignore", ".gitattributes", "Start Atlas.cmd", "Stop Atlas.cmd", "app.py", "launch_atlas.py",
    "server.py", "discovery.py", "bounty_watch.py", "mission_watch.py", "media_cache.py", "resource_discovery.py", "report_verification.py", "providers.py", "votes.py", "gps.py", "community_votes.py",
)
DIR_FILES = {
    "bin": {".mjs"},
    "public": {".html", ".css", ".mjs", ".json", ".webp", ".svg", ".ttf", ".txt"},
    "docs": {".md", ".webp"}, "tools": {".py", ".sha256", ".ps1"}, "tests": {".py", ".mjs"},
    ".github/ISSUE_TEMPLATE": {".md"},
}


def main():
    destination = ROOT / "release" / "Leonida-Loot-Atlas-source.zip"
    destination.parent.mkdir(exist_ok=True)
    paths = [ROOT / name for name in ROOT_FILES]
    for directory, suffixes in DIR_FILES.items():
        paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in suffixes)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as out:
        for p in sorted(paths):
            out.write(p, "Leonida-Loot-Atlas/" + p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(destination) as out:
        assert out.testzip() is None
    version = (ROOT / "VERSION").read_text().strip()
    copyfile(destination, destination.with_name(f"GTA-6-Interactive-Map-and-Loot-Tracker-v{version}.zip"))
    print(f"{destination.name}: {len(paths)} files, {destination.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()

