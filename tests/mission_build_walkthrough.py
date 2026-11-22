"""Exercise mission builds, player checklists, map starts and backup on desktop and mobile."""
import argparse
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Atlas, LocalServer


def capture(element, destination):
    if destination:
        from PIL import Image
        Image.open(io.BytesIO(element.screenshot())).convert("RGB").save(destination, "WEBP", quality=89, method=5)


def walk(browser, origin, width, workspace, shots):
    context = browser.new_context(viewport={"width": width, "height": 950 if width > 700 else 844})
    context.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).netloc == urlsplit(origin).netloc
                  else route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(origin + "/#missions")
    build = page.locator("#mission-build")
    expect(build.get_by_role("heading", name="Prologue")).to_be_visible()
    assert page.locator("#mission-list button").count() >= 150
    page.locator("#mission-search").fill("Lab Fees")
    page.locator("#mission-list button").first.click()
    expect(build).to_contain_text("Key Lento")
    expect(build).to_contain_text("Gone Fishing")
    page.locator('[data-unlock="mission-gone-fishing"]').click()
    expect(build.get_by_role("heading", name="Gone Fishing", exact=True)).to_be_visible()
    page.locator("#mission-search").fill("Lab Fees")
    page.locator("#mission-list button").first.click()
    objective = build.get_by_role("checkbox").first
    objective.check()
    expect(objective).to_be_checked()
    if shots:
        capture(page.locator(".mission-layout"), shots / "mission-build.webp")
    page.reload()
    expect(build.get_by_role("heading", name="Lab Fees", exact=True)).to_be_visible()
    expect(build.get_by_role("checkbox").first).to_be_checked()
    page.locator("#mission-complete").click()
    expect(page.locator("#mission-complete")).to_contain_text("undo")
    page.locator("#mission-goal").click()
    expect(page.locator("#sheet-content")).to_contain_text("Lab Fees")
    page.locator("nav [data-view=journal]").click()
    with page.expect_download() as item:
        page.locator("#backup").click()
    file = workspace / f"mission-{width}.json"
    item.value.save_as(file)
    backup = json.loads(file.read_text(encoding="utf-8"))
    assert backup["builds"]["mission-lab-fees"] and "mission-lab-fees" in backup["done"]
    assert any(goal.get("entryId") == "mission-lab-fees" for goal in backup["goals"]["goals"])
    page.locator("nav [data-view=missions]").click()
    page.locator("#mission-route").click()
    expect(page.locator("#instruction")).to_contain_text("in-game position")
    page.locator("#map-surface").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#route-status")).to_contain_text("Lab Fees")
    page.locator("nav [data-view=sources]").click()
    expect(page.get_by_text("Public source directory", exact=False)).to_be_visible()
    if shots:
        capture(page.locator("#sheet-content"), shots / "live-sources.webp")
    page.locator("#bounty-tab").click()
    expect(page.locator("#sheet-content")).to_contain_text("No qualifying bounty reports yet")
    if shots:
        capture(page.locator("#sheet-content"), shots / "bounty-watch.webp")
    page.locator("nav [data-view=missions]").click()
    page.locator("#mission-search").fill("No such Leonida mission")
    expect(build).to_contain_text("No matching missions")
    assert page.locator("body").evaluate("e => e.scrollWidth <= innerWidth")
    assert not errors, errors
    context.close()
    fresh = browser.new_context()
    fresh.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).netloc == urlsplit(origin).netloc
                else route.abort())
    page = fresh.new_page()
    page.goto(origin + "/#journal")
    page.locator("#restore-file").set_input_files(file)
    expect(page.locator("#toast")).to_contain_text("merged")
    page.locator("nav [data-view=missions]").click()
    page.locator("#mission-search").fill("Lab Fees")
    expect(page.locator("#mission-complete")).to_contain_text("undo")
    expect(page.locator("[data-step]").first).to_be_checked()
    page.locator("#mission-complete").click()
    expect(page.locator("#mission-complete")).to_contain_text("Mark mission complete")
    fresh.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as workspace, sync_playwright() as driver:
        root = Path(workspace)
        atlas = Atlas(cache=root / "state.json")
        with LocalServer(atlas, 0) as server:
            server.atlas.welcome_seen = True  # Returning player.
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            browser = driver.chromium.launch(channel="chrome", headless=True)
            try:
                for width in [1440, 360]:
                    walk(browser, f"http://127.0.0.1:{server.server_port}", width, root,
                         args.screenshots if width == 1440 else None)
            finally:
                browser.close()
                server.shutdown()
                thread.join()
    print("Mission selection, goals, objective progress, GPS, evidence directory and backup/restore passed on desktop and mobile.")
