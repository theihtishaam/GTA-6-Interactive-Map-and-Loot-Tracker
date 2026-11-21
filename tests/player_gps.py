"""Browser smoke test for local screenshot positioning and following an explicit game feed."""
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread

from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Atlas, LocalServer


def main():
    with tempfile.TemporaryDirectory(prefix="leonida-gps-ui-") as folder:
        runtime = Path(folder)
        reference = ROOT / ".atlas/powerpyx-map-original.png"
        shutil.copyfile(reference, runtime / reference.name)
        screenshot = runtime / "test-map-view.jpg"
        with Image.open(reference) as image:
            image.crop((1200, 1300, 2200, 2000)).convert("RGB").save(screenshot, quality=93)
        atlas = Atlas(cache=runtime / "test-state.json")
        with LocalServer(atlas, 0) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(channel="msedge", headless=True)
                    page = browser.new_page(viewport={"width":1280,"height":800})
                    base=f"http://127.0.0.1:{server.server_port}"
                    page.goto(base)
                    expect(page.locator("#map-img")).to_have_attribute("src","/game-map.png")
                    page.locator("#route-tools").click()
                    page.locator("#use-screenshot").click()
                    page.locator("#gps-file").set_input_files(screenshot)
                    page.locator("#gps-preview").click()
                    with page.expect_response(lambda r:r.url.endswith("/api/locate")) as response:
                        page.locator("#gps-confirm").click()
                    value=response.value.json()
                    assert response.value.ok and value["inliers"]>=10, value
                    expect(page.locator("#dialog")).not_to_be_visible()
                    expect(page.locator(".origin-ring")).to_have_count(1)
                    page.locator("#route-tools").click()
                    expect(page.locator("#dialog-body")).to_contain_text("Screenshot position")
                    page.get_by_text("Live position feed",exact=True).click()
                    page.locator("#follow-position").check()
                    assert page.request.post(base+"/api/position", data={"gameX":-3328,"gameY":768}).ok
                    expect(page.locator("#gps-feed-status")).to_contain_text("Position received", timeout=10000)
                    page.locator("#dialog-close").click()
                    page.locator("#route-tools").click()
                    expect(page.locator("#dialog-body")).to_contain_text("Live position")
                    print(f"Screenshot location accepted with {value['inliers']} inliers. Live grid input updated the route origin.")
                    browser.close()
            finally:
                server.shutdown()
                worker.join(timeout=2)


if __name__=="__main__":
    main()

