"""Check Goals using a local application server and synthetic, scheduled evidence updates.

Run with Playwright installed and Google Chrome available:
    python tests/goals_player_walkthrough.py
"""

import argparse
from datetime import timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from discovery import Source, make_report  # noqa: E402
from server import Atlas, LocalServer, utcnow  # noqa: E402

MISSION = "First duffel bag"
REPORT = "GTA VI Copper Heron collectible found at Jason's House"
REPORT_URL = "https://goals-fixture.example/copper-heron"
SOURCE = Source("goals-fixture", "Offline evidence fixture", "https://goals-fixture.example/")


def synthetic_snapshot(phase, landmarks):
    text = ("The Copper Heron collectible was found at Jason's House. Pick it up on the counter."
            if not phase["review"] else
            "I retract my report. I posted the wrong pin for the Copper Heron collectible.")
    entry = make_report(SOURCE, (REPORT, text, REPORT_URL, utcnow().isoformat(), None), landmarks)
    assert entry is not None
    health = {**SOURCE.health(), "status": "ok", "seen": 1, "matched": 1}
    return [health], [entry]


def scheduled_refresh(app, page, status):
    # Advance the isolated scheduler and browser poll rather than clicking Refresh.
    with app.change:
        app.next_run = utcnow() - timedelta(seconds=1)
        app.change.notify_all()
    deadline = monotonic() + 8
    while monotonic() < deadline:
        rows = app.state()["reports"]
        if rows and rows[0]["verification"]["status"] == status and not app.running:
            page.clock.fast_forward(62_000)
            return rows[0]
        sleep(.03)
    raise AssertionError(f"Expected scheduled report status {status}.")


def go(page, name):
    page.locator(f'nav [data-view="{name}"]').click()


def inspect(page, title):
    page.get_by_role("searchbox", name="Search places and activities").fill(title)
    page.locator("#results").get_by_role("button").filter(has_text=title).first.click()
    inspector = page.locator("#inspector")
    expect(inspector).to_be_visible()
    expect(inspector.get_by_role("heading", name=title)).to_be_visible()
    return inspector


def goal(page, heading):
    return page.locator(".goal-card").filter(has=page.get_by_role("heading", name=heading, exact=True))


def new_context(browser, base, external):
    context = browser.new_context(viewport={"width": 1440, "height": 940}, accept_downloads=True)
    def steer(route):
        destination = urlsplit(route.request.url)
        if destination.netloc == urlsplit(base).netloc:
            return route.continue_()
        external.append((route.request.method, route.request.url))
        if destination.hostname == "github.com" and destination.path.endswith("/issues/new"):
            return route.fulfill(body="Offline GitHub issue editor fixture", content_type="text/plain")
        return route.abort()
    context.route("**/*", steer)
    return context


def use_goals(page, save_to, screenshot):
    expect(page.locator("#pins button").first).to_be_attached()
    inspect(page, "Game Horde earbuds")
    page.locator("#here").click()
    page.locator("#close-item").click()
    inspect(page, MISSION)
    page.locator("#track-goal").click()
    target = goal(page, MISSION)
    expect(target).to_contain_text("0 / 1")
    expect(target).to_contain_text("mission start or contact")
    expect(target).to_contain_text("Lab Fees")
    if screenshot:
        target.get_by_text("How to complete", exact=True).click()
        page.clock.fast_forward(4500)
        target.screenshot(path=screenshot)
    target.get_by_role("button", name="Map details").click()
    expect(page.locator("#inspector")).to_contain_text(MISSION)
    go(page, "goals")
    target.get_by_role("button", name="Route here").click()
    expect(page.locator("#route-overlay .stop-dot")).to_have_count(1)
    expect(page.locator("#route-overlay polyline").first).to_be_attached()
    page.locator("#route-tools").click()
    expect(page.locator("#dialog-body")).to_contain_text(MISSION)
    page.locator("#dialog-close").click()
    go(page, "goals")
    target.get_by_role("button", name="Mark complete").click()
    expect(target).to_contain_text("1 / 1")
    page.reload()
    expect(target).to_contain_text("1 / 1")
    target.get_by_text("Completed entries · 1", exact=True).click()
    target.get_by_role("button", name="Undo completion of " + MISSION).click()
    expect(target).to_contain_text("0 / 1")

    form = page.locator("form[data-goal-form]")
    form.locator("select[name=type]").select_option("count")
    form.locator("select[name=category]").select_option("bounty")
    form.locator("input[name=target]").fill("3")
    form.get_by_role("button", name="Create goal").click()
    bounty = goal(page, "Complete 3 · Bounties")
    expect(bounty).to_contain_text("0 / 3")
    expect(bounty).to_contain_text("no more eligible sourced activities")
    expect(bounty.get_by_role("button", name="Route here")).to_have_count(0)
    bounty.get_by_role("button", name="Open Bounty Watch").click()
    expect(page.locator("#sheet-content")).to_contain_text("Bounty Watch")
    go(page, "goals")
    target.get_by_role("button", name="Mark complete").click()

    go(page, "journal")
    with page.expect_download() as download:
        page.locator("#backup").click()
    download.value.save_as(save_to)


def review_evidence(app, page, phase, external):
    go(page, "map")
    entry = scheduled_refresh(app, page, "single-source")
    assert entry["x"] is not None and entry["y"] is not None
    inspector = inspect(page, REPORT)
    expect(inspector.locator("[data-status=single-source]")).to_be_visible()
    expect(page.locator("#pins .selected")).to_contain_text(REPORT)
    page.locator("#track-goal").click()
    target = goal(page, REPORT)
    expect(target.get_by_role("button", name="Route here")).to_be_visible()
    target.get_by_role("button", name="Route here").click()
    expect(page.locator("#route-overlay .stop-dot")).to_have_count(1)
    expect(page.locator("#route-overlay polyline").first).to_be_attached()

    inspect(page, REPORT)
    page.locator("#draft-report").click()
    expect(page.locator("#report-preview a")).to_have_count(0)
    assert len(page.context.pages) == 1 and not external
    page.locator("#report-observation").fill("Observed in the offline walkthrough.")
    page.locator("#prepare-report").click()
    link = page.get_by_role("link", name="Review draft on GitHub")
    expect(link).to_be_visible()
    assert len(page.context.pages) == 1 and not external
    with page.context.expect_page() as opened:
        link.click()
    popup = opened.value
    popup.wait_for_load_state()
    parsed = urlsplit(popup.url)
    assert parsed.hostname == "github.com" and parsed.path.endswith("/issues/new")
    assert "Observed in the offline walkthrough." in parse_qs(parsed.query)["body"][0]
    assert [method for method, _ in external] == ["GET"]
    popup.close()
    page.locator("#dialog-close").click()

    phase["review"] = True
    newer = scheduled_refresh(app, page, "review")
    assert newer["x"] is None and newer["y"] is None
    expect(inspector.locator("[data-status=review]")).to_be_visible()
    expect(page.locator("#pins [data-entry='" + entry["id"] + "']")).to_have_count(0)
    expect(page.locator("#navigate")).to_have_count(0)
    expect(page.locator("#route-overlay .stop-dot")).to_have_count(0)
    expect(page.locator("#route-overlay polyline")).to_have_count(0)
    go(page, "goals")
    expect(target).to_contain_text("under review")
    expect(target.get_by_role("button", name="Route here")).to_have_count(0)


def restored(page, save_to):
    expect(page.locator("#pins button").first).to_be_attached()
    go(page, "goals")
    expect(goal(page, MISSION)).to_have_count(0)
    go(page, "journal")
    page.locator("#restore-file").set_input_files(save_to)
    expect(page.locator("#toast")).to_contain_text("restored")
    go(page, "goals")
    expect(goal(page, MISSION)).to_contain_text("1 / 1")
    expect(goal(page, "Complete 3 · Bounties")).to_contain_text("0 / 3")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--screenshot", type=Path, help="Optional PNG screenshot of the genuine mission goal.")
    args = cli.parse_args()
    phase = {"review": False}
    with TemporaryDirectory(prefix="atlas-goals-") as work, sync_playwright() as driver:
        app = Atlas(cache=Path(work) / "state.json", discovery=lambda rows: synthetic_snapshot(phase, rows))
        app.next_run = utcnow() + timedelta(days=1)
        with LocalServer(app, 0) as server:
            server.atlas.welcome_seen = True  # Returning player.
            threads = [Thread(target=server.serve_forever, daemon=True), Thread(target=app.worker, daemon=True)]
            for thread in threads:
                thread.start()
            browser = driver.chromium.launch(channel="chrome", headless=True)
            base = f"http://127.0.0.1:{server.server_port}"
            external = []
            try:
                context = new_context(browser, base, external)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.clock.install()
                page.goto(base)
                saved = Path(work) / "goals-journal.json"
                use_goals(page, saved, args.screenshot)
                review_evidence(app, page, phase, external)
                assert not errors, errors
                context.close()
                isolated = new_context(browser, base, [])
                reopened = isolated.new_page()
                reopened.goto(base)
                restored(reopened, saved)
                isolated.close()
            finally:
                browser.close()
                app.stop()
                server.shutdown()
                for thread in threads:
                    thread.join(timeout=3)
    print("Passed guide and route, goal persistence and undo, zero bounties, scheduled discovery/review, author-click draft, and fresh-context journal restore.")


if __name__ == "__main__":
    main()
