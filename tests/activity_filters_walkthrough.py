"""Exercise the map's family and activity-type filters with a disposable server and browser."""

import argparse
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Atlas, LocalServer


def walk(browser, origin, width, screenshot):
    mobile = width < 650
    context = browser.new_context(viewport={"width": width, "height": 900 if mobile else 1000},
                                  is_mobile=mobile, has_touch=mobile)
    context.route("**/*", lambda route: route.continue_()
                  if urlsplit(route.request.url).netloc == urlsplit(origin).netloc else route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(origin)
    expect(page.locator("#pins button").first).to_be_attached()
    index = page.locator("#mobile-index")

    def open_index():
        if mobile and index.get_attribute("aria-expanded") != "true":
            index.click()

    def rows(expected, missing=0):
        expect(page.locator("#result-count")).to_have_text(str(expected))
        expect(page.locator("#map-summary")).to_have_text(f"{expected - missing} mapped · {missing} awaiting a pin")
        expect(page.locator("#results .result")).to_have_count(expected)

    def family(key):
        return page.locator(f"#categories [data-cat='{key}']")

    def fit():
        if mobile and index.get_attribute("aria-expanded") == "true":
            index.click()
        page.locator("#map-key-toggle").click()
        page.locator("#map-fit-results").click()

    try:
        open_index()
        picker = page.get_by_role("combobox", name="Activity type")
        expect(picker.locator("optgroup[label='Heists']")).to_have_count(1)
        picker.select_option("heist:Bank vaults")
        rows(8)
        expect(page.locator("#map-stage")).to_have_class(re.compile(r"\bfiltered\b"))
        page.locator("#search").fill("downtown")
        rows(2)
        expect(picker.locator("option:checked")).to_have_text("Bank vaults (2)")
        assert all("vault-downtown" in row for row in page.locator("#results .result").evaluate_all("els => els.map(el => el.dataset.id)"))
        page.locator("#search").fill("missing synthetic name")
        rows(0)
        expect(picker.locator("option:checked")).to_have_text("Bank vaults (0)")
        expect(family("heist").locator(".qty")).to_have_text("0")
        expect(page.locator("#pins .pin")).to_have_count(0)
        expect(page.locator("#results")).to_contain_text("Try another")

        page.locator("#reset-filters").click()
        family("heist").click()
        picker.select_option("heist:Payday loans")
        rows(7)
        family("collectible").click()
        expect(picker).to_have_value("")
        picker.select_option("collectible:Meditations")
        rows(10)
        expect(picker.locator("option:checked")).to_have_text("Meditations (10)")
        family("mission").click()
        picker.select_option("mission:Strangers & Freaks")
        expect(picker.locator("option:checked")).to_contain_text("29")
        expect(page.locator("#result-count")).to_have_text("29")

        family("leisure").click()
        expect(family("leisure")).to_have_attribute("aria-pressed", "true")
        expect(family("leisure").locator(".qty")).to_have_text("8")
        for name, expected in (("Golf",1), ("Fitness",3), ("Arcade",1), ("Pool",3)):
            picker.select_option("leisure:" + name)
            rows(expected)
        pool_ids = set(page.locator("#results .result").evaluate_all("els => els.map(el => el.dataset.id)"))
        fit()
        expect(page.locator("#pins .pin")).to_have_count(3)
        assert set(page.locator("#pins .pin").evaluate_all("els => els.map(el => el.dataset.entry)")) == pool_ids
        assert page.locator("#pins .pin").first.evaluate(
            "el => getComputedStyle(el.querySelector('.pin-glyph'),'::before').boxShadow !== 'none'")
        open_index()
        page.locator("#results [data-id='guide-pool-delights']").click()
        expect(page.locator("#inspector")).to_contain_text("Pool · Delights Cabaret")
        expect(page.locator("#pins [aria-current=true]")).to_have_attribute("data-entry", "guide-pool-delights")
        if not mobile and screenshot:
            fit()
            expect(page.locator("#pins .pin")).to_have_count(3)
            expect(page.locator("#inspector")).to_contain_text("Pool · Delights Cabaret")
            page.mouse.move(10, 10)
            page.screenshot(path=screenshot, animations="disabled")

        page.locator("#complete").click()
        open_index()
        page.locator("#progress-filter").select_option("remaining")
        rows(2)
        expect(page.locator("#inspector")).to_be_hidden()
        expect(page.locator("#pins .selected")).to_have_count(0)
        expect(family("leisure").locator(".qty")).to_have_text("7")
        page.locator("#progress-filter").select_option("done")
        rows(1)
        expect(picker.locator("option:checked")).to_have_text("Pool (1)")
        page.locator(".extra-filters summary").click()
        page.locator("#region-filter").select_option("Key Lento")
        rows(0)
        page.locator("#region-filter").select_option("")
        rows(1)
        page.locator("#reset-filters").click()
        expect(picker).to_have_value("")
        expect(page.locator("#progress-filter")).to_have_value("all")
        expect(family("all")).to_have_attribute("aria-pressed", "true")
        expect(page.locator("#search")).to_have_value("")
        expect(page.locator("#map-stage")).not_to_have_class(re.compile(r"\bfiltered\b"))
        page.locator("#search").fill("bank vaults")
        expect(family("heist").locator(".qty")).to_contain_text("8")
        assert page.locator("body").evaluate("el => el.scrollWidth <= innerWidth")
        assert not errors, errors
        print(f"{width}px passed grouped filters, search, counts, isolated map pins, region, journal and reset")
    finally:
        context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="atlas-activity-filters-") as temp, sync_playwright() as driver:
        app = Atlas(cache=Path(temp) / "state.json")
        app.welcome_seen = True
        with LocalServer(app, 0) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            browser = driver.chromium.launch(channel="chrome", headless=True)
            try:
                for size in (1440, 360):
                    walk(browser, f"http://127.0.0.1:{server.server_port}", size, args.screenshot)
            finally:
                browser.close()
                server.shutdown()
                thread.join()
