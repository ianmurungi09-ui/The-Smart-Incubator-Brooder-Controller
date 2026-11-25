"""HTTP-level tests: auth, CSRF, validation, advisor endpoint, limits, headers."""
import itertools

import pytest

from webapp import app as appmod


@pytest.fixture()
def client():
    appmod.app.config["TESTING"] = True
    appmod.limiter.reset()
    with appmod.app.test_client() as c:
        yield c


_ids = itertools.count(1)


def signup(client, name=None):
    name = name or f"keeper{next(_ids)}"
    client.get("/signup")
    with client.session_transaction() as s:
        token = s["_csrf_token"]
    r = client.post("/signup", data={"username": name, "password": "correct-horse-1",
                                     "csrf_token": token})
    assert r.status_code == 302
    client.get("/app")                       # rendering the page issues a fresh CSRF token
    with client.session_transaction() as s:
        return s["_csrf_token"]


def post_json(client, url, body, token):
    return client.post(url, json=body, headers={"X-CSRF-Token": token})


def test_api_requires_login(client):
    assert client.post("/api/simulate", json={}).status_code == 401
    assert client.get("/api/runs").status_code == 401


def test_post_without_csrf_token_rejected(client):
    signup(client)
    assert client.post("/api/advise", json={}).status_code == 400


def test_security_headers_present(client):
    r = client.get("/")
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_advise_returns_findings(client):
    token = signup(client)
    r = post_json(client, "/api/advise", {"age_days": 3, "duration_h": 1, "h": 30,
                                          "power_reliable": False}, token)
    assert r.status_code == 200
    data = r.get_json()
    assert data["recommended_setpoint_C"] == 35.0
    assert any("backup" in f["message"] for f in data["findings"])


def test_advise_flags_wrong_target_for_age(client):
    token = signup(client)
    r = post_json(client, "/api/advise", {"age_days": 30, "T_set": 35, "duration_h": 1,
                                          "h": 30}, token)
    assert any(f["level"] == "warning" and "too warm" in f["message"]
               for f in r.get_json()["findings"])


@pytest.mark.parametrize("body,field", [({"age_days": 999}, "age_days"),
                                        ({"age_days": "abc"}, "age_days"),
                                        ({"T_set": 99}, "T_set"),
                                        ({"power_reliable": "maybe"}, "power_reliable")])
def test_advise_validates_input(client, body, field):
    token = signup(client)
    r = post_json(client, "/api/advise", body, token)
    assert r.status_code == 400 and field in r.get_json()["errors"]


def test_step_cap_enforced(client):
    token = signup(client)
    r = post_json(client, "/api/simulate", {"duration_h": 48, "h": 1}, token)
    assert r.status_code == 400 and "h" in r.get_json()["errors"]


def test_simulate_saves_and_isolates_users(client):
    token = signup(client)
    r = post_json(client, "/api/simulate", {"duration_h": 1, "h": 30}, token)
    assert r.status_code == 200
    run_id = r.get_json()["id"]
    client.post("/logout", data={"csrf_token": token})
    signup(client)
    assert client.get(f"/api/runs/{run_id}").status_code == 404
    assert client.get("/api/runs").get_json() == []


def test_rate_limit_returns_429(client):
    token = signup(client)
    codes = [post_json(client, "/api/advise", {"age_days": 3, "duration_h": 0.5, "h": 60},
                       token).status_code for _ in range(32)]
    assert 429 in codes


def test_rate_limiter_window():
    lim = appmod.RateLimiter()
    assert all(lim.allow("k", 3, 60) for _ in range(3))
    assert not lim.allow("k", 3, 60)
