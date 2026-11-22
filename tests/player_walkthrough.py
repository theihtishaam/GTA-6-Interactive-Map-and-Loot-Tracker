"""Optional player walkthrough using an isolated server and a fresh Chromium context.

Run with an installed Playwright Python package and Google Chrome:
    python tests/player_walkthrough.py
"""

import argparse
import csv
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import MAP_ASSETS, Atlas, LocalServer  # noqa: E402


def find_entry(page, title, mobile):
    if mobile:
        page.locator("#mobile-index").click()
    query = page.get_by_role("searchbox", name="Search places and activities")
    query.fill(title)
    result = page.locator("#results").get_by_role("button").filter(has_text=title).first
    result.click()
    inspector = page.locator("#inspector")
    expect(inspector).to_be_visible()
    expect(inspector).to_contain_text(title)
    return inspector


def play(page, origin, mobile, files, screenshots=None, reference_layers=False):
    page.goto(origin)
    expect(page.locator("#pins button").first).to_be_attached()
    assert page.locator("#map-img").evaluate("async img => { await img.decode(); return img.naturalWidth > 0 }")
    if screenshots:
        page.screenshot(path=screenshots / "map.png")
    inspector = find_entry(page, "Game Horde earbuds", mobile)
    expect(inspector).to_contain_text("Port Gellhorn")
    expect(inspector).to_contain_text("in-game map marker")
    expect(inspector).to_contain_text("GamesRadar+")
    expect(inspector.get_by_role("link", name="Supporting guide")).to_have_attribute(
        "href", "https://www.powerpyx.com/gta-6-all-electronics-stores-locations/")
    if screenshots:
        page.screenshot(path=screenshots / "venue.png")
    page.locator("#upvote").click()
    expect(page.locator("#vote-box")).to_contain_text("100% positive")
    page.locator("#downvote").click()
    expect(page.locator("#vote-box")).to_contain_text("0% positive · 1 vote")
    page.locator("#downvote").click()
    expect(page.locator("#vote-box")).to_contain_text("No votes yet")
    page.locator("#here").click()
    page.locator("#complete").click()
    expect(inspector).to_contain_text("Completed · undo")
    page.locator("#close-item").click()

    find_entry(page, "Afternoon Delight", mobile)
    page.locator("#navigate").click()
    expect(page.locator("#route-status")).to_contain_text("1 road leg")
    expect(page.locator("#route-overlay polyline.road-line")).to_have_count(1)
    page.locator("#route-tools").click()
    expect(page.locator("#dialog-body")).to_contain_text("GPS directions")
    page.locator("#dialog-close").click()
    if reference_layers:
        for layer, asset in {"poster": "/official-map.jpg", "day": "/day-map.webp",
                             "community": "/map.webp", "game": "/game-map.png"}.items():
            page.locator("#style-toggle").click()
            page.locator(f"[data-layer={layer}]").click()
            page.locator("#dialog-close").click()
            expect(page.locator("#map-img")).to_have_attribute("src", asset)
            assert page.locator("#map-img").evaluate("async img => { await img.decode(); return img.naturalWidth > 0 }")
            expect(page.locator("#route-overlay polyline.road-line")).to_have_count(1)
        page.locator("#style-toggle").click()
        page.locator("[data-style=night]").click()
        expect(page.locator("#map-stage")).to_have_attribute("data-style", "night")

    find_entry(page, "Ascent Mountain meditation", mobile)
    page.locator("#navigate").click()
    expect(page.locator("#route-status")).to_contain_text("1 direct bearing")
    expect(page.locator("#route-overlay polyline.road-line")).to_have_count(0)

    find_entry(page, "First duffel bag", mobile)
    expect(inspector).to_contain_text("Lab Fees")
    expect(inspector).to_contain_text("mission start or contact")
    inspector.get_by_text("Position evidence", exact=True).click()
    expect(inspector.get_by_text("The selected Collect Brian", exact=False)).to_be_visible()
    page.locator("#navigate").click()
    expect(page.locator("#route-status")).to_contain_text("1 road leg")
    if mobile:
        page.locator("#mobile-index").click()
    page.locator("#search").fill("anything-but-a-real-guide")
    expect(page.locator("#results")).to_contain_text("Try another")
    page.locator("#search").fill("")
    page.locator("#categories [data-cat=bounty]").click()
    expect(page.locator("#results")).to_contain_text("No sourced bounties")
    if mobile:
        page.locator("#mobile-index").click()

    page.locator("nav [data-view=journal]").click()
    page.locator("[data-tab=done]").click()
    expect(page.locator("#sheet-content .entryrow")).to_have_count(1)
    expect(page.locator("#sheet-content .entryrow")).to_contain_text("Game Horde earbuds")
    with page.expect_download() as backup:
        page.locator("#backup").click()
    saved = files / "player-backup.json"
    backup.value.save_as(saved)
    assert json.loads(saved.read_text("utf8"))["done"] == ["guide-game-horde-earbuds"]
    page.locator("[data-done=guide-game-horde-earbuds]").click()
    expect(page.locator("#sheet-content .entryrow")).to_have_count(0)
    page.locator("#restore-file").set_input_files(saved)
    expect(page.locator("#sheet-content .entryrow")).to_contain_text("Game Horde earbuds")

    page.locator("nav [data-view=map]").click()
    if mobile:
        page.locator("#mobile-index").click()
    page.locator("#reset-filters").click()
    page.locator("#progress-filter").select_option("done")
    expect(page.locator("#results .result")).to_have_count(1)
    page.locator("nav [data-view=journal]").click()
    with page.expect_download() as download:
        page.locator("#csv").click()
    target = files / "player.csv"
    download.value.save_as(target)
    rows = list(csv.DictReader(io.StringIO(target.read_text("utf-8-sig"))))
    assert [(r["ID"], r["Status"]) for r in rows] == [("guide-game-horde-earbuds", "completed")]
    page.reload()
    page.locator("nav [data-view=journal]").click()
    page.locator("[data-tab=done]").click()
    expect(page.locator("#sheet-content .entryrow")).to_contain_text("Game Horde earbuds")

    page.locator("#new-pin").click()
    page.locator("#pin-name").fill("Player’s own bounty lead")
    page.locator("#pin-cat").select_option("bounty")
    page.locator("#pin-note").fill("Personal test observation.")
    page.locator("#pin-form button").click()
    page.locator("#map-surface").focus()
    page.keyboard.press("Enter")
    expect(inspector).to_contain_text("Player’s own bounty lead")
    expect(inspector).to_contain_text("Personal pin")
    page.locator("#close-item").click()

    page.locator("#settings").click()
    expect(page.locator("#enable")).not_to_be_checked()
    expect(page.locator("#provider")).to_have_value("ollama-cloud")
    page.locator("#interval").select_option("6")
    page.locator("#save-interval").click()
    page.locator("#dialog-close").click()
    page.locator("nav [data-view=sources]").click()
    expect(page.locator("#sheet-content")).to_contain_text("6h")
    assert page.locator("body").evaluate("body => body.scrollWidth <= window.innerWidth")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="chrome")
    parser.add_argument("--screenshots", type=Path, help="Optional output directory")
    parser.add_argument("--installed-layers", action="store_true",
                        help="Also exercise the three optional locally installed reference maps")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="loot-atlas-player-") as temporary, sync_playwright() as driver:
        if args.installed_layers:
            for asset in ("/official-map.jpg", "/game-map.png", "/day-map.webp"):
                filename = MAP_ASSETS[asset]
                shutil.copyfile(ROOT / ".atlas" / filename, Path(temporary) / filename)
        app = Atlas(cache=Path(temporary) / "state.json")
        with LocalServer(app, 0) as server:
            server.atlas.welcome_seen = True  # Returning player.
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            try:
                browser = driver.chromium.launch(channel=args.channel, headless=True)
                try:
                    for mobile, size in ((False, (1440, 900)), (True, (390, 844))):
                        context = browser.new_context(viewport=dict(zip(("width", "height"), size)))
                        errors = []
                        context.route("**/*", lambda route: route.continue_()
                                      if urlsplit(route.request.url).netloc == urlsplit(origin).netloc else route.abort())
                        page = context.new_page()
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        shots = args.screenshots / str(size[0]) if args.screenshots else None
                        if shots:
                            shots.mkdir(parents=True, exist_ok=True)
                        play(page, origin, mobile, Path(temporary), shots, args.installed_layers)
                        print(f"{size[0]} × {size[1]} passed search, votes, checklist, routes, backup, import, CSV and schedule.")
                        assert not errors, str(errors)
                        context.close()
                finally:
                    browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)


if __name__ == "__main__":
    main()
