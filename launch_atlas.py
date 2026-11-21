"""Start a local atlas or reopen the one that is already running."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import errno
from http.client import HTTPConnection, HTTPException
import json
import os
import sys
from threading import Thread
from time import monotonic, sleep
import webbrowser

from server import Atlas, DATA_ROOT, LocalServer, PORT
from tools.install_local_maps import (
    GAME_HASH, GAME_URL, OFFICIAL_HASH, OFFICIAL_URL, install_image,
)

RUNTIME = DATA_ROOT


@contextmanager
def installation_lock(directory):
    # The OS releases this lock even when the console is closed abruptly.
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "launcher.lock").open("a+b") as handle:
        if not handle.seek(0, os.SEEK_END):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            yield False
        else:
            yield True


def last_session(directory):
    try:
        item = json.loads((directory / "launcher.json").read_text("utf-8"))
        if (isinstance(item, dict) and type(item.get("port")) is int and 0 < item["port"] <= 65535
                and isinstance(item.get("instance"), str) and len(item["instance"]) == 32):
            return item
    except (OSError, ValueError):
        pass
    return {}


def control(port, method, endpoint, payload=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        connection.request(method, endpoint, body, {"Content-Type": "application/json"} if body else {})
        response = connection.getresponse()
        if response.status == 200:
            result = json.loads(response.read(1025))
            if isinstance(result, dict):
                return result
    except (ValueError, OSError, HTTPException):
        pass
    finally:
        connection.close()
    return {}


def active_session(directory):
    deadline = monotonic() + 5
    while True:
        item = last_session(directory)
        if item:
            live = control(item["port"], "GET", "/api/launcher")
            if live.get("app") == "gta6-loot-map" and live.get("instance") == item["instance"]:
                return item
        if monotonic() >= deadline:
            return {}
        sleep(0.1)


@contextmanager
def launcher_session(directory):
    deadline = monotonic() + 90
    while True:
        with installation_lock(directory) as owner:
            if owner:
                yield None
                return
            item = active_session(directory)
            if item:
                yield item
                return
        if monotonic() >= deadline:
            raise OSError("The other atlas window is still busy. Close that launcher window and try again.")
        print("Waiting for the other atlas window to finish...", flush=True)
        sleep(0.5)


def bind_server(atlas, saved_port, requested_port):
    ports = [requested_port] if requested_port is not None else [
        saved_port, *range(PORT, PORT + 10), 0,
    ]
    for port in dict.fromkeys(ports):
        if port is None:
            continue
        try:
            return LocalServer(atlas, port)
        except OSError as exc:
            if exc.errno not in (errno.EADDRINUSE, errno.EACCES, 10048, 10013) or requested_port is not None or port == 0:
                raise
    raise OSError("Could not open a local port.")


def prepare_local_maps():
    directory = RUNTIME
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
            except (ValueError, OSError, HTTPException) as exc:
                print(f"Could not install {name}: {exc}. The included community map is available.", file=sys.stderr)


def run(args):
    if (args.stop or args.status) and not (RUNTIME / "launcher.lock").exists():
        print("GTA 6 Loot Map is already stopped.")
        return
    with launcher_session(RUNTIME) as item:
        if item:
            url = f"http://127.0.0.1:{item['port']}/"
            if args.stop:
                result = control(item["port"], "POST", "/api/launcher/stop", {"instance": item["instance"]})
                if not result.get("stopping"):
                    raise OSError("Could not confirm shutdown. Press Ctrl+C in the atlas window.")
                print("Stopping GTA 6 Loot Map. You can close the browser tab.", flush=True)
            else:
                print("The map is already running at " + url, flush=True)
                if not args.no_open and not args.status:
                    webbrowser.open(url)
            return
        if args.stop or args.status:
            print("GTA 6 Loot Map is already stopped.")
            return

        previous = last_session(RUNTIME)
        atlas = Atlas()
        with bind_server(atlas, previous.get("port"), args.port) as server:
            port = server.server_port
            url = f"http://127.0.0.1:{port}/"
            temp = RUNTIME / "launcher.tmp"
            temp.write_text(json.dumps({"port": port, "instance": atlas.instance}), encoding="utf-8")
            temp.replace(RUNTIME / "launcher.json")
            print("GTA 6 Loot Map is running at " + url, flush=True)
            print(f"Using Python {sys.version.split()[0]}.", flush=True)
            if args.port is None and port != (previous.get("port") or PORT):
                print("The usual port is busy. The atlas selected an available port.", flush=True)
            print("To stop, choose Settings > Stop server or press Ctrl+C.", flush=True)

            def open_map():
                if not args.bundled_only:
                    print("Checking the optional game map and poster...", flush=True)
                    prepare_local_maps()
                if not args.no_open and not atlas.stopping:
                    webbrowser.open(url)

            workers = [Thread(target=atlas.worker, daemon=True), Thread(target=atlas.bounty_worker, daemon=True)]
            try:
                for worker in workers:
                    worker.start()
                Thread(target=open_map, daemon=True).start()
                server.serve_forever(poll_interval=0.15)
            except KeyboardInterrupt:
                pass
            finally:
                atlas.stop()
        # Release the listener straight away. Finish any active writes before
        # allowing a second launcher to use this installation's data.
        for worker in workers:
            worker.join()
        print("GTA 6 Loot Map stopped.", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--stop", action="store_true", help="Stop the atlas running from this folder.")
    action.add_argument("--status", action="store_true", help="Show whether this copy is running and its local address.")
    parser.add_argument("--no-open", action="store_true", help="Run without opening a browser.")
    parser.add_argument("--bundled-only", action="store_true", help="Skip optional map downloads.")
    parser.add_argument("--port", type=int, help="Use a specific port. The default finds a free port automatically.")
    args = parser.parse_args(argv)
    if args.port is not None and not 0 <= args.port <= 65535:
        parser.error("The port must be between 0 and 65535.")
    try:
        run(args)
    except OSError as exc:
        print(f"Could not start or control the map: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
