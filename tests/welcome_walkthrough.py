"""Check the installed player's first visit and optionally capture its desktop and phone previews."""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Atlas, LocalServer


def first_visit(browser, width, height, action, screenshots, live_catalogue):
    with TemporaryDirectory(prefix="atlas-welcome-") as work:
        cache = Path(work) / "state.json"
        atlas = Atlas(cache=cache)
        with LocalServer(atlas, 0) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            context = browser.new_context(viewport={"width": width, "height": height})
            external = []
            def local_only(route):
                url = urlsplit(route.request.url)
                if url.netloc != urlsplit(origin).netloc:
                    external.append(url.hostname)
                    return route.abort()
                if url.path == "/api/provider/models" and not live_catalogue:
                    return route.fulfill(json={"models": ["gpt-oss:120b"], "recommended": "gpt-oss:120b", "billing": "metered"})
                return route.continue_()
            context.route("**/*", local_only)
            try:
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.goto(origin)
                welcome = page.get_by_role("dialog", name="Welcome to Leonida")
                expect(welcome).to_be_visible()
                expect(welcome.get_by_role("button", name="Explore the map")).to_be_focused()
                assert page.locator("#welcome-cover").evaluate("img => img.decode().then(() => img.naturalWidth === 1600)")
                assert page.locator("#map-img").evaluate("img => img.decode().then(() => img.naturalWidth > 0)")
                page.evaluate("document.fonts.ready")
                profile = welcome.get_by_role("link", name="@theihtishaam")
                expect(profile).to_have_attribute("href", "https://github.com/theihtishaam")
                github_links = {
                    "Give a star": "https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker",
                    "Follow on GitHub": "https://github.com/theihtishaam",
                }
                for name, target in github_links.items():
                    button = welcome.get_by_role("link", name=name, exact=True)
                    expect(button).to_have_attribute("href", target)
                    expect(button).to_be_in_viewport(ratio=1)
                    assert button.bounding_box()["height"] >= 54
                    if action == "explore":
                        context.route(target, lambda route: route.fulfill(body="GitHub destination"), times=1)
                        with page.expect_popup() as opened:
                            button.click()
                        opened.value.wait_for_url(target)
                        opened.value.close()
                feedback = page.locator("#creator-feedback").get_attribute("href")
                assert feedback.startswith("https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker/issues/new?")
                expect(welcome.get_by_role("link", name="Give feedback")).to_have_attribute("href", feedback)
                assert welcome.evaluate("el => el.scrollWidth <= el.clientWidth")
                if screenshots and action in ("settings", "close"):
                    label = "desktop" if width > 650 else "mobile"
                    page.screenshot(path=screenshots / f"welcome-{label}.png")
                    if label == "desktop":
                        welcome.screenshot(path=screenshots / "welcome-detail.png")
                if action == "escape":
                    page.keyboard.press("Escape")
                elif action == "settings":
                    welcome.get_by_role("button", name="Set up Ollama").click()
                    expect(page.locator("#provider")).to_have_value("ollama-cloud")
                    expect(page.locator("#enable")).not_to_be_checked()
                    expect(page.locator("#model-hint")).to_contain_text("text model", timeout=18000)
                    if screenshots:
                        page.locator("#dialog").screenshot(path=screenshots / "ollama-settings.png")
                    page.locator("#dialog-close").click()
                elif action == "reload":
                    page.reload()
                else:
                    welcome.get_by_role("button", name="Dismiss welcome" if action == "close" else "Explore the map").click()
                expect(welcome).not_to_be_visible()
                page.reload()
                expect(page.locator("#pins button").first).to_be_attached()
                expect(page.locator("#welcome")).not_to_be_visible()
                assert page.locator("#creator-feedback").is_visible()
                footer = page.get_by_role("contentinfo")
                for name, target in github_links.items():
                    button = footer.get_by_role("link", name=name, exact=True)
                    expect(button).to_have_attribute("href", target)
                    expect(button).to_be_in_viewport(ratio=1)
                    assert button.bounding_box()["height"] >= 44
                if screenshots and action in ("settings", "close"):
                    footer.screenshot(path=screenshots / f"footer-{label}.png")
                assert not atlas.provider.active and not atlas.requested and len(context.pages) == 1
                assert not external and not errors, (external, errors)
            finally:
                context.close()
                server.shutdown()
                worker.join()
        assert not Atlas(cache=cache).state()["welcomePending"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--live-catalogue", action="store_true", help="Read Ollama's public model list without a key.")
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as driver:
        browser = driver.chromium.launch(channel="chrome", headless=True)
        try:
            for width, height, action in [(1280, 800, "settings"), (390, 844, "close"),
                                          (320, 640, "escape"), (850, 600, "explore"), (800, 600, "reload")]:
                first_visit(browser, width, height, action, args.screenshots, args.live_catalogue)
                print(f"{width}x{height} passed first visit, {action}, return visit and restart.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
