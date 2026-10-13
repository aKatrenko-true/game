import os
import uuid

# This file is run only against the disposable PostgreSQL service in GitHub Actions.
import app as gamehub


def test_postgres_schema_and_seed_policy():
    assert gamehub.USE_POSTGRES is True
    with gamehub.db() as con:
        tables = {
            row["name"]
            for row in con.execute(
                "SELECT table_name AS name FROM information_schema.tables "
                "WHERE table_schema='public'"
            ).fetchall()
        }
    assert {"players", "teams", "matches", "users", "sessions", "lfg_posts", "cms_sections", "cms_settings"} <= tables


def test_postgres_init_is_idempotent_and_seeds_demo_data_when_enabled(monkeypatch):
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    gamehub.init_db()
    with gamehub.db() as con:
        first_players = con.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        first_teams = con.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        first_matches = con.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        assert first_players >= 60
        assert first_teams >= 6
        assert first_matches >= 3
        nickname = "PG_KEEP_" + uuid.uuid4().hex[:10]
        con.execute(
            "INSERT INTO players(nickname,game,rank,wins) VALUES(?,?,?,?)",
            (nickname, "CS2", "Unranked", 0),
        )
    gamehub.init_db()
    with gamehub.db() as con:
        assert con.execute("SELECT COUNT(*) FROM players").fetchone()[0] == first_players + 1
        assert con.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == first_teams
        assert con.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == first_matches
        assert con.execute(
            "SELECT COUNT(*) FROM players WHERE nickname=?", (nickname,)
        ).fetchone()[0] == 1



def test_postgres_player_create_and_read():
    nickname = "PG_" + uuid.uuid4().hex[:12]
    with gamehub.db() as con:
        cur = con.execute(
            "INSERT INTO players(nickname,game,rank,wins) VALUES(?,?,?,?)",
            (nickname, "CS2", "Unranked", 0),
        )
        player_id = cur.lastrowid
        assert player_id is not None
        row = con.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
        assert row["nickname"] == nickname
        assert row[0] == player_id



def test_postgres_api_register_and_lfg_round_trip():
    from fastapi.testclient import TestClient

    nickname = "PG_API_" + uuid.uuid4().hex[:8]
    with TestClient(gamehub.app) as client:
        registered = client.post("/api/auth/register", json={
            "nickname": nickname,
            "password": "TestPassword_123",
            "game": "CS2",
            "rank": "Unranked",
            "region": "EU",
            "play_time": "Вечером",
            "play_style": "Любой",
            "looking_for": "Напарника",
        })
        assert registered.status_code == 200, registered.text
        me = client.get("/api/auth/me")
        assert me.status_code == 200, me.text
        assert me.json()["nickname"] == nickname
        created = client.post("/api/lfg", json={
            "game": "CS2",
            "post_type": "duo",
            "rank": "Unranked",
            "region": "EU",
            "platform": "PC",
            "language": "Русский",
            "play_time": "Вечером",
            "description": "PostgreSQL integration check",
        })
        assert created.status_code == 201, created.text
        listing = client.get("/api/lfg", params={"game": "CS2"})
        assert listing.status_code == 200, listing.text
        assert any(item["id"] == created.json()["id"] for item in listing.json())


def test_postgres_team_and_match_endpoints():
    from fastapi.testclient import TestClient

    suffix = uuid.uuid4().hex[:8]
    team_a = "PG Team A " + suffix
    team_b = "PG Team B " + suffix
    with TestClient(gamehub.app) as client:
        team = client.post("/api/teams", json={
            "name": team_a, "game": "CS2", "description": "Postgres test"
        })
        assert team.status_code == 201, team.text
        team2 = client.post("/api/teams", json={
            "name": team_b, "game": "CS2", "description": "Postgres test"
        })
        assert team2.status_code == 201, team2.text
        match = client.post("/api/matches", json={
            "game": "CS2", "team_a": team_a, "team_b": team_b,
            "scheduled_at": "2026-10-20 18:00"
        })
        assert match.status_code == 201, match.text
        assert match.json()["team_a"] == team_a
        assert any(x["id"] == match.json()["id"] for x in client.get("/api/matches").json())


def test_sqlite_migration_script_copies_data_and_is_rerunnable(tmp_path, monkeypatch):
    import sqlite3
    import subprocess
    import sys
    from pathlib import Path

    source_path = tmp_path / "source.db"
    source = sqlite3.connect(source_path)
    source.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            nickname TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            nickname TEXT UNIQUE NOT NULL,
            game TEXT NOT NULL,
            rank TEXT NOT NULL DEFAULT 'Unranked',
            wins INTEGER NOT NULL DEFAULT 0,
            region TEXT NOT NULL DEFAULT 'EU',
            play_time TEXT NOT NULL DEFAULT 'Вечером',
            play_style TEXT NOT NULL DEFAULT 'Любой',
            looking_for TEXT NOT NULL DEFAULT 'Напарника',
            user_id INTEGER UNIQUE
        );
        INSERT INTO users(id,nickname,password_hash) VALUES(71,'MigrationUser','hashed-test-value');
        INSERT INTO players(id,nickname,game,rank,wins,user_id)
        VALUES(81,'MigrationPlayer','CS2','Gold Nova',7,71);
    """)
    source.commit()
    source.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = gamehub.DATABASE_URL
    script = str(gamehub.BASE / "migrate_sqlite_to_postgres.py")
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, script, str(source_path)],
            cwd=str(gamehub.BASE),
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + "\n" + result.stderr

    with gamehub.db() as con:
        user = con.execute("SELECT * FROM users WHERE id=?", (71,)).fetchone()
        player = con.execute("SELECT * FROM players WHERE id=?", (81,)).fetchone()
        assert user["nickname"] == "MigrationUser"
        assert user["password_hash"] == "hashed-test-value"
        assert player["nickname"] == "MigrationPlayer"
        assert player["user_id"] == 71
        assert con.execute("SELECT COUNT(*) FROM users WHERE id=71").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM players WHERE id=81").fetchone()[0] == 1
    assert source_path.exists()



def test_postgres_cms_section_create_and_public_read(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ADMIN_PASSWORD", "postgres-cms-test-password")
    slug = "pg-cms-" + uuid.uuid4().hex[:10]
    with TestClient(gamehub.app) as client:
        created = client.post("/api/admin/cms/sections",
            headers={"X-Admin-Password": "postgres-cms-test-password"},
            json={"title": "Postgres CMS", "slug": slug, "kind": "custom",
                  "body": "CMS database round trip", "visible": True, "sort_order": 9000})
        assert created.status_code == 201, created.text
        section_id = created.json()["id"]
        assert isinstance(section_id, int) and section_id > 0
        public = client.get("/api/cms/content")
        assert public.status_code == 200
        section = next(s for s in public.json()["sections"] if s["slug"] == slug)
        assert section["id"] == section_id
        assert section["body"] == "CMS database round trip"
        deleted = client.delete(f"/api/admin/cms/sections/{section_id}",
            headers={"X-Admin-Password": "postgres-cms-test-password"})
        assert deleted.status_code == 200, deleted.text



def test_postgres_cms_settings_and_hidden_media_persist():
    from fastapi.testclient import TestClient

    monkeypatch_password = "postgres-cms-persist-test"
    os.environ["ADMIN_PASSWORD"] = monkeypatch_password
    slug = "pg-cms-hidden-" + uuid.uuid4().hex[:10]
    headers = {"X-Admin-Password": monkeypatch_password}
    with TestClient(gamehub.app) as client:
        created = client.post("/api/admin/cms/sections", headers=headers, json={
            "title": "Hidden media", "slug": slug, "kind": "gallery",
            "body": "Sensitive draft body", "image_url": "data:image/png;base64,dGVzdA==",
            "visible": True, "sort_order": 9010,
        })
        assert created.status_code == 201, created.text
        section_id = created.json()["id"]
        saved = client.put("/api/admin/cms/settings/site_title", headers=headers,
                           json={"value": "Postgres persistence check"})
        assert saved.status_code == 200, saved.text

        gamehub.init_cms_tables()
        public = client.get("/api/cms/content").json()
        assert public["settings"]["site_title"] == "Postgres persistence check"
        section = next(item for item in public["sections"] if item["id"] == section_id)
        assert section["body"] == "Sensitive draft body"
        assert section["image_url"] == "data:image/png;base64,dGVzdA=="

        hidden = client.patch(f"/api/admin/cms/sections/{section_id}", headers=headers,
                              json={"visible": False})
        assert hidden.status_code == 200, hidden.text
        hidden_public = client.get("/api/cms/content").json()
        section = next(item for item in hidden_public["sections"] if item["id"] == section_id)
        assert section["visible"] in (False, 0)
        assert section["body"] == ""
        assert section["image_url"] == ""
        assert client.delete(f"/api/admin/cms/sections/{section_id}", headers=headers).status_code == 200
