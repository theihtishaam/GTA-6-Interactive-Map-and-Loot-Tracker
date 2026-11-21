"""One editable ballot per browser identifier and entry; contains no provider data."""
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
PLAYER = re.compile(r"[0-9a-f-]{36}\Z")


def shared_origin(public_dir):
    try:
        value = json.loads((Path(public_dir) / "community.json").read_text("utf-8")).get("origin", "")
        url = urlsplit(value)
        if url.scheme != "https" or url.username or url.password or url.query or url.fragment:
            return ""
        if url.path not in ("", "/") or not re.fullmatch(r"[A-Za-z0-9.-]+(:[0-9]{1,5})?", url.netloc):
            return ""
        return "https://" + url.netloc
    except (OSError, ValueError, TypeError, AttributeError):
        return ""


def _connect(directory):
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "ballots.sqlite3", timeout=5)
    db.execute("CREATE TABLE IF NOT EXISTS ballots (entry TEXT, player TEXT, choice INTEGER NOT NULL, PRIMARY KEY(entry,player))")
    return db


def _validate(entry, player):
    if not isinstance(entry, str) or not ID.fullmatch(entry):
        raise ValueError("Invalid atlas entry.")
    if not isinstance(player, str) or (player and not PLAYER.fullmatch(player)):
        raise ValueError("Invalid player ballot.")


def _summary(db, entry, player):
    up, down, mine = db.execute(
        "SELECT COUNT(CASE WHEN choice=1 THEN 1 END), COUNT(CASE WHEN choice=-1 THEN 1 END), "
        "COALESCE(MAX(CASE WHEN player=? THEN choice END),0) FROM ballots WHERE entry=?", (player, entry)
    ).fetchone()
    return {"up": up, "down": down, "mine": mine}


def handle_read(directory, entry, player=""):
    _validate(entry, player)
    with closing(_connect(directory)) as db:
        return _summary(db, entry, player)


def handle_write(directory, payload):
    entry, player, vote = (payload.get(k) for k in ("id", "player", "vote"))
    _validate(entry, player)
    if not player or type(vote) is not int or vote not in (-1, 0, 1):
        raise ValueError("Choose a positive or negative vote, or clear your vote.")
    with closing(_connect(directory)) as db, db:
        if vote == 0:
            db.execute("DELETE FROM ballots WHERE entry=? AND player=?", (entry, player))
        else:
            db.execute("INSERT INTO ballots VALUES(?,?,?) ON CONFLICT(entry,player) DO UPDATE SET choice=excluded.choice", (entry, player, vote))
        return _summary(db, entry, player)

