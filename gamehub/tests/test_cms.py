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


def test_cms_rejects_unknown_section_kind_on_create_and_update(client):
    invalid_create = client.post("/api/admin/cms/sections", headers=admin_headers(), json={
        "title": "Unknown block", "slug": "unknown-block", "kind": "script"
    })
    assert invalid_create.status_code == 422

    existing = client.get("/api/admin/cms/sections", headers=admin_headers()).json()
    hero = next(section for section in existing if section["slug"] == "hero")
    invalid_update = client.patch(
        f"/api/admin/cms/sections/{hero['id']}",
        headers=admin_headers(),
        json={"kind": "script"},
    )
    assert invalid_update.status_code == 422


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


def test_cms_settings_and_media_survive_database_reinitialization(client):
    section = client.post("/api/admin/cms/sections", headers=admin_headers(), json={
        "title": "Media check", "slug": "media-check", "kind": "gallery",
        "body": "Persist this content", "image_url": "data:image/png;base64,dGVzdA==",
        "visible": True, "sort_order": 77,
    })
    assert section.status_code == 201, section.text
    section_id = section.json()["id"]
    assert client.put("/api/admin/cms/settings/site_title", headers=admin_headers(),
                      json={"value": "Persistent GameHub"}).status_code == 200

    # Re-running table initialization simulates the application startup path after a restart.
    gamehub.init_cms_tables()
    public = client.get("/api/cms/content")
    assert public.status_code == 200
    assert public.json()["settings"]["site_title"] == "Persistent GameHub"
    saved = next(s for s in public.json()["sections"] if s["id"] == section_id)
    assert saved["body"] == "Persist this content"
    assert saved["image_url"] == "data:image/png;base64,dGVzdA=="
    assert saved["sort_order"] == 77


def test_cms_http_smoke_routes_and_static_assets(client):
    assert client.get("/").status_code == 200
    assert "cms-public.js" in client.get("/").text
    assert client.get("/admin/cms").status_code == 200
    assert client.get("/static/cms.js").status_code == 200
    assert client.get("/static/cms-public.js").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"


def test_public_cms_hidden_section_keeps_no_private_text_or_image(client):
    created = client.post("/api/admin/cms/sections", headers=admin_headers(), json={
        "title": "Secret draft", "slug": "secret-draft", "kind": "custom",
        "body": "PRIVATE CONTENT", "image_url": "data:image/png;base64,c2VjcmV0",
        "visible": True, "sort_order": 99,
    })
    assert created.status_code == 201
    section_id = created.json()["id"]
    hidden = client.patch(f"/api/admin/cms/sections/{section_id}",
                          headers=admin_headers(), json={"visible": False})
    assert hidden.status_code == 200
    public = client.get("/api/cms/content").json()
    section = next(s for s in public["sections"] if s["id"] == section_id)
    assert section["visible"] in (False, 0)
    assert section["body"] == ""
    assert section["image_url"] == ""


def test_admin_password_is_required_even_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    response = client.get("/api/admin/cms/sections")
    assert response.status_code == 503
    assert response.json()["detail"].startswith("Администратор не настроен")


def test_game_card_image_settings_are_writable_and_public(client):
    image = "data:image/png;base64," + ("a" * 30000)
    response = client.put("/api/admin/cms/settings/game_apex_image",
        headers=admin_headers(), json={"value": image})
    assert response.status_code == 200, response.text
    public = client.get("/api/cms/content").json()
    assert public["settings"]["game_apex_image"] == image


def test_game_card_image_settings_reject_unknown_keys(client):
    response = client.put("/api/admin/cms/settings/game_unlisted_image",
        headers=admin_headers(), json={"value": "https://example.com/image.png"})
    assert response.status_code == 422
