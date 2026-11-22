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


def latest_report_day(today, fetch):
    if today <= LAUNCH:
        return None
    try:
        latest = fetch("last-day")
    except HTTPError as exc:
        if exc.code == 404 and today <= LAUNCH + 2 * DAY:
            return None
        raise
    through = min(date.fromisoformat(latest["end"]), today - DAY)
    return through if through >= LAUNCH else None


def count_period(start, end, fetch):
    row = fetch(f"{start}:{end}")
    if row["start"] != str(start) or row["end"] != str(end):
        raise ValueError(f"Incomplete npm reporting period: {start} through {end}")
    count = row["downloads"]
    if type(count) is not int or count < 0:
        raise ValueError("Invalid npm download count")
    return count


def total_through(through, fetch):
    start = LAUNCH
    total = 0
    while start <= through:
        end = min(through, date(start.year, 12, 31))
        total += count_period(start, end, fetch)
        start = end + DAY
    return total


def lifetime_downloads(today, fetch=point):
    through = latest_report_day(today, fetch)
    return total_through(through, fetch) if through else None


def download_reports(today, fetch=point):
    through = latest_report_day(today, fetch)
    if through is None:
        return None
    total = total_through(through, fetch)
    start = through - 6 * DAY
    weekly = total if start <= LAUNCH else count_period(start, through, fetch)
    if weekly > total:
        raise ValueError("Weekly downloads exceed the lifetime total")
    return through, weekly, total


def svg_badge(through, weekly, total):
    week_label = f"7 days  {weekly:,}"
    total_label = f"since launch  {total:,}"
    week_width = 20 + 8 * len(week_label)
    total_width = 20 + 8 * len(total_label)
    width = 46 + week_width + total_width
    label = f"npm downloads through {through}: {weekly:,} in seven days, {total:,} since launch"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" role="img" aria-label="{label}">
  <title>{label}</title>
  <rect width="{width}" height="28" rx="5" fill="#193632"/>
  <path d="M46 0h{week_width}v28H46z" fill="#315852"/>
  <g font-family="Verdana,Arial,sans-serif" font-size="12" text-anchor="middle" fill="#fff">
    <text x="23" y="18" font-weight="bold">npm</text>
    <text x="{46 + week_width / 2}" y="18">{week_label}</text>
    <text x="{46 + week_width + total_width / 2}" y="18" fill="#bcf6d5">{total_label}</text>
  </g>
</svg>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args()
    reports = download_reports(datetime.now(timezone.utc).date())
    if reports is None and args.output.exists():
        return
    count = reports[2] if reports else None
    badge = {
        "schemaVersion": 1,
        "label": "total npm downloads",
        "message": "awaiting first report" if count is None else f"{count:,}",
        "color": "637489" if count is None else "007d73",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.svg and reports:
        args.svg.parent.mkdir(parents=True, exist_ok=True)
        args.svg.write_text(svg_badge(*reports), encoding="utf-8")
    args.output.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
