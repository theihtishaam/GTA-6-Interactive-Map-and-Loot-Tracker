"""Exercise the standard-library launcher and Windows double-click entry points in fresh copies."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import launch_atlas
from server import Atlas


def fresh_copy(parent, name, full_assets=False):
    project = parent / name
    project.mkdir()
    for path in (*ROOT.glob("*.py"), ROOT / "VERSION", ROOT / "Start Atlas.cmd", ROOT / "Stop Atlas.cmd"):
        shutil.copy2(path, project / path.name)
    (project / "tools").mkdir()
    for filename in ("install_local_maps.py", "WindowsLauncher.ps1"):
        shutil.copy2(ROOT / "tools" / filename, project / "tools" / filename)
    if full_assets:
        shutil.copytree(ROOT / "public", project / "public")
    else:
        (project / "public").mkdir()
        for filename in ("index.html", "community.json"):
            shutil.copy2(ROOT / "public" / filename, project / "public" / filename)
    cache = project / ".atlas"
    cache.mkdir()
    # Keep both real scheduling threads asleep for the entire test; no feed fetches.
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    state = {"interval": 24, "reports": [], "sources": [], "lastRun": future}
    (cache / "state.json").write_text(json.dumps({**state, "bounty": state}), encoding="utf8")
    return project


def execute(project, args):
    return subprocess.Popen(args, cwd=project, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace",
                            env={**os.environ, "GTA6_LOOT_MAP_DATA": str(project / ".atlas")},
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def atlas_command(*args):
    return [sys.executable, "-S", "app.py", "--no-open", "--bundled-only", *args]


def windows_command(action, *args):
    return ["cmd.exe", "/d", "/c", "call", action + " Atlas.cmd", *args]


def api(port, method, path, payload=None):
    if port == 8765:
        raise AssertionError("Launcher tests use dedicated loopback ports.")
    conn = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        body = None if payload is None else json.dumps(payload).encode()
        conn.request(method, path, body, {"Content-Type": "application/json"} if body else {})
        response = conn.getresponse()
        content = response.read()
        return response.status, json.loads(content) if path.startswith("/api/") else content
    finally:
        conn.close()


def ready(project, *, previous=None):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            row = json.loads((project / ".atlas/launcher.json").read_text("utf8"))
            if row.get("instance") != previous:
                status, live = api(row["port"], "GET", "/api/launcher")
                if status == 200 and live["app"] == "gta6-loot-map" and row["instance"] == live["instance"]:
                    return row
        except (OSError, ValueError):
            pass
        time.sleep(.05)
    raise AssertionError(f"No ready instance in temporary copy {project.name}")


def finish(process, expected=0):
    output, _ = process.communicate(timeout=15)
    if (process.returncode == 0) != (expected == 0):
        raise AssertionError(f"Unexpected launcher exit {process.returncode}: {output}")
    return output


@contextmanager
def sandbox_copy(folder, name, full_assets=False):
    project = fresh_copy(folder, name, full_assets)
    children = []
    def run(args):
        proc = execute(project, args)
        children.append(proc)
        return proc
    try:
        yield project, run
    finally:
        if any(child.poll() is None for child in children):
            try:
                row = json.loads((project / ".atlas/launcher.json").read_text("utf8"))
                status, current = api(row["port"], "GET", "/api/launcher")
                if status == 200 and current.get("instance") == row["instance"]:
                    api(row["port"], "POST", "/api/launcher/stop", {"instance": row["instance"]})
            except (OSError, ValueError):
                pass
        for child in children:
            try:
                if child.poll() is None:
                    child.wait(timeout=4)
            except subprocess.TimeoutExpired:
                child.terminate()  # Only a subprocess this context created in the disposable copy.
                child.wait(timeout=4)
            if child.stdout:
                child.stdout.close()


def occupied_socket():
    while True:
        sock = socket.socket()
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", 0))
        if 1024 < sock.getsockname()[1] < 65526:
            sock.listen()
            return sock
        sock.close()


class LauncherTests(unittest.TestCase):
    def test_busy_default_finds_another_port_and_explicit_busy_port_fails(self):
        with tempfile.TemporaryDirectory(prefix="atlas-test-") as folder:
            with sandbox_copy(Path(folder), "busy port test") as (project, run), occupied_socket() as busy:
                port = busy.getsockname()[1]
                # Exercise the exact default scan on an isolated port range.
                with patch.object(launch_atlas, "PORT", port):
                    app = Atlas(project / ".atlas/state.json", project / "public")
                    with launch_atlas.bind_server(app, None, None) as server:
                        self.assertNotEqual(port, server.server_port)
                self.assertIn("Could not", finish(run(atlas_command("--port", str(port))), expected=1))
                self.assertFalse((project / ".atlas/launcher.json").exists())
                self.assertEqual(busy.getsockname()[1], port)

    def test_simultaneous_starts_reuse_origin_and_stop_only_this_copy(self):
        with tempfile.TemporaryDirectory(prefix="atlas-test-") as folder:
            with sandbox_copy(Path(folder), "first atlas") as (a, run_a), sandbox_copy(Path(folder), "second atlas") as (b, run_b):
                children = [run_a(atlas_command("--port", "0")) for _ in range(2)]
                first = ready(a)
                deadline = time.monotonic() + 7
                while all(p.poll() is None for p in children) and time.monotonic() < deadline:
                    time.sleep(.05)
                owners = [p for p in children if p.poll() is None]
                self.assertEqual(len(owners), 1)
                reopened = finish(next(p for p in children if p is not owners[0]))
                self.assertIn("already running", reopened)
                self.assertIn(str(first["port"]), reopened)
                second_process = run_b(atlas_command("--port", "0"))
                second = ready(b)
                self.assertNotEqual(first["port"], second["port"])
                self.assertNotEqual(first["instance"], second["instance"])
                self.assertEqual(api(first["port"], "POST", "/api/launcher/stop", {"instance": second["instance"]})[0], 409)
                self.assertEqual(api(first["port"], "GET", "/api/launcher")[0], 200)
                finish(run_a(atlas_command("--stop")))
                finish(owners[0])
                self.assertIsNone(second_process.poll())
                self.assertEqual(api(second["port"], "GET", "/api/launcher")[1]["instance"], second["instance"])
                restarted_process = run_a(atlas_command())
                restarted = ready(a, previous=first["instance"])
                self.assertEqual(restarted["port"], first["port"])
                self.assertNotEqual(restarted["instance"], first["instance"])
                self.assertEqual(api(first["port"], "POST", "/api/launcher/stop", {"instance": first["instance"]})[0], 409)
                finish(run_a(atlas_command("--stop")))
                finish(restarted_process)
                # A stopped folder cannot stop another live copy, even with its stale metadata.
                (a / ".atlas/launcher.json").write_text(json.dumps(second), encoding="utf8")
                self.assertIn("already stopped", finish(run_a(atlas_command("--stop"))))
                self.assertEqual(api(second["port"], "GET", "/api/launcher")[1]["instance"], second["instance"])
                finish(run_b(atlas_command("--stop")))
                finish(second_process)
                self.assertIn("already stopped", finish(run_b(atlas_command("--stop"))))

    def test_fallback_port_survives_restart_after_default_becomes_available(self):
        with tempfile.TemporaryDirectory(prefix="atlas-test-") as folder:
            with sandbox_copy(Path(folder), "persistent fallback") as (project, run):
                with occupied_socket() as busy:
                    preferred = busy.getsockname()[1]
                    # Only the default port changes inside this disposable child. It runs the
                    # real app.main() with no explicit --port on both launches.
                    boot = ("import launch_atlas, app; "
                            f"launch_atlas.PORT = {preferred}; raise SystemExit(app.main())")
                    command = [sys.executable, "-S", "-c", boot, "--no-open", "--bundled-only"]
                    process = run(command)
                    first = ready(project)
                    self.assertNotEqual(first["port"], preferred)
                    finish(run(atlas_command("--stop")))
                    self.assertIn("usual port is busy", finish(process))
                restarted = run(command)
                after = ready(project, previous=first["instance"])
                self.assertEqual(after["port"], first["port"])
                finish(run(atlas_command("--stop")))
                finish(restarted)

    @unittest.skipUnless(os.name == "nt", "Windows launcher")
    def test_start_stop_cmd_with_standard_installed_python(self):
        with tempfile.TemporaryDirectory(prefix="atlas-test-") as folder:
            with sandbox_copy(Path(folder), "Windows source copy") as (project, run):
                self.assertIn("already stopped", finish(run(windows_command("Stop"))))
                proc = run(windows_command("Start", "-BundledOnly", "-NoOpen", "-Port", "0"))
                row = ready(project)
                self.assertIn(b"Leonida", api(row["port"], "GET", "/")[1])
                self.assertFalse((project / ".atlas/runtime").exists())
                self.assertIn("Stopping", finish(run(windows_command("Stop"))))
                finish(proc)

    def test_old_python_gets_an_actionable_version_message(self):
        import app
        from contextlib import redirect_stdout
        from io import StringIO
        with patch.object(app.sys, "version_info", (3, 9)), redirect_stdout(StringIO()) as output:
            self.assertEqual(app.main(), 1)
        self.assertIn("3.10", output.getvalue())


if __name__ == "__main__":
    unittest.main()
