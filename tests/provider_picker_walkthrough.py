"""Exercise Settings in disposable browser sessions with a synthetic provider catalogue."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
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
    checks = []
    hold_cloud, release_cloud = Event(), Event()

    def check_access(config):
        checks.append((config.kind, config.base))
        if config.key == "synthetic-invalid":
            raise RuntimeError("Fixture service rejected the key.")
        if config.kind == "ollama-local":
            return "local"
        return "verified" if config.kind in ("ollama-cloud", "openrouter") and config.key else "catalogue-only"

    def fixture(config):
        calls.append(config.kind)
        if config.kind == "ollama-cloud" and catalog["mode"] == "delayed":
            hold_cloud.set()
            release_cloud.wait(4)
        if catalog["mode"] == "offline":
            raise RuntimeError("Fixture catalogue unavailable.")
        if config.kind == "openrouter":
            rows = [{"id": "openrouter/free"}, {"id": "compact:free"}, {"id": "metered/large"}]
            if catalog["mode"] == "free-120b":
                rows.append({"id": "openai/gpt-oss-120b:free"})
        elif config.kind == "ollama-local":
            return list_models(config, lambda *_, **__: b'{"models":[{"name":"installed:3b"},{"name":"gpt-oss:120b"}]}')
        else:
            rows = [{"id": "gpt-oss:20b"}, {"id": "gemma4:31b"}, {"id": "gpt-oss:120b"}]
            if catalog["mode"] == "retired":
                rows.pop(0)
        return list_models(config, lambda *_, **__: json.dumps({"data": rows}).encode())

    with TemporaryDirectory(prefix="atlas-provider-test-") as folder, patch("server.list_models", fixture), patch("server.check_access", check_access):
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
                expect(hint).to_contain_text("gpt-oss:120b")
                expect(choice).to_have_value("gpt-oss:120b")
                expect(page.locator("#enable")).not_to_be_checked()
                expect(page.locator("#allow-paid")).not_to_be_checked()
                assert page.locator("#key").evaluate("(el) => !!(el.compareDocumentPosition(document.querySelector('#provider')) & Node.DOCUMENT_POSITION_FOLLOWING)")
                provider, key = page.locator("#provider"), page.locator("#key")
                key.fill("synthetic-opaque-key")
                expect(provider).to_have_value("")
                expect(page.locator("#key-route")).to_contain_text("issued this key")
                expect(page.locator("#save-provider")).to_be_disabled()
                page.wait_for_timeout(550)
                assert not checks
                provider.select_option("ollama-cloud")
                expect(page.locator("#key-route")).to_contain_text("confirmed this key")
                assert [kind for kind, _ in checks] == ["ollama-cloud"] and not app.requested
                provider.select_option("openrouter")
                expect(key).to_have_value("")
                expect(hint).to_contain_text("3 text model IDs")
                provider.select_option("ollama-cloud")
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
                expect(hint).to_contain_text("3 text model IDs")
                expect(choice.locator("option[value='compact:free']")).to_have_count(1)
                expect(choice.locator("option[value='metered/large']")).to_have_count(0)
                catalog["mode"] = "free-120b"
                page.locator("#list-models").click()
                expect(choice).to_have_value("openai/gpt-oss-120b:free")
                choice.select_option("compact:free")
                page.locator("#list-models").click()
                expect(hint).to_contain_text("4 text model IDs")
                expect(choice).to_have_value("compact:free")
                catalog["mode"] = "online"
                page.locator("#allow-paid").check()
                expect(choice.locator("option[value='metered/large']")).to_have_count(1)
                provider.select_option("custom")
                key.fill("synthetic-custom")
                page.locator("#base").fill("https://fixture.example/v1")
                page.locator("#base").press("Tab")
                expect(page.locator("#key-route")).to_contain_text("catalogue responded")
                assert ("custom", "https://fixture.example/v1") in checks
                page.locator("#base").fill("https://second-fixture.example/v1")
                expect(key).to_have_value("")
                page.locator("#provider").select_option("ollama-local")
                expect(choice.locator("option[value='installed:3b']")).to_have_count(1)
                expect(choice).to_have_value("gpt-oss:120b")
                provider.select_option("ollama-cloud")
                catalog["mode"] = "delayed"
                page.locator("#list-models").click()
                assert hold_cloud.wait(3)
                key.fill("sk-or-v1-" + ("a" * 64))
                expect(provider).to_have_value("openrouter")
                expect(page.locator("#key-route")).to_contain_text("confirmed this key")
                catalog["mode"] = "online"
                release_cloud.set()
                assert checks[-1][0] == "openrouter"
                expect(choice).to_have_value("openrouter/free")
                expect(choice.locator("option[value='gpt-oss:20b']")).to_have_count(0)
                page.locator("#enable").check()
                page.get_by_role("button", name="Connect and scan").click()
                expect(page.locator("#dialog")).not_to_be_visible()
                assert app.requested and app.provider.active and app.provider.kind == "openrouter"
                app.requested = False
                page.locator("#settings").click()
                expect(page.locator("#key-route")).to_contain_text("confirmed this key")
                page.get_by_role("button", name="Connect and scan").click()
                expect(page.locator("#dialog")).not_to_be_visible()
                assert not app.requested
                page.locator("#settings").click()
                key.fill("synthetic-invalid")
                expect(provider).to_have_value("")
                provider.select_option("openrouter")
                expect(page.locator("#key-route")).to_contain_text("rejected")
                page.get_by_role("button", name="Connect and scan").click()
                expect(page.locator("#provider-status")).to_contain_text("rejected")
                assert not app.requested
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
                print(f"{width}x{height} passed single-destination checks, automatic models, opt-in scan, cost consent, offline and schedule controls.")
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
