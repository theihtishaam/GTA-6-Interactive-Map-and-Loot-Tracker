"""Stop an extracted atlas from Settings, then reopen its journal using the original browser origin."""

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from test_launcher import api, atlas_command, finish, ready, sandbox_copy


def main():
    with TemporaryDirectory(prefix="atlas-launcher-ui-") as parent:
        with sandbox_copy(Path(parent), "Atlas unpacked", full_assets=True) as (project, run):
            process = run(atlas_command("--port", "0"))
            original = ready(project)
            port = original["port"]
            origin = f"http://127.0.0.1:{port}"
            with sync_playwright() as driver:
                browser = driver.chromium.launch(channel="chrome", headless=True)
                try:
                    context = browser.new_context(viewport={"width": 1280, "height": 800})
                    def local_only(route):
                        parsed = urlsplit(route.request.url)
                        if parsed.netloc != urlsplit(origin).netloc:
                            return route.abort()
                        if parsed.path == "/api/provider/models":
                            return route.fulfill(json={"models": [], "selectedAvailable": None,
                                                       "recommended": None, "billing": "metered"})
                        return route.continue_()
                    context.route("**/*", local_only)
                    stale = context.new_page()
                    stale.goto(origin)
                    expect(stale.locator("#pins button").first).to_be_attached()
                    stale.locator("#settings").click()
                    expect(stale.get_by_role("button", name="Stop server")).to_be_visible()
                    page = context.new_page()
                    page.goto(origin)
                    expect(page.locator("#pins button").first).to_be_attached()
                    page.locator("#search").fill("First duffel bag")
                    page.locator('#results [data-id="guide-duffel-bag"]').click()
                    page.locator("#complete").click()
                    expect(page.locator("#complete")).to_contain_text("Completed")
                    page.close()
                    assert api(port, "GET", "/api/launcher")[0] == 200

                    page = context.new_page()
                    page.goto(origin)
                    expect(page.locator("#pins button").first).to_be_attached()
                    page.locator("#settings").click()
                    page.get_by_role("button", name="Stop server").click()
                    expect(page.locator("#dialog-title")).to_have_text("Map server stopped")
                    expect(page.locator("#dialog-body")).to_contain_text("Start Atlas.cmd")
                    finish(process)

                    restarted = run(atlas_command())
                    after = ready(project, previous=original["instance"])
                    assert after["port"] == port
                    stale.get_by_role("button", name="Stop server").click()
                    expect(stale.locator("#server-status")).to_contain_text("restarted")
                    assert api(port, "GET", "/api/launcher")[1]["instance"] == after["instance"]
                    page.goto(origin)
                    expect(page.locator("#pins button").first).to_be_attached()
                    page.locator("#search").fill("First duffel bag")
                    page.locator('#results [data-id="guide-duffel-bag"]').click()
                    expect(page.locator("#complete")).to_contain_text("Completed")
                    page.locator("#settings").click()
                    page.get_by_role("button", name="Stop server").click()
                    expect(page.locator("#dialog-title")).to_have_text("Map server stopped")
                    finish(restarted)
                    print("Tab closure kept the server alive; Settings stopped the right copy. "
                          "Restart retained the origin and completed guide; a stale Settings tab could not stop it.")
                    context.close()
                finally:
                    browser.close()


if __name__ == "__main__":
    main()
