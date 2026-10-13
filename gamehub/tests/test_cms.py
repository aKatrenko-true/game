import pytest
from fastapi.testclient import TestClient
import app as gamehub


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(gamehub, "DB_PATH", tmp_path / "cms_test.db")
    monkeypatch.setattr(gamehub, "USE_POSTGRES", False)
    monkeypatch.setenv("ADMIN_PASSWORD", "cms-test-password")
    gamehub.init_db()
    gamehub.init_cms_tables()
    with TestClient(gamehub.app) as test_client:
        yield test_client


def admin_headers():
    return {"X-Admin-Password": "cms-test-password"}


def test_public_cms_content_returns_sections_and_settings(client):
    response = client.get("/api/cms/content")
    assert response.status_code == 200
    payload = response.json()
    assert any(section["slug"] == "hero" for section in payload["sections"])
    assert payload["settings"]["site_title"] == "GameHub"
    assert "ADMIN_PASSWORD" not in str(payload)


def test_cms_admin_api_requires_password(client):
    assert client.get("/api/admin/cms/sections").status_code == 401
    assert client.get("/api/admin/cms/settings").status_code == 401
    assert client.post("/api/admin/cms/sections", json={
        "title": "News", "slug": "news", "kind": "custom"
    }).status_code == 401


def test_cms_section_create_update_visibility_and_delete(client):
    created = client.post("/api/admin/cms/sections", headers=admin_headers(), json={
        "title": "Новости", "slug": "news", "kind": "custom",
        "body": "Последние новости", "visible": True, "sort_order": 60
    })
    assert created.status_code == 201, created.text
    section_id = created.json()["id"]

    updated = client.patch(f"/api/admin/cms/sections/{section_id}",
        headers=admin_headers(), json={"title": "Новости GameHub", "visible": False})
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Новости GameHub"
    assert updated.json()["visible"] in (0, False)

    public = client.get("/api/cms/content").json()
    saved = next(section for section in public["sections"] if section["slug"] == "news")
    assert saved["visible"] in (0, False)
    assert saved["body"] == ""

    deleted = client.delete(f"/api/admin/cms/sections/{section_id}", headers=admin_headers())
    assert deleted.status_code == 200
    assert all(section["slug"] != "news" for section in client.get("/api/cms/content").json()["sections"])


def test_cms_rejects_invalid_slug_and_duplicate_slug(client):
    invalid = client.post("/api/admin/cms/sections", headers=admin_headers(), json={
        "title": "Invalid", "slug": "Not Valid!", "kind": "custom"
    })
    assert invalid.status_code == 422
    duplicate = client.post("/api/admin/cms/sections", headers=admin_headers(), json={
        "title": "Another hero", "slug": "hero", "kind": "custom"
    })
    assert duplicate.status_code == 409


def test_cms_settings_persist_and_reject_unknown_keys_and_invalid_colors(client):
    saved = client.put("/api/admin/cms/settings/site_title", headers=admin_headers(),
                       json={"value": "My GameHub"})
    assert saved.status_code == 200
    assert client.get("/api/cms/content").json()["settings"]["site_title"] == "My GameHub"

    invalid_key = client.put("/api/admin/cms/settings/private_note", headers=admin_headers(),
                             json={"value": "should never be public"})
    assert invalid_key.status_code == 422

    invalid_color = client.put("/api/admin/cms/settings/primary_color", headers=admin_headers(),
                               json={"value": "red; background:url(https://example.com)"})
    assert invalid_color.status_code == 422

    # Even if a legacy/foreign setting exists in the table, the public API must not expose it.
    with gamehub.db() as connection:
        connection.execute("INSERT INTO cms_settings(key,value) VALUES(?,?)",
                            ("private_note", "must stay private"))
    public_settings = client.get("/api/cms/content").json()["settings"]
    assert "private_note" not in public_settings
