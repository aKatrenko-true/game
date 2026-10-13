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
    assert {"players", "teams", "matches", "users", "sessions", "lfg_posts"} <= tables


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


def test_postgres_init_is_idempotent_and_does_not_seed_fake_players():
    with gamehub.db() as con:
        nickname = "PG_KEEP_" + uuid.uuid4().hex[:10]
        con.execute(
            "INSERT INTO players(nickname,game,rank,wins) VALUES(?,?,?,?)",
            (nickname, "CS2", "Unranked", 0),
        )
    gamehub.init_db()
    with gamehub.db() as con:
        assert con.execute(
            "SELECT COUNT(*) FROM players WHERE nickname=?", (nickname,)
        ).fetchone()[0] == 1


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
