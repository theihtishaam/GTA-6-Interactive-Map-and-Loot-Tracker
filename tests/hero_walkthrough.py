"""Player walkthrough for character positioning, measured distances and personal bounties."""

import argparse
import base64
from hashlib import sha256
import json
import math
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
from server import Atlas, LocalServer


def data(name):
    return json.loads((ROOT / "public" / name).read_text("utf8"))


def grid(point):
    return point["x"] * 13824 - 10240, 10496 - point["y"] * 19456


def measured(a, b):
    east, north = b[0] - a[0], b[1] - a[1]
    span = math.hypot(east, north)
    if span < 1:
        return "At your position"
    units = f"{span / 1000:.1f} km" if span >= 1000 else f"{math.floor(span + .5)} m"
    directions = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")
    compass = directions[math.floor(math.degrees(math.atan2(east, north)) / 45 + .5) % 8]
    return f"{units} · {compass}"


def assert_fit(page):
    assert page.locator("body").evaluate("el => el.scrollWidth <= window.innerWidth")
    for selector in (".creator-footer", ".creator-footer strong", ".creator-handle", ".creator-footer small",
                     ".creator-footer .github-star", ".creator-footer .github-follow", "#hero-position", "#route-tools", "#style-toggle"):
        box = page.locator(selector).bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= page.viewport_size["width"] + 1, selector
        assert box["y"] + box["height"] <= page.viewport_size["height"] + 1, selector
    expect(page.locator(".creator-footer")).to_contain_text("The Ihtisham")
    expect(page.locator(".creator-handle")).to_have_text("@theihtishaam")
    expect(page.get_by_role("link", name="Follow on GitHub", exact=True)).to_have_attribute("href", "https://github.com/theihtishaam")
    expect(page.get_by_role("link", name="LinkedIn", exact=True)).to_have_attribute("href", "https://www.linkedin.com/in/ihtishamdeveloper/")
    expect(page.locator(".creator-footer small")).to_have_text(re.compile(r"v\d+\.\d+\.\d+"))
    expect(page.locator(".creator-footer .github-star")).to_have_attribute(
        "href", "https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker")


def player(page, base, width, shots, expected_image):
    mobile = width <= 650
    positions = data("guide-positions.json")
    records = {r["id"]: {**r, **positions.get(r["id"], {})}
               for r in data("guides.json") + data("collectible-guides.json")}
    shop = grid(records["guide-game-horde-earbuds"])
    club = grid(records["guide-afternoon-delight"])
    direct = measured(shop, club)
    base_distance = direct.split(" · ")[0]
    page.goto(base)
    expect(page.locator("#pins button").first).to_be_attached()
    assert_fit(page)

    def index():
        if mobile and "index-open" not in page.locator("#world").get_attribute("class").split():
            page.locator("#mobile-index").click()

    def entry(title):
        index()
        page.locator("#search").fill(title)
        page.locator("#results .result").filter(has_text=title).first.click()
        expect(page.locator("#inspector h2")).to_have_text(title)

    def choose_center(*pan):
        surface = page.locator("#map-surface")
        surface.focus()
        for key in pan:
            page.keyboard.press(key)
        page.keyboard.press("Enter")

    page.locator("#hero-position").click()
    expect(page.locator("#instruction")).to_contain_text("your character")
    page.locator("#cancel-place").click()
    entry("Game Horde earbuds")
    page.locator("#set-hero-distance").click()
    choose_center("ArrowUp")
    expect(page.locator("#hero-distance")).to_contain_text("Direct distance")
    expect(page.locator("#hero-distance b")).to_contain_text("south")
    page.locator("#here").click()
    expect(page.locator("#hero-distance b")).to_have_text("At your position")
    page.locator("#complete").click()
    media = page.locator("#evidence-media")
    media.get_by_role("button", name="Load source image").click()
    evidence = media.get_by_role("img")
    expect(evidence).to_have_attribute("src", re.compile(expected_image))
    assert evidence.evaluate("async img => {await img.decode(); return img.naturalWidth > 0}")
    expect(media.get_by_role("link", name="Publisher")).to_have_attribute(
        "href", positions["guide-game-horde-earbuds"]["locationSource"])
    page.locator("#close-item").click()
    entry("Game Horde earbuds")
    expect(page.locator("#evidence-media img")).to_have_attribute("src", re.compile(expected_image))
    page.locator("#close-item").click()
    entry("Afternoon Delight")
    expect(page.locator("#hero-distance b")).to_have_text(direct)
    page.locator("#close-item").click()

    title = "Player test bounty at Delights"
    page.locator("nav [data-view=journal]").click()
    page.locator("#new-pin").click()
    page.locator("#pin-name").fill(title)
    page.locator("#pin-cat").select_option("bounty")
    page.locator("#pin-note").fill("Disposable personal lead for a distance check.")
    page.locator("#pin-form button").click()
    choose_center()
    expect(page.locator("#inspector h2")).to_have_text(title)
    expect(page.locator("#inspector")).to_contain_text("Personal pin")
    expect(page.locator("#hero-distance b")).to_have_text(direct)
    expect(page.locator("#evidence-media")).to_have_count(0)
    card = page.locator("#inspector")
    page.locator("#hero-distance").scroll_into_view_if_needed()
    # Markers must stay under opaque cards, even where an individual button remains clickable.
    assert card.evaluate("""el => {
        const rect = el.getBoundingClientRect();
        for (let y = rect.top + 12; y < rect.bottom - 12; y += 18) {
          for (let x = rect.left + 12; x < rect.right - 12; x += 18) {
            if (document.elementFromPoint(x, y)?.closest('#pins')) return false;
          }
        }
        return true;
    }"""), "Map pins cover the personal-bounty inspector"
    if shots:
        expect(page.locator("#toast")).not_to_be_visible(timeout=8000)
        page.screenshot(path=shots / f"personal-bounty-{width}.png")
    page.locator("#navigate").click()
    expect(page.locator("#route-status")).to_contain_text(title)
    expect(page.locator("#route-status")).to_contain_text(f"{base_distance} direct to stop")
    expect(page.locator("#route-status")).to_contain_text("1 road leg")
    if shots:
        expect(page.locator("#toast")).not_to_be_visible(timeout=8000)
        page.screenshot(path=shots / f"character-route-{width}.png")
    page.locator("#hero-position").click()
    page.locator("#near-hero").click()
    expect(page.locator("#nearest-first")).to_be_checked()
    expect(page.locator("#progress-filter")).to_have_value("remaining")
    ids = page.locator("#results .result").evaluate_all("els => els.map(el => el.dataset.id)")
    assert len(ids) > 1 and "guide-game-horde-earbuds" not in ids
    # The index now contains mission starts in addition to guides and this player's pin.
    # Check the visible distance for every type, then independently verify the guide coordinates.
    ranked = []
    for label in page.locator("#results .result small").all_text_contents():
        match = re.search(r"·\s*([\d,.]+)\s*(km|m)\b", label)
        assert match, label
        ranked.append(float(match[1].replace(",", "")) * (1000 if match[2] == "km" else 1))
    assert ranked == sorted(ranked), ranked
    exact = [math.dist(shop, grid(records[i])) for i in ids if i in records]
    assert all(a <= b + .02 for a, b in zip(exact, exact[1:])), exact
    if mobile:
        page.locator("#mobile-index").click()
    page.locator("#hero-position").click()
    page.locator("#move-hero").click()
    choose_center("ArrowRight")
    expect(page.locator("#route-status")).to_contain_text(title)
    expect(page.locator("#route-status")).not_to_contain_text(f"{base_distance} direct to stop")
    page.locator("#hero-position").click()
    page.locator("#hero-route-options").click()
    page.get_by_text("Enter in-game grid coordinates", exact=True).click()
    # Whole-number grid fields place the player almost exactly 120 m west of the bounty.
    x, y = round(club[0]) - 120, round(club[1])
    page.locator("#grid-x").fill(str(x))
    page.locator("#grid-y").fill(str(y))
    page.locator("#grid-form button").click()
    page.locator("#dialog-close").click()
    revised = measured((x, y), club)
    expect(page.locator("#route-status")).to_contain_text(revised.split(" · ")[0] + " direct to stop")
    entry(title)
    expect(page.locator("#hero-distance b")).to_have_text(revised)
    page.locator("#close-item").click()
    page.locator("#route-tools").click()
    page.locator("#place-stop").click()
    choose_center("ArrowLeft")
    expect(page.locator("#route-status")).to_contain_text(title)
    page.locator("#route-tools").click()
    expect(page.locator("#dialog-body")).to_contain_text("Waypoint 2")
    page.locator("#arrived").click()
    page.locator("#dialog-close").click()
    expect(page.locator("#route-status strong")).to_have_text("Waypoint 2")
    entry(title)
    expect(page.locator("#hero-distance b")).to_have_text("At your position")
    page.locator("#close-item").click()
    page.reload()
    expect(page.locator("#route-status strong")).to_have_text("Waypoint 2")
    assert_fit(page)
    return direct, revised


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--installed-map", action="store_true",
                        help="Use the installed PowerPyx game map in the isolated server")
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    proof = data("guide-positions.json")["guide-game-horde-earbuds"]
    cached = ROOT / ".atlas/activity-screenshots" / proof["sourceImage"].split("/")[-1]
    if cached.is_file():
        image = cached.read_bytes()
        assert sha256(image).hexdigest() == proof["sourceImageSha256"]
        print("Using the cited source screenshot from the local cartography cache.")
    else:
        image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGP8P1WZARtgwio6aCUAW30Bx2v6g0EAAAAASUVORK5CYII=")
        print("Using a synthetic image fixture for the media cache.")
    expected_image = sha256(image).hexdigest()
    with sync_playwright() as driver:
        browser = driver.chromium.launch(channel="chrome", headless=True)
        try:
            for width, height in ((1440, 900), (390, 844), (320, 720)):
                with TemporaryDirectory(prefix="atlas-position-") as temporary:
                    if args.installed_map:
                        game_map = ROOT / ".atlas/powerpyx-map-original.png"
                        shutil.copyfile(game_map, Path(temporary) / game_map.name)
                    app = Atlas(cache=Path(temporary) / "state.json")
                    sources = []
                    def picture(url, **kwargs):
                        assert url == proof["sourceImage"]
                        sources.append(url)
                        return image
                    app.media.fetcher = picture
                    with LocalServer(app, 0) as server:
                        server.atlas.welcome_seen = True  # Returning player.
                        thread = Thread(target=server.serve_forever, daemon=True)
                        thread.start()
                        base = f"http://127.0.0.1:{server.server_port}"
                        context = browser.new_context(viewport={"width":width, "height":height})
                        try:
                            context.route("**/*", lambda route: route.continue_()
                                          if urlsplit(route.request.url).netloc == urlsplit(base).netloc else route.abort())
                            page = context.new_page()
                            errors = []
                            page.on("pageerror", lambda err: errors.append(str(err)))
                            before, after = player(page, base, width, args.screenshots, expected_image)
                            assert sources == [proof["sourceImage"]], "Repeated upstream image lookup"
                            assert not errors, errors
                            print(f"{width}x{height} passed personal and sourced positions ({before} then {after}), ordering, itinerary, image cache and footer.")
                        finally:
                            context.close()
                            server.shutdown()
                            thread.join(timeout=3)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
