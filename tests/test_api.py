"""Run with: py -3 -m pytest -q (Windows) or python3 -m pytest -q (macOS/Linux)."""
import os, re, sys, tempfile, uuid
from werkzeug.security import check_password_hash
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["BROODER_DB"] = tempfile.mktemp(suffix=".db")
from webapp.app import app, db


def csrf(client, path="/app"):
    response = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert response.status_code == 200 and match
    return match.group(1)


def signed_in_client(username=None, password="correct horse battery"):
    client = app.test_client()
    username = username or f"user_{uuid.uuid4().hex[:12]}"
    response = client.post("/signup", data={
        "csrf_token": csrf(client, "/signup"),
        "username": username,
        "password": password,
    })
    assert response.status_code == 302
    return client, username, password


def api_post(client, path, data):
    return client.post(path, json=data, headers={"X-CSRF-Token": csrf(client)})


def api_delete(client, path):
    return client.delete(path, headers={"X-CSRF-Token": csrf(client)})


def test_authentication_and_private_runs():
    anonymous = app.test_client()
    landing = anonymous.get("/")
    assert landing.status_code == 200 and b"Create account" in landing.data
    assert b"brooder" in landing.data.lower()
    assert anonymous.get("/app").status_code == 302
    assert anonymous.get("/api/runs").status_code == 401
    assert anonymous.post("/api/simulate", json={}).status_code == 401

    with app.app_context():
        connection = db()
        legacy = connection.execute(
            "INSERT INTO runs(created,label,params,metrics,result) VALUES(?,?,?,?,?)",
            (0, "pre-account run", "{}", "{}", "{}"))
        legacy_id = legacy.lastrowid
        connection.commit()

    owner, username, password = signed_in_client()
    with app.app_context():
        password_hash = db().execute(
            "SELECT password_hash FROM users WHERE username=?", (username,)).fetchone()[0]
    assert password_hash != password and check_password_hash(password_hash, password)
    assert legacy_id in [r["id"] for r in owner.get("/api/runs").get_json()]
    duplicate = app.test_client()
    response = duplicate.post("/signup", data={
        "csrf_token": csrf(duplicate, "/signup"),
        "username": username.upper(),
        "password": password,
    })
    assert response.status_code == 200
    assert "already taken" in response.get_data(as_text=True)

    run = api_post(owner, "/api/simulate", {"label": "private"}).get_json()
    other, _, _ = signed_in_client()
    assert [r["id"] for r in other.get("/api/runs").get_json()] == []
    assert other.get(f"/api/runs/{run['id']}").status_code == 404
    assert api_delete(other, f"/api/runs/{run['id']}").status_code == 404
    assert owner.get(f"/api/runs/{run['id']}").status_code == 200
    assert api_delete(owner, f"/api/runs/{legacy_id}").status_code == 200
    assert owner.post("/api/simulate", json={}, headers={}).status_code == 400

    login_client = app.test_client()
    login_token = csrf(login_client, "/login")
    response = login_client.post("/login", data={
        "csrf_token": login_token,
        "username": username,
        "password": "incorrect password",
    })
    assert response.status_code == 200 and "Invalid username or password" in response.get_data(as_text=True)
    response = login_client.post("/login", data={
        "csrf_token": csrf(login_client, "/login"),
        "username": username.upper(),
        "password": password,
    })
    assert response.status_code == 302
    assert login_client.get("/app").status_code == 200

    response = login_client.post("/logout", data={"csrf_token": csrf(login_client)})
    assert response.status_code == 302 and login_client.get("/app").status_code == 302
    assert login_client.get("/").status_code == 200


def test_pages_and_validation():
    c, _, _ = signed_in_client()
    assert c.get("/").status_code == 200
    assert c.get("/app").status_code == 200
    assert api_post(c, "/api/simulate", ["not", "an", "object"]).status_code == 400
    r = api_post(c, "/api/simulate", {"R": -3, "h": "abc"})
    assert r.status_code == 400 and {"R", "h"} <= set(r.get_json()["errors"])
    assert api_post(c, "/api/simulate", {"h": 0.5, "duration_h": 48}).status_code == 400
    r = api_post(c, "/api/simulate", {"method": "bogus", "antiwindup": "false", "heater_fail_h": "abc"})
    assert r.status_code == 400 and {"method", "heater_fail_h"} <= set(r.get_json()["errors"])
    r = api_post(c, "/api/simulate", {"n_chicks": 1.5, "save": "sometimes"})
    assert r.status_code == 400 and {"n_chicks", "save"} <= set(r.get_json()["errors"])
    assert api_post(c, "/api/simulate", {"method": "RK4", "antiwindup": "false"}).status_code == 200


def test_simulation_ends_on_duration_and_heater_failure_time():
    c, _, _ = signed_in_client()
    d = api_post(c, "/api/simulate", {
        "duration_h": 0.5, "h": 7, "heater_fail_h": 0.013, "save": False
    }).get_json()
    ts = d["series"]["t"]
    assert abs(ts[-1] - 0.5) < 1e-12
    fail_index = next(i for i, t in enumerate(ts) if abs(t - 0.013) < 1e-12)
    assert d["series"]["P"][fail_index] == 0


def test_run_save_load_delete_and_metrics():
    c, _, _ = signed_in_client()
    before = len(c.get("/api/runs").get_json())
    unsaved = api_post(c, "/api/simulate", {"save": "false"}).get_json()
    assert "id" not in unsaved and len(c.get("/api/runs").get_json()) == before
    d = api_post(c, "/api/simulate", {"label": "t"}).get_json()
    m = d["metrics"]
    assert abs(m["recovery_min"] - 70) < 5 and abs(m["steady_state_error_K"]) < 0.01
    assert c.get(f"/api/runs/{d['id']}").status_code == 200
    assert api_delete(c, f"/api/runs/{d['id']}").status_code == 200
    assert api_delete(c, f"/api/runs/{d['id']}").status_code == 404
    assert c.get(f"/api/runs/{d['id']}").status_code == 404


def test_euler_instability_reported_and_rk4_fine():
    c, _, _ = signed_in_client()
    bad = api_post(c, "/api/simulate", {"method": "euler", "h": 130, "Kd": 3000, "duration_h": 4, "save": False}).get_json()
    ok = api_post(c, "/api/simulate", {"method": "rk4", "h": 130, "Kd": 3000, "duration_h": 4, "save": False}).get_json()
    assert bad["metrics"]["unstable"] and ok["metrics"]["unstable"] is None


if __name__ == "__main__":
    test_authentication_and_private_runs()
    test_pages_and_validation()
    test_simulation_ends_on_duration_and_heater_failure_time()
    test_run_save_load_delete_and_metrics()
    test_euler_instability_reported_and_rk4_fine()
    print("all API tests passed")
