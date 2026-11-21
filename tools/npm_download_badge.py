"""Write the lifetime npm download badge from complete, non-overlapping npm reports."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

PACKAGE = "gta6-loot-map"
LAUNCH = date(2026, 11, 21)
DAY = timedelta(days=1)


def point(period):
    with urlopen(f"https://api.npmjs.org/downloads/point/{period}/{PACKAGE}", timeout=30) as response:
        record = json.load(response)
    if record.get("package") != PACKAGE:
        raise ValueError("npm returned a report for a different package")
    return record


def lifetime_downloads(today, fetch=point):
    if today <= LAUNCH:
        return None
    try:
        latest = fetch("last-day")
    except HTTPError as exc:
        if exc.code == 404 and today <= LAUNCH + 2 * DAY:
            return None
        raise
    through = min(date.fromisoformat(latest["end"]), today - DAY)
    if through < LAUNCH:
        return None
    start = LAUNCH
    total = 0
    while start <= through:
        end = min(through, date(start.year, 12, 31))
        row = fetch(f"{start}:{end}")
        if row["start"] != str(start) or row["end"] != str(end):
            raise ValueError(f"Incomplete npm reporting period: {start} through {end}")
        count = row["downloads"]
        if type(count) is not int or count < 0:
            raise ValueError("Invalid npm download count")
        total += count
        start = end + DAY
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count = lifetime_downloads(datetime.now(timezone.utc).date())
    badge = {
        "schemaVersion": 1,
        "label": "total npm downloads",
        "message": "awaiting first report" if count is None else f"{count:,}",
        "color": "637489" if count is None else "007d73",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
