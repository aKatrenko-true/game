from contextlib import asynccontextmanager
from pathlib import Path
import os, sqlite3
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
        CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY, nickname TEXT UNIQUE NOT NULL, game TEXT NOT NULL, rank TEXT NOT NULL DEFAULT 'Unranked', wins INTEGER NOT NULL DEFAULT 0 CHECK(wins>=0));
        CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, game TEXT NOT NULL, description TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY, game TEXT NOT NULL, team_a TEXT NOT NULL, team_b TEXT NOT NULL, score_a INTEGER NOT NULL DEFAULT 0 CHECK(score_a>=0), score_b INTEGER NOT NULL DEFAULT 0 CHECK(score_b>=0), status TEXT NOT NULL DEFAULT 'Scheduled' CHECK(status IN ('Scheduled','Live','Completed')), scheduled_at TEXT NOT NULL);
        """)
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

class PlayerIn(BaseModel):
    nickname: str = Field(min_length=3,max_length=20,pattern=r"^[A-Za-z0-9_]+$")
    game: str = Field(min_length=2,max_length=40)
    rank: str = Field(default="Unranked",max_length=30)

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
            cur=c.execute("INSERT INTO players(nickname,game,rank) VALUES(?,?,?)",(p.nickname,p.game.strip(),p.rank.strip()))
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
    rank: Optional[str] = Field(default=None, max_length=30)
    wins: Optional[int] = Field(default=None, ge=0, le=999999)

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
