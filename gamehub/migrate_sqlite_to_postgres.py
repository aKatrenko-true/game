"""One-time, idempotent copy of an existing GameHub SQLite database to PostgreSQL.

Run only after the PostgreSQL schema has been created by the app:
  python migrate_sqlite_to_postgres.py /path/to/gamehub.db

DATABASE_URL must point to the target PostgreSQL database. This script copies rows
without deleting the source and preserves primary keys, passwords hashes and sessions.
"""
import os
import sqlite3
import sys

TABLES = ("users", "players", "teams", "matches", "sessions", "lfg_posts")

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python migrate_sqlite_to_postgres.py /path/to/gamehub.db")
    source_path = sys.argv[1]
    url = os.getenv("DATABASE_URL", "").strip()
    if not url.startswith(("postgres://", "postgresql://")):
        raise SystemExit("DATABASE_URL must point to the target PostgreSQL database")
    if not os.path.isfile(source_path):
        raise SystemExit(f"SQLite source database not found: {source_path}")

    import psycopg
    from psycopg import sql
    # Ensure the destination schema exists without seeding demo rows.
    import app as gamehub
    if not gamehub.USE_POSTGRES:
        raise SystemExit("Import app with DATABASE_URL set before running migration")
    gamehub.init_db()

    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    with psycopg.connect(url) as target:
        # Parents before children; all inserts are conflict-safe so reruns are possible.
        for table in TABLES:
            exists = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                print(f"{table}: source table absent, skipped")
                continue
            columns = [row["name"] for row in source.execute(f'PRAGMA table_info("{table}")')]
            rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
            if not rows:
                print(f"{table}: 0 rows")
                continue
            statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(col) for col in columns),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            )
            with target.cursor() as cur:
                cur.executemany(statement, [tuple(row[col] for col in columns) for row in rows])
            print(f"{table}: processed {len(rows)} source rows")
        # Fix identity sequences after preserving explicit IDs.
        for table in ("players", "teams", "matches", "users", "lfg_posts"):
            target.execute(
                sql.SQL("SELECT setval(pg_get_serial_sequence({}, 'id'), "
                        "GREATEST(COALESCE((SELECT MAX(id) FROM {}), 1), 1), "
                        "EXISTS(SELECT 1 FROM {}))").format(
                    sql.Literal(table), sql.Identifier(table), sql.Identifier(table)
                )
            )
    source.close()
    print("Migration copy finished. Source SQLite file was not modified.")

if __name__ == "__main__":
    main()
