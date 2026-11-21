"""Exercise the Windows npm package in a fresh offline cache and global prefix."""

from datetime import datetime, timezone
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
from shutil import which
import socket
from subprocess import CREATE_NO_WINDOW, PIPE, STDOUT, Popen, run
import sys
import tarfile
from tempfile import TemporaryDirectory
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "gta6-loot-map"
ADDRESS = re.compile(r"http://127\.0\.0\.1:(\d+)/")


def test_environment(work, data_dir):
    allowed = ("Path", "PATHEXT", "SystemRoot", "SystemDrive", "COMSPEC",
               "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432", "LOCALAPPDATA",
               "APPDATA", "USERPROFILE", "ProgramFiles", "ProgramFiles(x86)",
               "ProgramW6432", "ProgramData", "WINDIR")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    for name in ("user.npmrc", "global.npmrc"):
        (work / name).write_text("", encoding="ascii")
    environment.update(
        GTA6_LOOT_MAP_DATA=str(data_dir),
        NPM_CONFIG_USERCONFIG=str(work / "user.npmrc"),
        NPM_CONFIG_GLOBALCONFIG=str(work / "global.npmrc"),
        NPM_CONFIG_CACHE=str(work / "npm-cache"),
        NPM_CONFIG_OFFLINE="true",
        NPM_CONFIG_UPDATE_NOTIFIER="false",
        NPM_CONFIG_AUDIT="false",
        NPM_CONFIG_FUND="false",
        TEMP=str(work),
        TMP=str(work),
    )
    return environment


def fixture(data_dir):
    # Set the next discovery runs in the future so this launch stays loopback-only.
    now = datetime.now(timezone.utc).isoformat()
    initial = {"interval": 24, "reports": [], "sources": [], "lastRun": now}
    data_dir.mkdir()
    (data_dir / "state.json").write_text(json.dumps({**initial, "bounty": initial}), encoding="utf-8")


def command(args, work, environment, expected=0):
    result = run(args, cwd=work, env=environment, stdout=PIPE, stderr=STDOUT,
                 text=True, encoding="utf-8", errors="replace", timeout=90, creationflags=CREATE_NO_WINDOW)
    assert result.returncode == expected, f"{args[0]} exited {result.returncode}: {result.stdout}"
    return result.stdout


def request(port, method, path, payload=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    try:
        connection.request(method, path, json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        content = response.read()
        assert response.status == 200, (path, response.status)
        return content
    finally:
        connection.close()


def url_when_ready(process, log):
    deadline = monotonic() + 30
    while monotonic() < deadline:
        output = log.read_text(encoding="utf-8", errors="replace")
        address = ADDRESS.search(output)
        if address:
            port = int(address.group(1))
            request(port, "GET", "/")
            return port
        if process.poll() is not None:
            raise AssertionError(f"Launcher exited {process.returncode}: {output}")
        sleep(.15)
    raise AssertionError("Launch timed out.")


def start(args, log, work, environment):
    with log.open("wb") as output:
        return Popen(args, cwd=work, env=environment, stdout=output, stderr=STDOUT,
                     creationflags=CREATE_NO_WINDOW)


def package_paths(archive):
    with tarfile.open(archive, "r:gz") as package:
        paths = set(package.getnames())
    mandatory = {
        "package/bin/gta6-loot-map.mjs", "package/bin/portable-python.mjs",
        "package/tools/WindowsLauncher.ps1", "package/tools/install_local_maps.py",
        "package/public/index.html", "package/public/map.webp", "package/public/themes.css",
    }
    assert mandatory <= paths, mandatory - paths
    forbidden = {"package/public/game-map.png", "package/public/official-map.jpg",
                 "package/public/day-map.webp"}
    assert paths.isdisjoint(forbidden), paths & forbidden
    assert not any("/.atlas/" in name or name.endswith((".exe", "/state.json")) for name in paths), paths
    return len(paths)


def main():
    if sys.platform != "win32":
        print("This walkthrough is for Windows.")
        return
    npm, npx = which("npm.cmd"), which("npx.cmd")
    if not npm or not npx:
        raise RuntimeError("Node.js, npm and npx must be installed.")
    metadata = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="gta6-npm-walkthrough-") as temporary:
        work = Path(temporary)
        data = work / "Player Data"
        prefix = work / "Global Prefix"
        environment = test_environment(work, data)
        fixture(data)
        packed = json.loads(command([npm, "pack", "--offline", "--ignore-scripts",
                                     "--json", str(ROOT)], work, environment))
        entry = packed[0] if isinstance(packed, list) else packed.get(PACKAGE, packed)
        archive = work / entry["filename"]
        print(f"Packed {archive.name} with {package_paths(archive)} shipped paths.", flush=True)
        call_npx = [npx, "--offline", "--yes", "--package", str(archive), "--", PACKAGE]
        npx_version = command([*call_npx, "--version"], work, environment).strip()
        assert npx_version.splitlines()[-1:] == [metadata["version"]], npx_version
        print("npx resolved the local tarball with an isolated offline cache.", flush=True)

        install = [npm, "install", "--offline", "--ignore-scripts", "--global",
                   "--prefix", str(prefix), str(archive)]
        command(install, work, environment)
        shim = str(prefix / (PACKAGE + ".cmd"))
        assert Path(shim).is_file()
        assert command([shim, "--version"], work, environment).strip() == metadata["version"]
        assert "already stopped" in command([shim, "status"], work, environment)
        print("Isolated npm global installation and generated shim passed.", flush=True)

        with socket.socket() as occupied:
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            occupied.bind(("127.0.0.1", 0))
            occupied.listen(1)
            active_port = occupied.getsockname()[1]
            refused = command([shim, "start", "--no-open", "--bundled-only",
                               "--port", str(active_port)], work, environment, expected=1)
            assert "Could not start or control" in refused, refused
        print("An occupied explicit port failed cleanly.", flush=True)

        options = ["start", "--no-open", "--bundled-only", "--port", "0"]
        log = work / "npx-launch.log"
        process = start([*call_npx, *options], log, work, environment)
        try:
            port = url_when_ready(process, log)
            address = f"http://127.0.0.1:{port}/"
            assert address in command([shim, "status"], work, environment)
            second = command([shim, *options], work, environment)
            assert "already running" in second and address in second, second
            assert b"GTA 6 Loot Map" in request(port, "GET", "/")
            assert request(port, "GET", "/map.webp").startswith(b"RIFF")
            updated = json.loads(request(port, "POST", "/api/settings", {"interval": 6}))
            assert updated["interval"] == 6, updated
            assert "Stopping" in command([shim, "stop"], work, environment)
            assert process.wait(timeout=30) == 0
        finally:
            if process.poll() is None:
                command([shim, "stop"], work, environment)
                process.wait(timeout=30)
        assert "already stopped" in command([shim, "status"], work, environment)
        print("npx started the map, the second launch reused the active port, and the global shim stopped it.", flush=True)

        command([npm, "uninstall", "--offline", "--global", "--prefix", str(prefix), PACKAGE],
                work, environment)
        assert not Path(shim).exists()
        command(install, work, environment)
        log = work / "shim-launch.log"
        process = start([shim, *options], log, work, environment)
        try:
            port = url_when_ready(process, log)
            saved = json.loads(request(port, "GET", "/api/state"))
            assert saved["interval"] == 6
            assert "already running" in command([shim, "status"], work, environment)
        finally:
            command([shim, "stop"], work, environment)
            assert process.wait(timeout=30) == 0
        print("Global shim start and persisted player settings passed after uninstall/reinstall.", flush=True)


if __name__ == "__main__":
    main()
