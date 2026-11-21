"""Exercise Settings in disposable browser sessions with a synthetic provider catalogue."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from providers import list_models
from server import Atlas, LocalServer


def browser_check(browser, width, height):
    catalog = {"mode": "online"}
    calls = []

    def fixture(config):
        calls.append(config.kind)
        if catalog["mode"] == "offline":
            raise RuntimeError("Fixture catalogue unavailable.")
        if config.kind == "openrouter":
            rows = [{"id": "openrouter/free"}, {"id": "compact:free"}, {"id": "metered/large"}]
        elif config.kind == "ollama-local":
            return list_models(config, lambda *_, **__: b'{"models":[{"name":"installed:3b"}]}')
        else:
            rows = [{"id": "gpt-oss:20b"}, {"id": "gemma4:31b"}]
            if catalog["mode"] == "retired":
                rows.pop(0)
        return list_models(config, lambda *_, **__: json.dumps({"data": rows}).encode())

    with TemporaryDirectory(prefix="atlas-provider-test-") as folder, patch("server.list_models", fixture):
        app = Atlas(cache=Path(folder)/"state.json")
        with LocalServer(app, 0) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            context = browser.new_context(viewport={"width": width, "height": height})
            try:
                context.route("**/*", lambda route: route.continue_()
                              if urlsplit(route.request.url).netloc == urlsplit(base).netloc else route.abort())
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.goto(base)
                expect(page.locator("#pins button").first).to_be_attached()
                assert calls == []
                page.locator("#settings").click()
                choice, hint = page.locator("#model-choice"), page.locator("#model-hint")
                expect(hint).to_contain_text("gpt-oss:20b")
                expect(choice).to_have_value("")
                expect(page.locator("#enable")).not_to_be_checked()
                expect(page.locator("#allow-paid")).not_to_be_checked()
                choice.select_option("gpt-oss:20b")
                page.locator("#enable").check()
                page.locator("#save-provider").click()
                expect(page.locator("#provider-status")).to_contain_text("explicit consent")
                page.locator("#enable").uncheck()
                catalog["mode"] = "retired"
                page.locator("#list-models").click()
                expect(hint).to_contain_text("outside this list")
                expect(choice).to_have_value("gpt-oss:20b")
                catalog["mode"] = "offline"
                page.locator("#list-models").click()
                expect(hint).to_contain_text("last list loaded")
                choice.select_option("__custom__")
                page.get_by_role("textbox", name="Custom model ID", exact=True).fill("fixture-custom")
                page.locator("#save-provider").click()
                expect(page.locator("#dialog")).not_to_be_visible()
                assert app.provider.model == "fixture-custom" and not app.provider.active
                page.locator("#settings").click()
                expect(choice).to_have_value("fixture-custom")
                catalog["mode"] = "online"
                page.locator("#provider").select_option("openrouter")
                expect(choice).to_have_value("openrouter/free")
                page.locator("#list-models").click()
                expect(hint).to_contain_text("3 text model IDs")
                expect(choice.locator("option[value='compact:free']")).to_have_count(1)
                expect(choice.locator("option[value='metered/large']")).to_have_count(0)
                page.locator("#allow-paid").check()
                expect(choice.locator("option[value='metered/large']")).to_have_count(1)
                page.locator("#provider").select_option("ollama-local")
                page.locator("#list-models").click()
                expect(choice.locator("option[value='installed:3b']")).to_have_count(1)
                page.locator("#provider").select_option("none")
                expect(choice).not_to_be_visible()
                for hours in (6, 12, 24):
                    page.locator("#interval").select_option(str(hours))
                    with page.expect_response(lambda r: r.url.endswith("/api/settings") and r.status == 200):
                        page.locator("#save-interval").click()
                    assert app.interval == hours
                page.locator("#save-provider").click()
                expect(page.locator("#dialog")).not_to_be_visible()
                assert app.provider.kind == "none" and not app.provider.active and not errors, errors
                print(f"{width}x{height} passed model selection, metered consent, offline handling and all schedules.")
            finally:
                context.close()
                server.shutdown()
                thread.join(timeout=3)


if __name__ == "__main__":
    with sync_playwright() as driver:
        browser = driver.chromium.launch(channel="chrome", headless=True)
        try:
            for size in ((1440, 900), (390, 844)):
                browser_check(browser, *size)
        finally:
            browser.close()
