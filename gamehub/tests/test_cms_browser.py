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

        # Re-enable a view and ensure it becomes available again after CMS refresh.
        sections = page.request.get(browser_app + "/api/admin/cms/sections",
                                    headers={"X-Admin-Password": password}).json()
        teams = next(item for item in sections if item["slug"] == "teams")
        restored = page.request.patch(
            browser_app + f"/api/admin/cms/sections/{teams['id']}",
            headers={"X-Admin-Password": password},
            data={"visible": True},
        )
        assert restored.status == 200, restored.text()
        page.reload(wait_until="networkidle")
        assert page.locator('.sidebar [data-view="teams"]').is_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.locator('.mobile-nav [data-view="teams"]').is_visible()
        browser.close()


def test_cms_custom_content_is_rendered_as_text_without_executing_markup(browser_app):
    password = "browser-cms-test-password"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        created = page.request.post(
            browser_app + "/api/admin/cms/sections",
            headers={"X-Admin-Password": password},
            data={
                "title": "Browser XSS regression",
                "slug": "browser-xss-regression",
                "kind": "custom",
                "body": '<img src=x onerror="window.__cmsXss=1">literal markup',
                "image_url": "",
                "visible": True,
                "sort_order": 999,
            },
        )
        assert created.status == 201, created.text()
        page.goto(browser_app, wait_until="networkidle")
        section = page.locator('[data-cms-slug="browser-xss-regression"]')
        assert section.is_visible()
        assert section.locator("p").inner_text() == '<img src=x onerror="window.__cmsXss=1">literal markup'
        assert section.locator("img").count() == 0
        assert page.evaluate("window.__cmsXss || 0") == 0
        browser.close()


def test_cms_admin_login_and_appearance_editor_work_in_browser(browser_app):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(browser_app + "/admin/cms", wait_until="networkidle")

        assert page.locator("#cms-login").is_visible()
        assert page.locator("#cms-app").is_hidden()

        page.locator("#cms-password").fill("wrong-password")
        page.locator("#cms-login-form button").click()
        page.wait_for_function("document.querySelector('#cms-login-error')?.textContent.trim().length > 0")

        page.locator("#cms-password").fill("browser-cms-test-password")
        page.locator("#cms-login-form button").click()
        page.wait_for_function("document.querySelector('#cms-app') && !document.querySelector('#cms-app').hidden")

        page.locator('[data-cms-tab="appearance"]').click()
        page.locator('input[name="site_title"]').fill("GameHub Browser Test")
        page.locator('input[name="primary_color"]').fill("#123ABC")
        page.locator("#appearance-form button").click()
        page.wait_for_function("document.querySelector('#cms-notice')?.textContent.includes('сохранены')")

        public = page.request.get(browser_app + "/api/cms/content").json()
        assert public["settings"]["site_title"] == "GameHub Browser Test"
        assert public["settings"]["primary_color"] == "#123ABC"
        assert not errors, "CMS browser JavaScript errors: " + "; ".join(errors)
        browser.close()


def test_cms_media_upload_saves_image_to_selected_section(browser_app, tmp_path):
    from base64 import b64encode

    password = "browser-cms-test-password"
    # A tiny valid PNG fixture (1x1 pixel).
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000b49444154789c636000020000050001a5f645400000000049454e44ae426082"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(browser_app + "/admin/cms", wait_until="networkidle")
        page.locator("#cms-password").fill(password)
        page.locator("#cms-login-form button").click()
        page.wait_for_function("document.querySelector('#cms-app') && !document.querySelector('#cms-app').hidden")

        page.locator('[data-cms-tab="media"]').click()
        page.locator("#media-file").set_input_files({
            "name": "pixel.png",
            "mimeType": "image/png",
            "buffer": png_bytes,
        })
        page.wait_for_function("document.querySelector('#media-save') && !document.querySelector('#media-save').disabled")
        page.locator("#media-save").click()
        page.wait_for_function("document.querySelector('#cms-notice')?.textContent.includes('Изображение сохранено')")

        section_id = int(page.locator("#media-section").input_value())
        sections = page.request.get(
            browser_app + "/api/admin/cms/sections",
            headers={"X-Admin-Password": password},
        ).json()
        selected = next(s for s in sections if s["id"] == section_id)
        assert selected["image_url"].startswith("data:image/png;base64,")
        assert b64encode(png_bytes).decode() in selected["image_url"]
        browser.close()



def test_cms_section_edits_persist_after_reload(browser_app):
    password = "browser-cms-test-password"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(browser_app + "/admin/cms", wait_until="networkidle")
        page.locator("#cms-password").fill(password)
        page.locator("#cms-login-form button").click()
        page.wait_for_function("document.querySelector('#cms-app') && !document.querySelector('#cms-app').hidden")

        section = page.locator(".cms-section").first
        section_id = int(section.get_attribute("data-id"))
        title = section.locator('[data-field="title"]')
        body = section.locator('[data-field="body"]')
        updated_title = "Browser persistence regression"
        updated_body = "CMS body persists after page reload"
        title.fill(updated_title)
        body.fill(updated_body)
        section.locator(".save-section").click()
        page.wait_for_function("document.querySelector('#cms-notice')?.textContent.includes('Изменения сохранены')")

        page.reload(wait_until="networkidle")
        page.wait_for_function("document.querySelector('#cms-app') && !document.querySelector('#cms-app').hidden")
        saved = page.locator(f'.cms-section[data-id="{section_id}"]')
        assert saved.locator('[data-field="title"]').input_value() == updated_title
        assert saved.locator('[data-field="body"]').input_value() == updated_body

        response = page.request.get(
            browser_app + "/api/admin/cms/sections",
            headers={"X-Admin-Password": password},
        )
        assert response.status == 200, response.text()
        persisted = next(item for item in response.json() if item["id"] == section_id)
        assert persisted["title"] == updated_title
        assert persisted["body"] == updated_body
        browser.close()


@pytest.mark.parametrize(
    ("name", "mime_type", "buffer", "expected_notice"),
    [
        ("notes.txt", "text/plain", b"not an image", "Неподдерживаемый формат"),
        ("oversized.png", "image/png", b"x" * (int(1.5 * 1024 * 1024) + 1), "Файл больше 1,5 МБ"),
    ],
)
def test_cms_media_rejects_unsupported_or_oversized_files(
    browser_app, name, mime_type, buffer, expected_notice
):
    password = "browser-cms-test-password"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(browser_app + "/admin/cms", wait_until="networkidle")
        page.locator("#cms-password").fill(password)
        page.locator("#cms-login-form button").click()
        page.wait_for_function("document.querySelector('#cms-app') && !document.querySelector('#cms-app').hidden")
        page.locator('[data-cms-tab="media"]').click()

        page.locator("#media-file").set_input_files({
            "name": name,
            "mimeType": mime_type,
            "buffer": buffer,
        })
        page.wait_for_function(
            "() => document.querySelector('#cms-notice')?.textContent.includes(" + repr(expected_notice) + ")"
        )
        assert page.locator("#media-save").is_disabled()
        assert page.locator("#media-file").input_value() == ""
        browser.close()
