from fastapi.testclient import TestClient
import app as gamehub

def setup_function():
    gamehub.DB_PATH = gamehub.BASE / "test_gamehub.db"
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
