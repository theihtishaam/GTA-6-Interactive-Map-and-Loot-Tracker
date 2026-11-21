"""Optional browser-level checks for atlas markers, legend and map groups."""
import argparse
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import MAP_ASSETS, Atlas, LocalServer  # noqa: E402


def check_map(page, origin, touch, screenshots):
    page.goto(origin)
    map_surface = page.locator("#map-surface")
    expect(page.locator("#pins .pin").first).to_be_attached()
    assert page.locator("#map-img").evaluate("async img => { await img.decode(); return img.naturalWidth > 0 }")

    legend_button = page.get_by_role("button", name="Map legend", exact=True)
    legend = page.locator("#map-key-panel")
    legend_button.click()
    expect(legend).to_be_visible()
    expect(legend.get_by_text("Completed")).to_be_visible()
    large = legend.get_by_role("checkbox", name="Larger markers")
    sample = page.locator("#pins .pin").first
    small_width = sample.evaluate("el => el.offsetWidth")
    large.check()
    expect(page.locator("#map-stage")).to_have_class(re.compile(r"\blarge-markers\b"))
    assert sample.evaluate("el => el.offsetWidth") > small_width
    if touch:
        assert sample.evaluate("el => el.offsetWidth") >= 44
    else:
        assert sample.locator(".pin-glyph").evaluate(
            "el => getComputedStyle(el, '::before').transitionDuration") == "0s"
    if screenshots:
        page.screenshot(path=screenshots / ("touch-key.png" if touch else "desktop-key.png"))
    legend.get_by_role("button", name="Fit filtered results").click()
    expect(legend).to_be_hidden()
    page.get_by_role("button", name="Fit map", exact=True).click()
    expect(page.locator("#zoom-level")).to_have_text("1×")

    group = page.locator("#pins .pin.cluster:not(.place)").first
    if touch:
        group.tap()
    else:
        group.hover()
        expect(group.locator(".pin-label")).to_be_visible()
        group.click()
    preview = page.locator("#map-group-preview")
    expect(preview).to_be_visible()
    expect(group).to_have_attribute("aria-expanded", "true")
    if screenshots:
        page.screenshot(path=screenshots / ("touch-group.png" if touch else "desktop-group.png"))
    preview.get_by_role("button", name="Browse entries").click()
    expect(page.get_by_role("heading", name="Nearby map entries")).to_be_visible()
    page.locator("#dialog-close").click()

    page.get_by_role("button", name="Fit map", exact=True).click()
    before = page.locator("#zoom-level").text_content()
    page.locator("#pins .pin.cluster:not(.place)").first.click()
    preview.get_by_role("button", name="Zoom in").click()
    expect(preview).to_be_hidden()
    expect(page.locator("#zoom-level")).not_to_have_text(before)
    if touch:
        cdp = page.context.new_cdp_session(page)
        box = map_surface.bounding_box()
        x, y = box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.53
        zoom_after_group = page.locator("#zoom-level").text_content()
        def pinch_points(offset):
            return [{"x": x - offset, "y": y, "id": 1}, {"x": x + offset, "y": y, "id": 2}]
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pinch_points(32)})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pinch_points(58)})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        expect(page.locator("#zoom-level")).not_to_have_text(zoom_after_group)
        expect(preview).to_be_hidden()
    else:
        page.get_by_role("button", name="Fit map", exact=True).click()
        map_surface.focus()
        page.keyboard.press("Enter")
        assert page.evaluate("document.activeElement.matches('#pins .pin')")
        assert page.evaluate("getComputedStyle(document.activeElement.querySelector('.pin-label')).display") == "block"
        prior = page.evaluate("document.activeElement.dataset.entry")
        page.keyboard.press("ArrowUp")
        assert page.evaluate("document.activeElement.dataset.entry") != prior
        page.keyboard.press("Escape")
        expect(map_surface).to_be_focused()

    if touch:
        page.locator("#mobile-index").tap()
    page.get_by_role("searchbox", name="Search places and activities").fill("First duffel bag")
    page.locator("#results button").first.click()
    selected = page.locator("#pins .pin.selected")
    expect(selected).to_have_attribute("data-kind", "bag")
    expect(selected.locator(".pin-label")).to_be_visible()
    page.locator("#complete").click()
    expect(selected.locator(".pin-done")).to_be_visible()
    expect(selected).to_have_attribute("aria-label", re.compile("selected, completed$"))
    if screenshots:
        page.screenshot(path=screenshots / ("touch-selected.png" if touch else "desktop-selected.png"))
    assert page.locator("body").evaluate("el => el.scrollWidth === document.documentElement.clientWidth")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--game-layer", action="store_true")
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="atlas-map-input-") as tmp, sync_playwright() as driver:
        if args.game_layer:
            name = MAP_ASSETS["/game-map.png"]
            shutil.copyfile(ROOT / ".atlas" / name, Path(tmp) / name)
        with LocalServer(Atlas(cache=Path(tmp) / "state.json"), 0) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            try:
                browser = driver.chromium.launch(channel="chrome", headless=True)
                for touch, size in ((False, (1440, 900)), (True, (390, 844))):
                    context = browser.new_context(
                        viewport=dict(zip(("width", "height"), size)),
                        has_touch=touch, is_mobile=touch, reduced_motion="reduce",
                    )
                    context.route("**/*", lambda route: route.continue_()
                                  if urlsplit(route.request.url).netloc == urlsplit(origin).netloc else route.abort())
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    try:
                        check_map(page, origin, touch, args.screenshots)
                    except Exception:
                        if errors:
                            print("Browser errors:", errors)
                        raise
                    assert not errors, errors
                    context.close()
                    print(f"{size[0]} × {size[1]} map interactions passed.")
                browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)


if __name__ == "__main__":
    main()
