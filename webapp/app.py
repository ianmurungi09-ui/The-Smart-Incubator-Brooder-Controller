"""Full-stack brooder app: Flask API (runs our own Euler/RK4) + SQLite run history + web form UI.

    python -m webapp.app        ->  http://127.0.0.1:5000
"""
import json
import hmac
import os
import re
import secrets
import sqlite3
import time
from functools import wraps



app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-secure-development-secret-key-12345')
import numpy as np
from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from brooder.model import Plant, Controller, make_rhs, control, required_power
from brooder.solvers import STEPPERS
from brooder.metrics import recovery_time, steady_state_error, peak_deviation, overshoot_pct

DB_PATH = os.environ.get("BROODER_DB", os.path.join(os.path.dirname(__file__), "runs.db"))
MAX_STEPS = 200_000
MAX_POINTS = 1200

# field -> (min, max, default).  Everything the form sends is validated against this table.
SPEC = {
    "C": (1000, 100000, 8000), "R": (0.05, 1.0, 0.20), "rain_loss": (0, 2, 0.30),
    "n_chicks": (0, 200, 20), "q_chick": (0, 2, 0.4), "P_max": (10, 1000, 150),
    "T_set": (25, 40, 35), "Kp": (0, 200, 8), "Ki": (0, 1, 0.01), "Kd": (0, 50000, 0),
    "tau_d": (5, 600, 60), "T0": (0, 45, 25),
    "manual_power_pct": (0, 100, 50),
    "amb_day": (-10, 40, 25), "amb_night": (-10, 40, 12), "night_start_h": (0, 47, 2),
    "night_ramp_min": (1, 360, 30), "dawn_start_h": (0, 48, 9),
    "rain_start_h": (0, 48, 5), "rain_end_h": (0, 48, 7),
    "duration_h": (0.5, 48, 12), "h": (0.5, 300, 5),
}

app = Flask(__name__)
app.secret_key = os.environ.get("BROODER_SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


# ------------------------------------------------------------------ database
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            created REAL NOT NULL)""")
        g.db.execute("""CREATE TABLE IF NOT EXISTS runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, label TEXT,
            params TEXT, metrics TEXT, result TEXT,
            user_id INTEGER REFERENCES users(id))""")
        columns = {row["name"] for row in g.db.execute("PRAGMA table_info(runs)")}
        if "user_id" not in columns:
            g.db.execute("ALTER TABLE runs ADD COLUMN user_id INTEGER REFERENCES users(id)")
        g.db.execute("CREATE INDEX IF NOT EXISTS runs_user_id_id ON runs(user_id, id DESC)")
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d is not None:
        d.close()


def csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_csrf():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if request.path.startswith("/api/") and session.get("user_id") is None:
        return jsonify({"error": "authentication required"}), 401
    expected = session.get("_csrf_token")
    provided = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if expected and provided and hmac.compare_digest(expected, provided):
        return
    if request.path.startswith("/api/"):
        return jsonify({"error": "invalid or missing CSRF token"}), 400
    abort(400, description="Invalid or missing CSRF token.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication required"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id") is not None:
        return redirect(url_for("index"))
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not 3 <= len(username) <= 32 or not re.fullmatch(r"[\w.-]+", username):
            error = "Username must be 3–32 letters, numbers, dots, dashes, or underscores."
        elif not 8 <= len(password) <= 128:
            error = "Password must be between 8 and 128 characters."
        else:
            try:
                connection = db()
                cur = connection.execute(
                    "INSERT INTO users(username,password_hash,created) VALUES(?,?,?)",
                    (username, generate_password_hash(password), time.time()))
                if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
                    connection.execute("UPDATE runs SET user_id=? WHERE user_id IS NULL",
                                       (cur.lastrowid,))
                connection.commit()
            except sqlite3.IntegrityError:
                error = "That username is already taken."
            else:
                session.clear()
                session["user_id"] = cur.lastrowid
                return redirect(url_for("index"))
    return render_template("auth.html", mode="signup", error=error, username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id") is not None:
        return redirect(url_for("index"))
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db().execute(
            "SELECT id, password_hash FROM users WHERE username=? COLLATE NOCASE",
            (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid username or password."
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
    return render_template("auth.html", mode="login", error=error, username=username)


@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- validation
def _parse_bool(value, default=True):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"1", "true", "yes", "on"}:
            return True
        if s in {"0", "false", "no", "off"}:
            return False
    raise ValueError("must be a boolean")


def parse(body):
    errors, p = {}, {}
    mode = str(body.get("mode", "automatic")).lower()
    for k, (lo, hi, default) in SPEC.items():
        if k == "manual_power_pct" and mode == "automatic":
            p[k] = default
            continue
        raw = body.get(k, default)
        try:
            v = float(raw)
            if not np.isfinite(v):
                raise ValueError
        except (TypeError, ValueError):
            errors[k] = "must be a number"
            continue
        if not lo <= v <= hi:
            errors[k] = f"must be between {lo} and {hi}"
        if k == "n_chicks" and not v.is_integer():
            errors[k] = "must be an integer"
        p[k] = v
    method = str(body.get("method", "rk4")).lower()
    p["method"] = method
    if p["method"] not in STEPPERS:
        errors["method"] = "must be 'euler' or 'rk4'"
    p["mode"] = mode
    if p["mode"] not in {"automatic", "manual"}:
        errors["mode"] = "must be 'automatic' or 'manual'"
    try:
        p["antiwindup"] = _parse_bool(body.get("antiwindup", True))
    except ValueError:
        errors["antiwindup"] = "must be a boolean"
    try:
        p["save"] = _parse_bool(body.get("save", True))
    except ValueError:
        errors["save"] = "must be a boolean"
    raw_fail = body.get("heater_fail_h")
    if raw_fail not in (None, ""):
        try:
            fail_h = float(raw_fail)
            if not np.isfinite(fail_h) or fail_h < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors["heater_fail_h"] = "must be a non-negative number"
        else:
            p["heater_fail_h"] = fail_h
    else:
        p["heater_fail_h"] = None
    if "rain_end_h" in p and "rain_start_h" in p and p["rain_end_h"] < p["rain_start_h"]:
        errors["rain_end_h"] = "must be after rain start"
    if "duration_h" in p and "h" in p and p["duration_h"] * 3600 / p["h"] > MAX_STEPS:
        errors["h"] = f"too many steps (max {MAX_STEPS}); increase h or shorten the run"
    return p, errors


# ----------------------------------------------------------------- simulation
def ramp(t, t0, dur, a, b):
    s = min(max((t - t0) / dur, 0.0), 1.0)
    return a + (b - a) * s


def simulate(p):
    plant = Plant(C=p["C"], R=p["R"], rain_loss=p["rain_loss"], q_chick=p["q_chick"],
                  n_chicks=int(p["n_chicks"]), P_max=p["P_max"])
    ctrl = Controller(T_set=p["T_set"], Kp=p["Kp"], Ki=p["Ki"], Kd=p["Kd"],
                      tau_d=p["tau_d"], antiwindup=p["antiwindup"], mode=p["mode"],
                      manual_power_pct=p["manual_power_pct"])
    H = 3600.0
    t_n, t_d = p["night_start_h"] * H, p["dawn_start_h"] * H
    ramp_s = p["night_ramp_min"] * 60.0
    r0, r1 = p["rain_start_h"] * H, p["rain_end_h"] * H

    def ambient(t):
        a = ramp(t, t_n, ramp_s, p["amb_day"], p["amb_night"])
        return ramp(t, t_d, ramp_s, a, p["amb_day"]) if t >= t_d > t_n else a

    def rain(t):
        if r1 <= r0:
            return 0.0
        return min(ramp(t, r0, 300, 0, 1), ramp(t, r1, 300, 1, 0) if t >= r1 else 1.0)

    fail = p.get("heater_fail_h")
    f = make_rhs(plant, ctrl, ambient, rain)
    step = STEPPERS[p["method"]]
    h, t_end = p["h"], p["duration_h"] * H
    n = int(np.ceil(t_end / h))
    stride = max(1, int(np.ceil((n + 1) / MAX_POINTS)))
    y = np.array([p["T0"], 0.0, p["T0"]])
    t = 0.0
    metric_t = [t]
    metric_T = [float(y[0])]
    rec = {k: [] for k in ("t", "T", "Ta", "P", "rain")}
    unstable = None
    fail_t = None if fail in (None, "") else float(fail) * H

    def record():
        rec["t"].append(t / H)
        rec["T"].append(float(y[0]))
        rec["Ta"].append(ambient(t))
        rec["P"].append(control(ctrl, plant, *y)[2])
        rec["rain"].append(rain(t))

    if fail_t is not None and t >= fail_t:
        ctrl.heater_on = False
    record()
    i = 0
    while t < t_end:
        if fail_t is not None and t >= fail_t:
            ctrl.heater_on = False
        hi = min(h, t_end - t)
        if fail_t is not None and t < fail_t < t + hi:
            hi = fail_t - t
        y = step(f, t, y, hi)
        t = t_end if hi >= t_end - t else t + hi
        i += 1
        if fail_t is not None and t >= fail_t:
            ctrl.heater_on = False
        if (not np.all(np.isfinite(y))) or abs(y[2] - y[0]) > 500 or abs(y[0]) > 500:
            unstable = (f"Numerical instability at t = {t / H:.2f} h with {p['method'].upper()} and "
                        f"h = {h:g} s. Reduce h or use RK4.")
            break
        metric_t.append(t)
        metric_T.append(float(y[0]))
        if i % stride == 0 or t >= t_end or (fail_t is not None and t == fail_t):
            record()
    ts = np.array(metric_t)
    temperatures = np.array(metric_T)
    e = ctrl.T_set - temperatures
    metrics = {"unstable": unstable,
               "required_power_night_W": required_power(plant, ctrl.T_set, p["amb_night"]),
               "required_power_night_rain_W": required_power(plant, ctrl.T_set, p["amb_night"], 1.0),
               "heater_can_hold_night_rain": required_power(plant, ctrl.T_set, p["amb_night"], 1.0) <= plant.P_max}
    if len(ts) > 3 and not unstable:
        # score the cold-night disturbance only up to the next scenario event (rain or dawn)
        nxt = [x for x in ([r0] if r1 > r0 else []) + [t_d] if x > t_n + ramp_s]
        w_end = min([ts[-1]] + nxt)
        mw = (ts <= w_end)
        rt = recovery_time(ts[mw], e[mw], t_n) if t_n < w_end else float("nan")
        metrics.update({
            "peak_dev_K": peak_deviation(ts[mw], e[mw], t_n) if t_n < w_end else None,
            "recovery_min": None if np.isnan(rt) else rt / 60,
            "steady_state_error_K": steady_state_error(ts, e, min(1800, ts[-1] / 2)),
            "startup_overshoot_pct": overshoot_pct(temperatures, p["T0"], ctrl.T_set) if p["T0"] < ctrl.T_set - 1 else None,
            "minutes_outside_33_37C": float(np.sum(
                ((temperatures[:-1] < 33) | (temperatures[:-1] > 37)) * np.diff(ts)
            ) / 60),
            "max_T": float(np.max(temperatures)), "min_T": float(np.min(temperatures))})
    return rec, metrics


# ------------------------------------------------------------------ routes
@app.get("/")
def landing():
    return render_template("landing.html", logged_in=session.get("user_id") is not None)


@app.get("/app")
@login_required
def index():
    user = db().execute("SELECT username FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if user is None:
        session.clear()
        return redirect(url_for("login"))
    return render_template("index.html", spec=SPEC, username=user["username"],
                           csrf=csrf_token())


@app.post("/api/simulate")
@login_required
def api_simulate():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"errors": {"body": "must be a JSON object"}}), 400
    p, errors = parse(body)
    if errors:
        return jsonify({"errors": errors}), 400
    should_save = p.pop("save")
    t0 = time.time()
    rec, metrics = simulate(p)
    metrics["compute_s"] = round(time.time() - t0, 3)
    out = {"params": {k: v for k, v in p.items()}, "metrics": metrics, "series": rec}
    if should_save:
        label = str(body.get("label") or f"{p['mode'].title()} {p['method'].upper()} h={p['h']:g}s")[:80]
        cur = db().execute(
            "INSERT INTO runs(created,label,params,metrics,result,user_id) VALUES(?,?,?,?,?,?)",
            (time.time(), label, json.dumps(out["params"]), json.dumps(metrics), json.dumps(rec),
             session["user_id"]))
        db().commit()
        out["id"] = cur.lastrowid
    return jsonify(out)


@app.get("/api/runs")
@login_required
def api_runs():
    rows = db().execute(
        "SELECT id, created, label, params, metrics FROM runs WHERE user_id=? "
        "ORDER BY id DESC LIMIT 50", (session["user_id"],)).fetchall()
    return jsonify([{"id": r["id"], "created": r["created"], "label": r["label"],
                     "params": json.loads(r["params"]), "metrics": json.loads(r["metrics"])} for r in rows])


@app.get("/api/runs/<int:rid>")
@login_required
def api_run(rid):
    r = db().execute("SELECT * FROM runs WHERE id=? AND user_id=?",
                     (rid, session["user_id"])).fetchone()
    if r is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": rid, "label": r["label"], "params": json.loads(r["params"]),
                    "metrics": json.loads(r["metrics"]), "series": json.loads(r["result"])})


@app.delete("/api/runs/<int:rid>")
@login_required
def api_delete(rid):
    cur = db().execute("DELETE FROM runs WHERE id=? AND user_id=?",
                       (rid, session["user_id"]))
    if cur.rowcount == 0:
        return jsonify({"error": "not found"}), 404
    db().commit()
    return jsonify({"deleted": rid})


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
