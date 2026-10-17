from contextlib import asynccontextmanager
from pathlib import Path
import os, sqlite3, hashlib, hmac, time
from typing import Optional
import secrets
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = Path(os.getenv("GAMEHUB_DB", BASE / "gamehub.db"))
USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

class HybridRow(dict):
    """A row supporting both SQLite-style numeric and named column access."""
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

class CompatCursor:
    def __init__(self, cursor, columns=None, lastrowid=None):
        self._cursor = cursor
        self._columns = columns
        self.lastrowid = lastrowid
    @property
    def rowcount(self):
        return self._cursor.rowcount
    def _row(self, row):
        if row is None:
            return None
        if isinstance(row, dict):
            return HybridRow(row.keys(), row.values())
        return HybridRow(self._columns or [d[0] for d in self._cursor.description], row)
    def fetchone(self):
        return self._row(self._cursor.fetchone())
    def fetchall(self):
        return [self._row(r) for r in self._cursor.fetchall()]

class PostgresConnection:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self._psycopg = psycopg
        self._con = psycopg.connect(url, row_factory=dict_row)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self._con.rollback()
        else:
            self._con.commit()
        self._con.close()
    def execute(self, sql, args=()):
        sql = sql.strip()
        # PostgreSQL requires an explicit cast when timestamp defaults target TEXT columns.
        sql = sql.replace("DEFAULT CURRENT_TIMESTAMP", "DEFAULT (CURRENT_TIMESTAMP::text)")
        if sql.upper().startswith("PRAGMA TABLE_INFO("):
            table = sql[sql.find("(")+1:sql.rfind(")")].strip().strip('"')
            cur = self._con.execute(
                "SELECT ordinal_position AS cid, column_name AS name, data_type AS type, "
                "0 AS not_null, NULL AS dflt_value, ordinal_position AS pk "
                "FROM information_schema.columns WHERE table_schema='public' AND table_name=%s "
                "ORDER BY ordinal_position", (table,))
            rows = cur.fetchall()
            return CompatCursor(_RowsCursor([
                (i, row["name"], row["type"], 0, None, i if row["name"] == "id" else 0)
                for i, row in enumerate(rows)
            ], ["cid","name","type","notnull","dflt_value","pk"]))
        if sql.upper().startswith("INSERT OR IGNORE INTO"):
            sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
            if " ON CONFLICT " not in sql.upper():
                sql += " ON CONFLICT DO NOTHING"
        # Use serial identity columns for new tables.
        sql = sql.replace("INTEGER PRIMARY KEY,", "BIGSERIAL PRIMARY KEY,")
        sql = sql.replace("INTEGER PRIMARY KEY)", "BIGSERIAL PRIMARY KEY)")
        sql = sql.replace("?", "%s")
        table = None
        if sql.upper().startswith("INSERT INTO"):
            try:
                table = sql.split(None, 3)[2].split("(")[0].strip('"')
            except Exception:
                table = None
        has_returning = " RETURNING " in sql.upper()
        needs_id = table in {"players","teams","matches","users","lfg_posts","cms_sections"} and not has_returning and "ON CONFLICT DO NOTHING" not in sql.upper()
        if needs_id:
            sql += " RETURNING id"
        cur = self._con.execute(sql, args)
        lastrowid = None
        if needs_id:
            row = cur.fetchone()
            if row:
                lastrowid = row["id"]
            # Keep cursor behavior predictable for callers that only need lastrowid.
            cur = _RowsCursor([], [])
        return CompatCursor(cur, lastrowid=lastrowid)
    def executemany(self, sql, seq):
        sql = sql.replace("?", "%s")
        if sql.upper().startswith("INSERT OR IGNORE INTO"):
            sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
            if " ON CONFLICT " not in sql.upper():
                sql += " ON CONFLICT DO NOTHING"
        sql = sql.replace("INTEGER PRIMARY KEY,", "BIGSERIAL PRIMARY KEY,")
        sql = sql.replace("INTEGER PRIMARY KEY)", "BIGSERIAL PRIMARY KEY)")
        cur = self._con.cursor()
        cur.executemany(sql, seq)
        return CompatCursor(cur)
    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)
        return CompatCursor(_RowsCursor([], []))

class _RowsCursor:
    def __init__(self, rows, columns):
        self._rows = list(rows)
        self._columns = columns
        self.description = [(c,) for c in columns] if columns else None
        self.rowcount = len(self._rows)
    def fetchone(self):
        return self._rows.pop(0) if self._rows else None
    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

def db():
    if USE_POSTGRES:
        return PostgresConnection(DATABASE_URL)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def is_integrity_error(exc):
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    try:
        import psycopg
        return isinstance(exc, psycopg.IntegrityError)
    except ImportError:
        return False

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY, nickname TEXT UNIQUE NOT NULL, game TEXT NOT NULL, rank TEXT NOT NULL DEFAULT 'Unranked', wins INTEGER NOT NULL DEFAULT 0 CHECK(wins>=0), region TEXT NOT NULL DEFAULT 'EU', play_time TEXT NOT NULL DEFAULT 'Вечером', play_style TEXT NOT NULL DEFAULT 'Любой', looking_for TEXT NOT NULL DEFAULT 'Напарника', user_id INTEGER UNIQUE);
        CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, game TEXT NOT NULL, description TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY, game TEXT NOT NULL, team_a TEXT NOT NULL, team_b TEXT NOT NULL, score_a INTEGER NOT NULL DEFAULT 0 CHECK(score_a>=0), score_b INTEGER NOT NULL DEFAULT 0 CHECK(score_b>=0), status TEXT NOT NULL DEFAULT 'Scheduled' CHECK(status IN ('Scheduled','Live','Completed')), scheduled_at TEXT NOT NULL);
        """)
        player_columns = {row[1] for row in c.execute("PRAGMA table_info(players)").fetchall()}
        for column, definition in [
            ("region", "TEXT NOT NULL DEFAULT 'EU'"),
            ("play_time", "TEXT NOT NULL DEFAULT 'Вечером'"),
            ("play_style", "TEXT NOT NULL DEFAULT 'Любой'"),
            ("looking_for", "TEXT NOT NULL DEFAULT 'Напарника'"),
            ("user_id", "INTEGER"),
        ]:
            if column not in player_columns:
                c.execute(f"ALTER TABLE players ADD COLUMN {column} {definition}")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            nickname TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lfg_posts(
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            game TEXT NOT NULL,
            post_type TEXT NOT NULL CHECK(post_type IN ('duo','team','stack')),
            rank TEXT NOT NULL DEFAULT 'Любой',
            region TEXT NOT NULL DEFAULT 'EU',
            platform TEXT NOT NULL DEFAULT 'PC',
            language TEXT NOT NULL DEFAULT 'Русский',
            play_time TEXT NOT NULL DEFAULT 'Вечером',
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        user_columns = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if "is_blocked" not in user_columns:
            c.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
        # Seed demo content on a new database only when explicitly enabled.
        # This supports fresh PostgreSQL setup without importing old SQLite data.
        if not USE_POSTGRES or os.getenv("SEED_DEMO_DATA", "").strip().lower() == "true":
            # Seed demo content only when each table is empty; never overwrite existing records.
            names = [
              ("Aveli","CS2","Gold Nova",42),("v1exa","Valorant","Diamond",67),("Ch1ksa","CS2","Master Guardian",31),("pixelfox","Apex Legends","Platinum",54),
              ("Nexa","CS2","Legendary Eagle",29),("LunaByte","Valorant","Ascendant",51),("RiftWalker","Apex Legends","Diamond",36),("NovaRush","CS2","Gold Nova",18),
              ("Kira.exe","Valorant","Platinum",24),("ZeroPing","CS2","Master Guardian",47),("MiraFox","Dota 2","Ancient",33),("Hexa","CS2","Silver Elite",12),
              ("NyxWave","Valorant","Immortal",73),("Frosty","Apex Legends","Gold",21),("EchoAim","CS2","Supreme",61),("PixelStorm","Dota 2","Divine",45),
              ("RavenQ","CS2","Gold Nova",16),("Vanta","Valorant","Diamond",39),("LimeCat","Apex Legends","Platinum",27),("GhostTap","CS2","Master Guardian",44),
              ("ArcticFox","Valorant","Ascendant",57),("K0met","CS2","Silver Elite",9),("MochiAim","Apex Legends","Gold",19),("Drift","Dota 2","Legend",28),
              ("ByteMe","CS2","Legendary Eagle",52),("SovaMain","Valorant","Platinum",26),("KarmaFPS","CS2","Gold Nova",22),("Orbit","Apex Legends","Diamond",41),
              ("ToxicTea","Valorant","Gold",14),("ClutchQueen","CS2","Master Guardian",49),
              ("WarVixen","WarDogs","Veteran",38),("Ch1ksa_WD","WarDogs","Elite",52),("AveliFox","WarDogs","Veteran",44),
              ("V1perWD","WarDogs","Elite",61),("NoxByte","WarDogs","Rookie",17),("RogueMira","WarDogs","Veteran",33),
              ("KiraStrike","WarDogs","Elite",48),("FoxUnit","WarDogs","Veteran",29),("NightK0met","WarDogs","Rookie",12),
              ("RavenOps","WarDogs","Elite",57),("PixelRaider","WarDogs","Veteran",35),("VexaCore","WarDogs","Elite",46),
              ("GhostSquad","WarDogs","Veteran",31),("LunaTrigger","WarDogs","Rookie",14),("ZeroRecoil","WarDogs","Elite",63),
              ("MochiTactical","WarDogs","Veteran",26),("FrostUnit","WarDogs","Rookie",19),("OrbitDog","WarDogs","Elite",41),
              ("NexaWolf","WarDogs","Veteran",37),("ClutchFox","WarDogs","Elite",55),("DustViper","WarDogs","Rookie",21),
              ("VantaOps","WarDogs","Veteran",32),("EchoRanger","WarDogs","Elite",49),("ArcticUnit","WarDogs","Veteran",28),
              ("ByteHunter","WarDogs","Elite",43),("KarmaWolf","WarDogs","Rookie",16),("SovaTactical","WarDogs","Veteran",34),
              ("NightPixel","WarDogs","Elite",58),("RiftRunner","WarDogs","Veteran",25),("NovaStrike","WarDogs","Rookie",11),
              ("ToxicRanger","WarDogs","Veteran",30),("LimeOps","WarDogs","Elite",47),("DriftWolf","WarDogs","Veteran",23)
            ]
            if c.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0:
                c.executemany("INSERT INTO players(nickname,game,rank,wins) VALUES(?,?,?,?)", names)
            if c.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0:
                c.executemany("INSERT INTO teams(name,game,description) VALUES(?,?,?)", [
                  ("Night Owls","CS2","Late-night ranked squad. Teamwork first."),
                  ("Pixel Rebels","Valorant","Competitive and always improving."),
                  ("Critical Five","CS2","Looking for focused players and good comms."),
                  ("WarDogs Alpha","WarDogs","Тактический состав WarDogs. Ищем активных игроков."),
                  ("WarDogs Wolves","WarDogs","Команда для совместных матчей и тренировок."),
                  ("WarDogs Night Raid","WarDogs","Собираем сыгранный состав для вечерних игр.")])
            if c.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 0:
                c.executemany("INSERT INTO matches(game,team_a,team_b,score_a,score_b,status,scheduled_at) VALUES(?,?,?,?,?,?,?)",[
                  ("CS2","Night Owls","Critical Five",0,0,"Scheduled","2026-10-15 19:00"),
                  ("Valorant","Pixel Rebels","Radiant Core",13,9,"Completed","2026-10-10 18:30"),
                  ("CS2","Critical Five","Dust Devils",0,0,"Live","2026-10-12 20:00")])
            if c.execute("SELECT COUNT(*) FROM matches WHERE game='WarDogs'").fetchone()[0] == 0:
                c.executemany("INSERT INTO matches(game,team_a,team_b,score_a,score_b,status,scheduled_at) VALUES(?,?,?,?,?,?,?)",[
                  ("WarDogs","WarDogs Alpha","WarDogs Wolves",0,0,"Scheduled","2026-10-17 19:00"),
                  ("WarDogs","WarDogs Night Raid","WarDogs Alpha",0,0,"Scheduled","2026-10-18 20:00")])
    
# Ensure database schema exists before serving requests.
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app=FastAPI(title="GameHub API", version="1.0.0", description="Educational gaming community app for QA portfolio")
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
@app.get("/",include_in_schema=False)
def home(): return FileResponse(BASE/"static"/"index.html")

@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(BASE / "static" / "sw.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})

class PlayerIn(BaseModel):
    nickname: str = Field(min_length=3,max_length=20,pattern=r"^[A-Za-z0-9_]+$")
    game: str = Field(min_length=2,max_length=40)
    rank: str = Field(default="Unranked",max_length=30)
    region: str = Field(default="EU", max_length=20)
    play_time: str = Field(default="Вечером", max_length=30)
    play_style: str = Field(default="Любой", max_length=30)
    looking_for: str = Field(default="Напарника", max_length=30)

class TeamIn(BaseModel):
    name: str = Field(min_length=3,max_length=40)
    game: str = Field(min_length=2,max_length=40)
    description: str = Field(default="",max_length=240)

class MatchIn(BaseModel):
    game: str = Field(min_length=2,max_length=40)
    team_a: str = Field(min_length=2,max_length=40)
    team_b: str = Field(min_length=2,max_length=40)
    scheduled_at: str = Field(min_length=10,max_length=30)

class MatchPatch(BaseModel):
    status: Optional[str] = None
    score_a: Optional[int] = Field(default=None,ge=0,le=999)
    score_b: Optional[int] = Field(default=None,ge=0,le=999)

@app.get("/api/health")
def health(): return {"status":"ok","service":"GameHub API"}

@app.get("/api/players")
def players(q: Optional[str]=None,game: Optional[str]=None):
    sql="SELECT * FROM players WHERE 1=1"; args=[]
    if q: sql+=" AND nickname LIKE ?"; args.append("%"+q+"%")
    if game: sql+=" AND game=?"; args.append(game)
    sql+=" ORDER BY wins DESC,nickname ASC"
    with db() as c: return [dict(x) for x in c.execute(sql,args).fetchall()]

@app.post("/api/players",status_code=201)
def create_player(p: PlayerIn):
    with db() as c:
        try:
            cur=c.execute("INSERT INTO players(nickname,game,rank,region,play_time,play_style,looking_for) VALUES(?,?,?,?,?,?,?)",(p.nickname,p.game.strip(),p.rank.strip(),p.region,p.play_time,p.play_style,p.looking_for))
            return dict(c.execute("SELECT * FROM players WHERE id=?",(cur.lastrowid,)).fetchone())
        except Exception as exc:
            if not is_integrity_error(exc):
                raise
            raise HTTPException(status_code=409,detail="Nickname already exists")

@app.get("/api/teams")
def teams(game: Optional[str]=None):
    with db() as c:
        rows=c.execute("SELECT * FROM teams"+(" WHERE game=?" if game else "")+" ORDER BY name",([game] if game else [])).fetchall()
        return [dict(x) for x in rows]

@app.post("/api/teams",status_code=201)
def create_team(p: TeamIn):
    with db() as c:
        try:
            cur=c.execute("INSERT INTO teams(name,game,description) VALUES(?,?,?)",(p.name.strip(),p.game.strip(),p.description.strip()))
            return dict(c.execute("SELECT * FROM teams WHERE id=?",(cur.lastrowid,)).fetchone())
        except Exception as exc:
            if not is_integrity_error(exc):
                raise
            raise HTTPException(status_code=409,detail="Team name already exists")

@app.get("/api/matches")
def matches(status: Optional[str]=None,game: Optional[str]=None):
    sql="SELECT * FROM matches WHERE 1=1"; args=[]
    if status: sql+=" AND status=?"; args.append(status)
    if game: sql+=" AND game=?"; args.append(game)
    sql+=" ORDER BY scheduled_at DESC"
    with db() as c: return [dict(x) for x in c.execute(sql,args).fetchall()]

@app.post("/api/matches",status_code=201)
def create_match(p: MatchIn):
    if p.team_a.strip().casefold()==p.team_b.strip().casefold():
        raise HTTPException(status_code=422,detail="A team cannot play against itself")
    with db() as c:
        cur=c.execute("INSERT INTO matches(game,team_a,team_b,scheduled_at) VALUES(?,?,?,?)",(p.game.strip(),p.team_a.strip(),p.team_b.strip(),p.scheduled_at.strip()))
        return dict(c.execute("SELECT * FROM matches WHERE id=?",(cur.lastrowid,)).fetchone())

@app.patch("/api/matches/{match_id}")
def patch_match(match_id:int,p:MatchPatch):
    if p.status is not None and p.status not in {"Scheduled","Live","Completed"}:
        raise HTTPException(status_code=422,detail="Invalid match status")
    fields=[]; vals=[]
    if p.status is not None: fields.append("status=?"); vals.append(p.status)
    if p.score_a is not None: fields.append("score_a=?"); vals.append(p.score_a)
    if p.score_b is not None: fields.append("score_b=?"); vals.append(p.score_b)
    if not fields: raise HTTPException(status_code=422,detail="At least one field is required")
    with db() as c:
        if not c.execute("SELECT id FROM matches WHERE id=?",(match_id,)).fetchone(): raise HTTPException(status_code=404,detail="Match not found")
        vals.append(match_id); c.execute("UPDATE matches SET "+",".join(fields)+" WHERE id=?",vals)
        return dict(c.execute("SELECT * FROM matches WHERE id=?",(match_id,)).fetchone())


# Admin API. Set ADMIN_PASSWORD in Render Environment before using /admin.
def check_admin(request: Request):
    expected = os.getenv("ADMIN_PASSWORD", "")
    supplied = request.headers.get("X-Admin-Password", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Администратор не настроен: добавьте ADMIN_PASSWORD в Render Environment")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Неверный пароль администратора")

class AdminPlayerPatch(BaseModel):
    nickname: Optional[str] = Field(default=None, min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")
    game: Optional[str] = Field(default=None, min_length=2, max_length=40)
    rank: Optional[str] = Field(default=None, max_length=30)
    wins: Optional[int] = Field(default=None, ge=0, le=999999)
    region: Optional[str] = Field(default=None, max_length=20)
    play_time: Optional[str] = Field(default=None, max_length=30)
    play_style: Optional[str] = Field(default=None, max_length=30)
    looking_for: Optional[str] = Field(default=None, max_length=30)

class AdminUserPatch(BaseModel):
    nickname: Optional[str] = Field(default=None, min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")
    password: Optional[str] = Field(default=None, min_length=10, max_length=128)
    is_blocked: Optional[bool] = None

class AdminTeamPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=40)
    game: Optional[str] = Field(default=None, min_length=2, max_length=40)
    description: Optional[str] = Field(default=None, max_length=240)

class AdminMatchPatch(BaseModel):
    game: Optional[str] = Field(default=None, min_length=2, max_length=40)
    team_a: Optional[str] = Field(default=None, min_length=2, max_length=40)
    team_b: Optional[str] = Field(default=None, min_length=2, max_length=40)
    score_a: Optional[int] = Field(default=None, ge=0, le=999)
    score_b: Optional[int] = Field(default=None, ge=0, le=999)
    status: Optional[str] = None
    scheduled_at: Optional[str] = Field(default=None, min_length=10, max_length=30)

@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(BASE / "static" / "admin.html")

@app.get("/api/admin/summary")
def admin_summary(request: Request):
    check_admin(request)
    with db() as c:
        return {
            "players": c.execute("SELECT COUNT(*) FROM players").fetchone()[0],
            "teams": c.execute("SELECT COUNT(*) FROM teams").fetchone()[0],
            "matches": c.execute("SELECT COUNT(*) FROM matches").fetchone()[0],
            "warDogsPlayers": c.execute("SELECT COUNT(*) FROM players WHERE game='WarDogs'").fetchone()[0],
        }

@app.post("/api/admin/players", status_code=201)
def admin_create_player(p: PlayerIn, request: Request):
    check_admin(request)
    with db() as c:
        try:
            cur = c.execute("""INSERT INTO players(nickname,game,rank,region,play_time,play_style,looking_for)
                               VALUES(?,?,?,?,?,?,?)""",
                            (p.nickname,p.game.strip(),p.rank.strip(),p.region,p.play_time,p.play_style,p.looking_for))
            return dict(c.execute("SELECT * FROM players WHERE id=?", (cur.lastrowid,)).fetchone())
        except Exception as exc:
            if not is_integrity_error(exc):
                raise
            raise HTTPException(status_code=409, detail="Никнейм уже существует")

@app.patch("/api/admin/players/{player_id}")
def admin_update_player(player_id: int, p: AdminPlayerPatch, request: Request):
    check_admin(request)
    fields, vals = [], []
    if p.rank is not None:
        fields.append("rank=?"); vals.append(p.rank.strip())
    if p.wins is not None:
        fields.append("wins=?"); vals.append(p.wins)
    if not fields:
        raise HTTPException(status_code=422, detail="Укажи ранг или количество побед")
    with db() as c:
        if not c.execute("SELECT id FROM players WHERE id=?", (player_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Игрок не найден")
        vals.append(player_id)
        c.execute("UPDATE players SET " + ",".join(fields) + " WHERE id=?", vals)
        return dict(c.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

@app.delete("/api/admin/players/{player_id}")
def admin_delete_player(player_id: int, request: Request):
    check_admin(request)
    with db() as c:
        cur = c.execute("DELETE FROM players WHERE id=?", (player_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Игрок не найден")
    return {"ok": True}

@app.post("/api/admin/teams", status_code=201)
def admin_create_team(p: TeamIn, request: Request):
    check_admin(request)
    with db() as c:
        try:
            cur = c.execute("INSERT INTO teams(name,game,description) VALUES(?,?,?)", (p.name.strip(), p.game.strip(), p.description.strip()))
            return dict(c.execute("SELECT * FROM teams WHERE id=?", (cur.lastrowid,)).fetchone())
        except Exception as exc:
            if not is_integrity_error(exc):
                raise
            raise HTTPException(status_code=409, detail="Команда с таким названием уже существует")

@app.delete("/api/admin/teams/{team_id}")
def admin_delete_team(team_id: int, request: Request):
    check_admin(request)
    with db() as c:
        cur = c.execute("DELETE FROM teams WHERE id=?", (team_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Команда не найдена")
    return {"ok": True}

@app.post("/api/admin/matches", status_code=201)
def admin_create_match(p: MatchIn, request: Request):
    check_admin(request)
    if p.team_a.strip().casefold() == p.team_b.strip().casefold():
        raise HTTPException(status_code=422, detail="Команда не может играть сама с собой")
    with db() as c:
        cur = c.execute("INSERT INTO matches(game,team_a,team_b,scheduled_at) VALUES(?,?,?,?)", (p.game.strip(), p.team_a.strip(), p.team_b.strip(), p.scheduled_at.strip()))
        return dict(c.execute("SELECT * FROM matches WHERE id=?", (cur.lastrowid,)).fetchone())

@app.patch("/api/admin/matches/{match_id}")
def admin_update_match(match_id: int, p: MatchPatch, request: Request):
    check_admin(request)
    if p.status is not None and p.status not in {"Scheduled", "Live", "Completed"}:
        raise HTTPException(status_code=422, detail="Некорректный статус матча")
    fields, vals = [], []
    if p.status is not None:
        fields.append("status=?"); vals.append(p.status)
    if p.score_a is not None:
        fields.append("score_a=?"); vals.append(p.score_a)
    if p.score_b is not None:
        fields.append("score_b=?"); vals.append(p.score_b)
    if not fields:
        raise HTTPException(status_code=422, detail="Нет полей для обновления")
    with db() as c:
        if not c.execute("SELECT id FROM matches WHERE id=?", (match_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Матч не найден")
        vals.append(match_id)
        c.execute("UPDATE matches SET " + ",".join(fields) + " WHERE id=?", vals)
        return dict(c.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone())

@app.delete("/api/admin/matches/{match_id}")
def admin_delete_match(match_id: int, request: Request):
    check_admin(request)
    with db() as c:
        cur = c.execute("DELETE FROM matches WHERE id=?", (match_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Матч не найден")
    return {"ok": True}


# CMS: editable site content, sections, appearance and media.
class CMSSectionIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    kind: str = Field(default="content", max_length=40, pattern=r"^(hero|content|cards|players|teams|matches|gallery|custom)$")
    body: str = Field(default="", max_length=20000)
    image_url: str = Field(default="", max_length=2000000)
    visible: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

class CMSSectionPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    kind: Optional[str] = Field(default=None, max_length=40, pattern=r"^(hero|content|cards|players|teams|matches|gallery|custom)$")
    body: Optional[str] = Field(default=None, max_length=20000)
    image_url: Optional[str] = Field(default=None, max_length=2000000)
    visible: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0, le=10000)

class CMSSettingIn(BaseModel):
    value: str = Field(max_length=2100000)

CMS_PUBLIC_SETTING_KEYS = {
    "site_title", "logo_text", "meta_description",
    "menu_players", "menu_teams", "menu_matches", "menu_lfg",
    "primary_color", "background_color",
    "game_cs2_image", "game_valorant_image", "game_wd_image", "game_apex_image",
}

def init_cms_tables():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS cms_sections(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
          kind TEXT NOT NULL DEFAULT 'content', body TEXT NOT NULL DEFAULT '',
          image_url TEXT NOT NULL DEFAULT '', visible INTEGER NOT NULL DEFAULT 1,
          sort_order INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS cms_settings(
          key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        if c.execute("SELECT COUNT(*) FROM cms_sections").fetchone()[0] == 0:
            c.executemany("INSERT INTO cms_sections(title,slug,kind,body,visible,sort_order) VALUES(?,?,?,?,?,?)", [
              ("Найди свою команду. Играй на своём уровне.","hero","hero","Игроки, команды и матчи — в одном месте.",1,10),
              ("Игры","games","cards","Выбирай игру и находи своё сообщество.",1,20),
              ("Игроки","players","players","Игровое сообщество GameHub",1,30),
              ("Команды","teams","teams","Собирай состав и играй вместе.",1,40),
              ("Матчи","matches","matches","Следи за игровыми матчами.",1,50)
            ])
        for key,value in [("site_title","GameHub"),("logo_text","gamehub"),("primary_color","#c3ff68"),("background_color","#080b12"),("meta_description","Находи напарников, собирай команды и следи за игровыми матчами в GameHub."),
            ("game_cs2_image",""),("game_valorant_image",""),("game_wd_image",""),("game_apex_image","")]:
            c.execute("INSERT OR IGNORE INTO cms_settings(key,value) VALUES(?,?)",(key,value))

init_cms_tables()

@app.get("/admin/cms", include_in_schema=False)
def cms_admin_page():
    return FileResponse(BASE / "static" / "cms.html")

@app.get("/api/admin/cms/sections")
def cms_sections(request: Request):
    check_admin(request)
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM cms_sections ORDER BY sort_order,id").fetchall()]

@app.post("/api/admin/cms/sections", status_code=201)
def cms_create_section(p: CMSSectionIn, request: Request):
    check_admin(request)
    with db() as c:
        try:
            cur=c.execute("INSERT INTO cms_sections(title,slug,kind,body,image_url,visible,sort_order) VALUES(?,?,?,?,?,?,?)",
              (p.title.strip(),p.slug,p.kind,p.body,p.image_url,1 if p.visible else 0,p.sort_order))
        except Exception as exc:
            if is_integrity_error(exc): raise HTTPException(status_code=409,detail="Раздел с таким адресным именем уже существует")
            raise
        return dict(c.execute("SELECT * FROM cms_sections WHERE id=?",(cur.lastrowid,)).fetchone())

@app.patch("/api/admin/cms/sections/{section_id}")
def cms_update_section(section_id: int, p: CMSSectionPatch, request: Request):
    check_admin(request)
    values=p.model_dump(exclude_unset=True)
    if not values: raise HTTPException(status_code=422,detail="Нет изменений")
    if "visible" in values: values["visible"]=1 if values["visible"] else 0
    with db() as c:
        if not c.execute("SELECT id FROM cms_sections WHERE id=?",(section_id,)).fetchone():
            raise HTTPException(status_code=404,detail="Раздел не найден")
        try:
            values["updated_at"]="CURRENT_TIMESTAMP"
            fields=[]; args=[]
            for k,v in values.items():
                if k=="updated_at": fields.append("updated_at=CURRENT_TIMESTAMP")
                else: fields.append(k+"=?"); args.append(v.strip() if isinstance(v,str) else v)
            args.append(section_id)
            c.execute("UPDATE cms_sections SET "+",".join(fields)+" WHERE id=?",args)
        except Exception as exc:
            if is_integrity_error(exc): raise HTTPException(status_code=409,detail="Адресное имя уже занято")
            raise
        return dict(c.execute("SELECT * FROM cms_sections WHERE id=?",(section_id,)).fetchone())

@app.delete("/api/admin/cms/sections/{section_id}")
def cms_delete_section(section_id: int, request: Request):
    check_admin(request)
    with db() as c:
        cur=c.execute("DELETE FROM cms_sections WHERE id=?",(section_id,))
        if cur.rowcount==0: raise HTTPException(status_code=404,detail="Раздел не найден")
    return {"ok":True}

@app.get("/api/admin/cms/settings")
def cms_get_settings(request: Request):
    check_admin(request)
    with db() as c: return {r["key"]:r["value"] for r in c.execute("SELECT key,value FROM cms_settings").fetchall()}

@app.put("/api/admin/cms/settings/{key}")
def cms_set_setting(key: str, p: CMSSettingIn, request: Request):
    check_admin(request)
    if key not in CMS_PUBLIC_SETTING_KEYS:
        raise HTTPException(status_code=422,detail="Неизвестный ключ настройки")
    if key.endswith("_color") and not __import__("re").fullmatch(r"#[0-9a-fA-F]{6}", p.value):
        raise HTTPException(status_code=422,detail="Цвет должен быть в формате HEX, например #c3ff68")
    with db() as c:
        c.execute("INSERT INTO cms_settings(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP",(key,p.value))
    return {"key":key,"value":p.value}

@app.get("/api/cms/content")
def cms_public_content():
    with db() as c:
        sections=[dict(r) for r in c.execute("""SELECT id,CASE WHEN visible=1 THEN title ELSE '' END AS title,slug,kind,CASE WHEN visible=1 THEN body ELSE '' END AS body,CASE WHEN visible=1 THEN image_url ELSE '' END AS image_url,visible,sort_order FROM cms_sections ORDER BY sort_order,id""").fetchall()]
        settings={r["key"]:r["value"] for r in c.execute(
            "SELECT key,value FROM cms_settings WHERE key IN (" + ",".join("?" for _ in CMS_PUBLIC_SETTING_KEYS) + ")",
            tuple(sorted(CMS_PUBLIC_SETTING_KEYS))).fetchall()}
    return {"sections":sections,"settings":settings}


# Player accounts: passwords are hashed and sessions are opaque, expiring tokens.
SESSION_DAYS = 30

def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
    return salt.hex() + ":" + digest.hex()

def password_matches(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 310000).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False

def issue_session(user_id: int, request: Request, response):
    token = secrets.token_urlsafe(32)
    with db() as c:
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        c.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                  (hashlib.sha256(token.encode()).hexdigest(), user_id, int(time.time()) + SESSION_DAYS * 86400))
    response.set_cookie("gh_session", token, httponly=True, secure=request.url.scheme == "https",
                        samesite="lax", max_age=SESSION_DAYS * 86400, path="/")

def current_user(request: Request):
    token = request.cookies.get("gh_session", "")
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db() as c:
        row = c.execute("""SELECT u.id,u.nickname,u.created_at,u.is_blocked,p.id AS player_id,p.game,p.rank,p.wins,
                           p.region,p.play_time,p.play_style,p.looking_for
                           FROM sessions s JOIN users u ON u.id=s.user_id
                           LEFT JOIN players p ON p.user_id=u.id
                           WHERE s.token_hash=? AND s.expires_at>? AND u.is_blocked=0""", (token_hash, int(time.time()))).fetchone()
        return dict(row) if row else None

class RegisterIn(BaseModel):
    nickname: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)
    game: str = Field(default="CS2", min_length=2, max_length=40)
    rank: str = Field(default="Unranked", max_length=30)
    region: str = Field(default="EU", max_length=20)
    play_time: str = Field(default="Вечером", max_length=30)
    play_style: str = Field(default="Любой", max_length=30)
    looking_for: str = Field(default="Напарника", max_length=30)

class LoginIn(BaseModel):
    nickname: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=1, max_length=128)

class ProfilePatch(BaseModel):
    game: Optional[str] = Field(default=None, min_length=2, max_length=40)
    rank: Optional[str] = Field(default=None, max_length=30)
    region: Optional[str] = Field(default=None, max_length=20)
    play_time: Optional[str] = Field(default=None, max_length=30)
    play_style: Optional[str] = Field(default=None, max_length=30)
    looking_for: Optional[str] = Field(default=None, max_length=30)

@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(BASE / "static" / "account.html")

@app.get("/account", include_in_schema=False)
def account_page():
    return FileResponse(BASE / "static" / "account.html")

@app.post("/api/auth/register", status_code=201)
def register_account(p: RegisterIn, request: Request):
    nickname = p.nickname.strip()
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE lower(nickname)=lower(?)", (nickname,)).fetchone():
            raise HTTPException(status_code=409, detail="Этот никнейм уже зарегистрирован")
        if c.execute("SELECT 1 FROM players WHERE lower(nickname)=lower(?)", (nickname,)).fetchone():
            raise HTTPException(status_code=409, detail="Никнейм уже занят в GameHub")
        try:
            cur = c.execute("INSERT INTO users(nickname,password_hash) VALUES(?,?)", (nickname, password_hash(p.password)))
            user_id = cur.lastrowid
            c.execute("""INSERT INTO players(nickname,game,rank,region,play_time,play_style,looking_for,user_id)
                         VALUES(?,?,?,?,?,?,?,?)""",
                      (nickname,p.game.strip(),p.rank.strip(),p.region,p.play_time,p.play_style,p.looking_for,user_id))
        except Exception as exc:
            if not is_integrity_error(exc):
                raise
            raise HTTPException(status_code=409, detail="Не удалось создать аккаунт: проверь никнейм")
    from fastapi.responses import JSONResponse
    response = JSONResponse({"ok": True, "nickname": nickname})
    issue_session(user_id, request, response)
    return response

@app.post("/api/auth/login")
def login_account(p: LoginIn, request: Request):
    with db() as c:
        user = c.execute("SELECT id,nickname,password_hash,is_blocked FROM users WHERE lower(nickname)=lower(?)", (p.nickname.strip(),)).fetchone()
    if not user or user["is_blocked"] or not password_matches(p.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный никнейм или пароль")
    from fastapi.responses import JSONResponse
    response = JSONResponse({"ok": True, "nickname": user["nickname"]})
    issue_session(user["id"], request, response)
    return response

@app.post("/api/auth/logout")
def logout_account(request: Request):
    token = request.cookies.get("gh_session", "")
    if token:
        with db() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
    from fastapi.responses import JSONResponse
    response = JSONResponse({"ok": True})
    response.delete_cookie("gh_session", path="/")
    return response

@app.get("/api/auth/me")
def auth_me(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт")
    return user

@app.patch("/api/auth/profile")
def update_my_profile(p: ProfilePatch, request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт")
    values = p.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="Нет изменений")
    if not user.get("player_id"):
        raise HTTPException(status_code=404, detail="Игровой профиль не найден")
    with db() as c:
        c.execute("UPDATE players SET " + ",".join(f"{key}=?" for key in values) + " WHERE user_id=?",
                  [v.strip() if isinstance(v,str) else v for v in values.values()] + [user["id"]])
    return current_user(request)


class LFGPostIn(BaseModel):
    game: str = Field(min_length=2, max_length=40)
    post_type: str = Field(default="duo", pattern=r"^(duo|team|stack)$")
    rank: str = Field(default="Любой", max_length=30)
    region: str = Field(default="EU", max_length=20)
    platform: str = Field(default="PC", max_length=20)
    language: str = Field(default="Русский", max_length=30)
    play_time: str = Field(default="Вечером", max_length=30)
    description: str = Field(default="", max_length=300)

class LFGStatusPatch(BaseModel):
    status: str = Field(pattern=r"^(open|closed)$")

@app.get("/api/lfg")
def list_lfg(game: Optional[str]=None, rank: Optional[str]=None, region: Optional[str]=None, platform: Optional[str]=None, language: Optional[str]=None, status: str="open"):
    sql = """SELECT l.id,l.user_id,u.nickname,l.game,l.post_type,l.rank,l.region,l.platform,l.language,l.play_time,l.description,l.status,l.created_at
             FROM lfg_posts l JOIN users u ON u.id=l.user_id WHERE 1=1"""
    args = []
    for field, value in (("game",game),("rank",rank),("region",region),("platform",platform),("language",language),("status",status)):
        if value:
            sql += f" AND l.{field}=?"
            args.append(value)
    sql += " ORDER BY l.created_at DESC,l.id DESC LIMIT 100"
    with db() as c:
        return [dict(row) for row in c.execute(sql,args).fetchall()]

@app.post("/api/lfg", status_code=201)
def create_lfg(p: LFGPostIn, request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт, чтобы создать объявление")
    with db() as c:
        cur = c.execute("""INSERT INTO lfg_posts(user_id,game,post_type,rank,region,platform,language,play_time,description)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (user["id"],p.game.strip(),p.post_type,p.rank.strip(),p.region,p.platform,p.language,p.play_time,p.description.strip()))
        row = c.execute("""SELECT l.id,l.user_id,u.nickname,l.game,l.post_type,l.rank,l.region,l.platform,l.language,l.play_time,l.description,l.status,l.created_at
                           FROM lfg_posts l JOIN users u ON u.id=l.user_id WHERE l.id=?""",(cur.lastrowid,)).fetchone()
        return dict(row)

@app.patch("/api/lfg/{post_id}")
def update_lfg(post_id: int, p: LFGStatusPatch, request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Войди в аккаунт")
    with db() as c:
        post = c.execute("SELECT id,user_id FROM lfg_posts WHERE id=?",(post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Объявление не найдено")
        if post["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Можно изменять только свои объявления")
        c.execute("UPDATE lfg_posts SET status=? WHERE id=?",(p.status,post_id))
        return dict(c.execute("SELECT id,status FROM lfg_posts WHERE id=?",(post_id,)).fetchone())


@app.get("/api/admin/users")
def admin_users(request: Request):
    check_admin(request)
    with db() as c:
        rows = c.execute("""SELECT u.id,u.nickname,u.is_blocked,u.created_at,
                            p.id AS player_id,p.game,p.rank,p.wins,p.region,p.play_time,p.play_style,p.looking_for
                            FROM users u LEFT JOIN players p ON p.user_id=u.id ORDER BY u.id DESC""").fetchall()
        return [dict(row) for row in rows]

@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, p: AdminUserPatch, request: Request):
    check_admin(request)
    values = p.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="Нет изменений")
    with db() as c:
        user = c.execute("SELECT id,nickname FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")
        if "nickname" in values:
            new_nick = values.pop("nickname").strip()
            if c.execute("SELECT 1 FROM users WHERE lower(nickname)=lower(?) AND id<>?", (new_nick,user_id)).fetchone():
                raise HTTPException(status_code=409, detail="Никнейм уже занят")
            c.execute("UPDATE users SET nickname=? WHERE id=?", (new_nick,user_id))
            c.execute("UPDATE players SET nickname=? WHERE user_id=?", (new_nick,user_id))
        if "password" in values:
            new_password = values.pop("password")
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash(new_password),user_id))
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        if "is_blocked" in values:
            blocked = 1 if values.pop("is_blocked") else 0
            c.execute("UPDATE users SET is_blocked=? WHERE id=?", (blocked,user_id))
            if blocked:
                c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        return dict(c.execute("SELECT id,nickname,is_blocked,created_at FROM users WHERE id=?", (user_id,)).fetchone())

@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request):
    check_admin(request)
    with db() as c:
        user = c.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")
        c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM players WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"ok": True}

@app.patch("/api/admin/teams/{team_id}")
def admin_update_team(team_id: int, p: AdminTeamPatch, request: Request):
    check_admin(request)
    values = p.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="Нет изменений")
    with db() as c:
        if not c.execute("SELECT id FROM teams WHERE id=?", (team_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Команда не найдена")
        try:
            c.execute("UPDATE teams SET "+",".join(f"{key}=?" for key in values)+" WHERE id=?", [v.strip() if isinstance(v,str) else v for v in values.values()]+[team_id])
        except Exception as exc:
            if not is_integrity_error(exc):
                raise
            raise HTTPException(status_code=409, detail="Название команды уже занято")
        return dict(c.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone())

@app.patch("/api/admin/matches/{match_id}/full")
def admin_update_match_full(match_id: int, p: AdminMatchPatch, request: Request):
    check_admin(request)
    values = p.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="Нет изменений")
    if values.get("status") is not None and values["status"] not in {"Scheduled","Live","Completed"}:
        raise HTTPException(status_code=422, detail="Некорректный статус матча")
    if values.get("team_a") and values.get("team_b") and values["team_a"].strip().casefold()==values["team_b"].strip().casefold():
        raise HTTPException(status_code=422, detail="Команда не может играть сама с собой")
    with db() as c:
        if not c.execute("SELECT id FROM matches WHERE id=?", (match_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Матч не найден")
        c.execute("UPDATE matches SET "+",".join(f"{key}=?" for key in values)+" WHERE id=?", [v.strip() if isinstance(v,str) else v for v in values.values()]+[match_id])
        return dict(c.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone())
