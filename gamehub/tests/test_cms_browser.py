import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def browser_app(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("gamehub-browser") / "browser.db"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env["GAMEHUB_DB"] = str(db_path)
    env["ADMIN_PASSWORD"] = "browser-cms-test-password"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        import urllib.request
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("GameHub test server exited before becoming ready")
            try:
                with urllib.request.urlopen(base_url + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("GameHub test server did not become ready")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_homepage_runs_cms_without_browser_errors_and_supports_mobile(browser_app):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        response = page.goto(browser_app, wait_until="networkidle")
        assert response and response.status == 200
        page.wait_for_function("document.querySelector('#api')?.textContent === 'Подключено'")
        assert page.locator(".mobile-nav").is_visible()
        assert page.locator(".hero").is_visible()
        assert not page_errors, "Browser JavaScript errors: " + "; ".join(page_errors)
        browser.close()


def test_hidden_cms_views_hide_desktop_mobile_navigation_and_block_spa_route(browser_app):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(browser_app, wait_until="networkidle")
        password = "browser-cms-test-password"
        for slug in ("players", "teams", "matches"):
            response = page.request.get(browser_app + "/api/admin/cms/sections",
                                        headers={"X-Admin-Password": password})
            assert response.status == 200, response.text()
            sections = response.json()
            section = next(item for item in sections if item["slug"] == slug)
            update = page.request.patch(
                browser_app + f"/api/admin/cms/sections/{section['id']}",
                headers={"X-Admin-Password": password},
                data={"visible": False},
            )
            assert update.status == 200, update.text()

        page.reload(wait_until="networkidle")
        for view in ("players", "teams", "matches"):
            assert page.locator(f'.sidebar [data-view="{view}"]').is_hidden()
            assert page.locator(f'.mobile-nav [data-view="{view}"]').is_hidden()
        page.evaluate("window.render('teams')")
        assert page.locator("#crumb").inner_text() == "Обзор"
        browser.close()
