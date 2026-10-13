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
