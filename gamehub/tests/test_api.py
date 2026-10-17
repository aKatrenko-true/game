import os
import tempfile
from pathlib import Path

# app.py initializes its database at import time. Keep that bootstrap database
# outside the repository so collecting tests never creates gamehub/gamehub.db.
bootstrap_db = Path(tempfile.gettempdir()) / f"gamehub-test-bootstrap-{os.getpid()}.db"
os.environ["GAMEHUB_DB"] = str(bootstrap_db)

import pytest
from fastapi.testclient import TestClient
import app as gamehub

bootstrap_db.unlink(missing_ok=True)

def setup_function():
    gamehub.DB_PATH = Path(tempfile.gettempdir()) / f"gamehub-test-{os.getpid()}.db"
    gamehub.init_db()

def teardown_function():
    try: gamehub.DB_PATH.unlink(missing_ok=True)
    except Exception: pass

def test_health():
    with TestClient(gamehub.app) as client:
        assert client.get("/api/health").status_code == 200

def test_players_seeded():
    with TestClient(gamehub.app) as client:
        r = client.get("/api/players")
        assert r.status_code == 200
        assert len(r.json()) >= 20

def test_create_player_and_duplicate():
    with TestClient(gamehub.app) as client:
        payload = {"nickname":"NewTester_01","game":"CS2","rank":"Gold Nova"}
        assert client.post("/api/players",json=payload).status_code == 201
        assert client.post("/api/players",json=payload).status_code == 409

def test_invalid_nickname():
    with TestClient(gamehub.app) as client:
        r = client.post("/api/players",json={"nickname":"x!","game":"CS2","rank":"Gold"})
        assert r.status_code == 422

def test_player_search():
    with TestClient(gamehub.app) as client:
        r = client.get("/api/players",params={"q":"Aveli"})
        assert r.status_code == 200
        assert any(p["nickname"] == "Aveli" for p in r.json())

def test_create_match_against_self_rejected():
    with TestClient(gamehub.app) as client:
        r = client.post("/api/matches",json={"game":"CS2","team_a":"Night Owls","team_b":"night owls","scheduled_at":"2026-10-20 18:00"})
        assert r.status_code == 422

def test_lfg_requires_login_to_create():
    with TestClient(gamehub.app) as client:
        r = client.post("/api/lfg", json={"game":"CS2","post_type":"duo"})
        assert r.status_code == 401

def test_lfg_create_and_list_for_authenticated_user():
    with TestClient(gamehub.app) as client:
        register = client.post("/api/auth/register", json={
            "nickname":"LfgTester_01","password":"TestPassword_123",
            "game":"CS2","rank":"Gold Nova","region":"EU",
            "play_time":"Вечером","play_style":"Любой","looking_for":"Напарника"
        })
        assert register.status_code == 201
        created = client.post("/api/lfg", json={
            "game":"CS2","post_type":"duo","rank":"Gold Nova","region":"EU",
            "platform":"PC","language":"Русский","play_time":"Вечером",
            "description":"Ищу напарника для рейтинга"
        })
        assert created.status_code == 201
        assert created.json()["nickname"] == "LfgTester_01"
        listing = client.get("/api/lfg", params={"game":"CS2","region":"EU"})
        assert listing.status_code == 200
        assert any(x["id"] == created.json()["id"] for x in listing.json())

def test_lfg_validation_rejects_unknown_post_type():
    with TestClient(gamehub.app) as client:
        register = client.post("/api/auth/register", json={
            "nickname":"LfgTester_02","password":"TestPassword_123","game":"CS2"
        })
        assert register.status_code == 201
        r = client.post("/api/lfg", json={"game":"CS2","post_type":"whatever"})
        assert r.status_code == 422

def test_lfg_user_cannot_close_another_users_post():
    with TestClient(gamehub.app) as first:
        assert first.post("/api/auth/register", json={
            "nickname":"LfgOwner_01","password":"TestPassword_123","game":"CS2"
        }).status_code == 201
        post = first.post("/api/lfg", json={"game":"CS2","post_type":"duo"})
        assert post.status_code == 201
        post_id = post.json()["id"]
    with TestClient(gamehub.app) as second:
        assert second.post("/api/auth/register", json={
            "nickname":"LfgOther_01","password":"TestPassword_123","game":"CS2"
        }).status_code == 201
        r = second.patch(f"/api/lfg/{post_id}", json={"status":"closed"})
        assert r.status_code == 403


def test_login_logout_and_session_revocation():
    with TestClient(gamehub.app) as client:
        registered = client.post("/api/auth/register", json={
            "nickname": "AuthFlow_01", "password": "TestPassword_123", "game": "CS2"
        })
        assert registered.status_code == 201
        assert client.get("/api/auth/me").status_code == 200

        logged_out = client.post("/api/auth/logout")
        assert logged_out.status_code == 200
        assert client.get("/api/auth/me").status_code == 401

        login = client.post("/api/auth/login", json={
            "nickname": "AuthFlow_01", "password": "TestPassword_123"
        })
        assert login.status_code == 200
        assert client.get("/api/auth/me").status_code == 200


def test_login_rejects_wrong_password():
    with TestClient(gamehub.app) as client:
        assert client.post("/api/auth/register", json={
            "nickname": "AuthWrong_01", "password": "TestPassword_123", "game": "CS2"
        }).status_code == 201
        response = client.post("/api/auth/login", json={
            "nickname": "AuthWrong_01", "password": "WrongPassword_123"
        })
        assert response.status_code == 401


def test_admin_api_requires_configured_password(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with TestClient(gamehub.app) as client:
        response = client.get("/api/admin/summary")
        assert response.status_code == 503


def test_admin_api_rejects_wrong_password(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "TestAdminPassword_123")
    with TestClient(gamehub.app) as client:
        response = client.get("/api/admin/summary", headers={
            "X-Admin-Password": "WrongAdminPassword_123"
        })
        assert response.status_code == 401


def test_admin_api_accepts_correct_password(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "TestAdminPassword_123")
    with TestClient(gamehub.app) as client:
        response = client.get("/api/admin/summary", headers={
            "X-Admin-Password": "TestAdminPassword_123"
        })
        assert response.status_code == 200
