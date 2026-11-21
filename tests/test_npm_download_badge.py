from datetime import date
import unittest
from urllib.error import HTTPError

from tools.npm_download_badge import LAUNCH, lifetime_downloads


class LifetimeDownloadsTest(unittest.TestCase):
    def test_launch_day_has_no_completed_reporting_day(self):
        self.assertIsNone(lifetime_downloads(LAUNCH, lambda period: self.fail(period)))

    def test_new_package_waits_for_its_first_report(self):
        def unavailable(period):
            raise HTTPError("https://api.npmjs.org", 404, "Not found", {}, None)

        self.assertIsNone(lifetime_downloads(date(2026, 11, 22), unavailable))
        with self.assertRaises(HTTPError):
            lifetime_downloads(date(2027, 1, 1), unavailable)

    def test_sums_disjoint_periods_through_the_latest_reported_day(self):
        periods = []
        def fetch(period):
            periods.append(period)
            if period == "last-day":
                return {"end": "2028-06-30"}
            start, end = period.split(":")
            return {"start": start, "end": end, "downloads": (date.fromisoformat(end) - date.fromisoformat(start)).days + 1}

        count = lifetime_downloads(date(2028, 7, 2), fetch)
        self.assertEqual(periods, ["last-day", "2026-11-21:2026-12-31", "2027-01-01:2027-12-31", "2028-01-01:2028-06-30"])
        self.assertEqual(count, (date(2028, 7, 1) - LAUNCH).days)

    def test_rejects_truncated_reporting_windows(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            lifetime_downloads(date(2027, 1, 2), lambda _: {"start": "2026-12-01", "end": "2026-12-31", "downloads": 5})
