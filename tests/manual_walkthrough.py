"""Run the player field manual in two fresh, loopback-only browser sessions."""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Atlas, LocalServer  # noqa: E402


def test_manual(page, base, width, shots):
    page.goto(base)
    expect(page.locator("#pins button").first).to_be_attached()
    manual_nav = page.locator("nav [data-view=manual]")
    manual_nav.click()
    manual = page.locator(".fm")
    expect(manual.get_by_role("heading", name="Player field manual")).to_be_visible()
    expect(manual.locator(".fm-map svg")).to_be_visible()

    def chapter(index):
        if width < 741:
            manual.get_by_label("Choose a chapter").select_option(str(index))
        else:
            manual.locator(f"button[data-fm-chapter='{index}']").click()
        expect(manual.locator(".fm-chapter-count")).to_have_text(f"Chapter {index+1} of 7")
        assert manual.evaluate("el => el.scrollWidth <= el.clientWidth")

    if shots:
        shots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=shots / f"manual-{width}.png")
    next_chapter = manual.locator("[data-fm-turn='1']")
    next_chapter.focus()
    page.keyboard.press("Enter")
    expect(manual.locator("#fm-title")).to_be_focused()
    expect(manual.locator(".fm-chapter-count")).to_have_text("Chapter 2 of 7")
    manual.locator("[data-fm-turn='-1']").click()
    guides = {r["id"]: r for r in json.loads((ROOT/"public/guides.json").read_text("utf8"))}
    guides.update({r["id"]:r for r in json.loads((ROOT/"public/collectible-guides.json").read_text("utf8"))})
    destinations = {}
    for index in range(7):
        chapter(index)
        if index == 2:
            spoiler = manual.locator(".fm-spoiler")
            expect(spoiler.get_by_role("button")).not_to_be_visible()
            spoiler.locator("summary").click()
            expect(spoiler).to_contain_text("GTA$10,000")
        for target in manual.locator(".fm-page [data-fm-action=openEntry]").all():
            guide_id = target.get_attribute("data-fm-value")
            assert guide_id in guides
            destinations[guide_id] = index
        for source in manual.locator(".fm-citation a").all():
            assert urlsplit(source.get_attribute("href")).scheme == "https"
    assert len(destinations) >= 6
    for guide_id, index in destinations.items():
        chapter(index)
        target = manual.locator(f".fm-page [data-fm-value='{guide_id}']")
        if not target.is_visible():
            manual.locator(".fm-spoiler summary").click()
        target.click()
        expect(page.locator("#inspector h2")).to_have_text(guides[guide_id]["title"])
        manual_nav.click()

    chapter(3)
    manual.locator("[data-fm-action=openRoutes]").click()
    expect(page.locator("#dialog")).to_be_visible()
    expect(page.locator("#dialog")).to_contain_text("Route planner")
    page.locator("#dialog-close").click()
    manual_nav.click()
    chapter(4)
    manual.locator("[data-fm-action=openBountyWatch]").click()
    expect(page).to_have_url(base + "/#bounties")
    manual_nav.click()
    chapter(4)
    for category in ("bounty", "gloves"):
        target = manual.locator(f"[data-fm-value='{category}']")
        if target.count():
            target.click()
            expect(page.locator("#results")).to_contain_text("No sourced")
            manual_nav.click()
            chapter(4)
    manual.locator("[data-fm-action=openSources]").click()
    expect(page.locator("nav [data-view=sources]")).to_have_attribute("aria-current", "page")
    manual_nav.click()
    chapter(5)
    manual.locator("[data-fm-action=openJournal]").click()
    expect(page.locator("nav [data-view=journal]")).to_have_attribute("aria-current", "page")
    manual_nav.click()
    chapter(5)
    manual.get_by_role("button", name="Bag mission").click()
    page.locator("#complete").click()
    page.locator("#share-field-card").click()
    expect(page.locator("#export-scope")).to_have_value("entry")
    expect(page.locator("#export-route")).not_to_be_checked()
    with page.expect_download() as card:
        page.locator("#export-download").click()
    with open(card.value.path(), encoding="utf8") as downloaded:
        single = downloaded.read()
    assert 'class="card"' in single and "GTA 6 field card" in single and "265 167" in single
    assert card.value.suggested_filename == "gta6-location-card.html"
    page.locator("#dialog-close").click()
    manual_nav.click()
    chapter(5)
    manual.locator("[data-fm-action=openExport]").click()
    expect(page.locator("#dialog")).to_be_visible()
    expect(page.locator("#dialog")).to_contain_text("Export")
    page.locator("#export-scope").select_option("done")
    expect(page.locator("#export-preview")).to_contain_text("1 mapped")
    with page.expect_download() as pack_download:
        page.locator("#export-download").click()
    with open(pack_download.value.path(), encoding="utf8") as pack:
        html = pack.read()
    assert "First duffel bag" in html and "data:image/webp;base64," in html
    assert "mission start or contact" in html and "gta-6-lab-fees-collect-brians-rent-walkthrough" in html
    assert html.count("<article>") == 1
    page.locator("#dialog-close").click()
    manual_nav.click()
    chapter(6)
    manual.locator("[data-fm-action=openMap]").click()
    expect(page.locator("nav [data-view=map]")).to_have_attribute("aria-current", "page")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="atlas-manual-") as temporary:
        with LocalServer(Atlas(cache=Path(temporary)/"state.json"), 0) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with sync_playwright() as driver:
                    browser = driver.chromium.launch(channel="chrome", headless=True)
                    try:
                        for width, height in [(1440, 900), (390, 844)]:
                            context = browser.new_context(viewport={"width": width, "height": height})
                            context.route("**/*", lambda route: route.continue_()
                                          if urlsplit(route.request.url).netloc == urlsplit(base).netloc
                                          else route.abort())
                            page = context.new_page()
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            test_manual(page, base, width, args.screenshots)
                            assert not errors, errors
                            context.close()
                            print(f"{width}x{height} passed all chapters, guide links and atlas actions.")
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)


if __name__ == "__main__":
    main()
