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
DB_PATH = Path(os.getenv("GAMEHUB_DB", BASE / "gamehub.db"))

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY, nickname TEXT UNIQUE NOT NULL, game TEXT NOT NULL, rank TEXT NOT NULL DEFAULT 'Unranked', wins INTEGER NOT NULL DEFAULT 0 CHECK(wins>=0), region TEXT NOT NULL DEFAULT 'EU', play_time TEXT NOT NULL DEFAULT 'Вечером', play_style TEXT NOT NULL DEFAULT 'Любой', looking_for TEXT NOT NULL DEFAULT 'Напарника', user_id INTEGER UNIQUE);
        CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, game TEXT NOT NULL, description TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY, game TEXT NOT NULL, team_a TEXT NOT NULL, team_b TEXT NOT NULL, score_a INTEGER NOT NULL DEFAULT 0 CHECK(score_a>=0), score_b INTEGER NOT NULL DEFAULT 0 CHECK(score_b>=0), status TEXT NOT NULL DEFAULT 'Scheduled' CHECK(status IN ('Scheduled','Live','Completed')), scheduled_at TEXT NOT NULL);
        """)
        # Safe migrations for databases created by older GameHub versions.
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
        """)
        user_columns = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if "is_blocked" not in user_columns:
            c.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
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
        c.executemany("INSERT OR IGNORE INTO players(nickname,game,rank,wins) VALUES(?,?,?,?)", names)
        c.executemany("INSERT OR IGNORE INTO teams(name,game,description) VALUES(?,?,?)", [
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
        except sqlite3.IntegrityError:
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
        except sqlite3.IntegrityError: raise HTTPException(status_code=409,detail="Team name already exists")

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
        except sqlite3.IntegrityError:
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
        except sqlite3.IntegrityError:
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
        except sqlite3.IntegrityError:
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
        except sqlite3.IntegrityError:
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
