# Smart Incubator / Brooder Controller  (Project 14)

This project combines a Flask web app with a Pygame desktop simulation of a poultry brooder. Both model
temperature control with a PI/PID-controlled heater as outdoor conditions change. The web app includes
beginner-friendly controls, private saved runs, a persistent light/dark theme, and Pip's optional spoken guide.
The numerical methods (explicit Euler and classical RK4) are implemented in `brooder/solvers.py` without an ODE
library or physics engine.

## Run the web app (recommended)

Run these commands from the project folder (the folder containing this README).

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m webapp.app
```

Open `http://127.0.0.1:5000` in your browser. Stop the server with **Ctrl+C** in the terminal.

### macOS / Linux

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m webapp.app
```

### Run from VS Code

Open this project folder in VS Code, select **Run Brooder Web App** in Run and Debug, then press **F5**.
VS Code starts Flask and opens the local app.

### Run the tests

Pytest is a development dependency and is not included in `requirements.txt`. Install it in the same environment,
then run:

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

**macOS / Linux:**

```sh
./.venv/bin/python -m pip install pytest
./.venv/bin/python -m pytest -q
```

### Pygame simulation and experiments

The original desktop simulation and report-generation scripts are still available:

```powershell
.\.venv\Scripts\python.exe brooder_sim.py
.\.venv\Scripts\python.exe experiments.py
.\.venv\Scripts\python.exe brooder_sim.py --selftest
.\.venv\Scripts\python.exe make_report.py
.\.venv\Scripts\python.exe make_slides.py
```

`make_report.py` rebuilds `Brooder_Controller_Report.docx` from the tables and figures in `results/`. The report now
also explains the web application, including the shared sign-up/sign-in page, theme behavior, saved-run flow and
security checks. The `python-docx` dependency is installed with `requirements.txt`.

`make_slides.py` builds an editable 16:9 PowerPoint deck with the model, solver validation, experiment findings,
web-app architecture, account flow and safety limits. It uses the project photo and figures from `results/`;
`python-pptx` is installed with `requirements.txt`.

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `./.venv/bin/python`.

## Model (details in the report)
State `y = [T, I, Tm]` (brooder temperature, PID integral, low-pass filtered temperature for the D-term):

    C dT/dt = P + Q_chicks - (1 + k_rain*rain(t)) * (T - T_a(t)) / R        P = clip(u, 0, P_max)
    dI/dt   = e  (+ back-calculation anti-windup)       dTm/dt = (T - Tm)/tau_d
    u       = Kp*e + Ki*I - Kd*(T - Tm)/tau_d           e = T_set - T

| symbol | meaning | default | unit |
|---|---|---|---|
| C | thermal capacity (air, bedding, box) | 8000 | J/K |
| R | insulation resistance (UA = 1/R = 5 W/K) | 0.20 | K/W |
| k_rain | extra heat loss when raining | 0.30 | - |
| Q_chicks | 20 chicks x 0.4 W | 8 | W |
| P_max | heater capacity | 150 | W |
| T_set | target | 35 | deg C |
| Kp, Ki, Kd, tau_d | controller | 8, 0.01, 0, 60 | W/K, W/(K s), W s/K, s |

Initial condition in the program: cold start `T(0) = T_a = 25 deg C`, `I(0) = 0`.

## Files
| file | purpose |
|---|---|
| `brooder_sim.py` | Pygame program (GUI) + headless self-test |
| `brooder/solvers.py` | our Euler and RK4 steppers + fixed-step `integrate` |
| `brooder/model.py` | plant, controller, right-hand side `f(t, y)` |
| `brooder/analytic.py` | exact solutions (open loop; unsaturated PI loop via eigen-decomposition) |
| `brooder/metrics.py` | recovery time, steady-state error, peak deviation, overshoot |
| `experiments.py` | all experiments, figures (`results/*.png`) and tables (`results/*.csv`) |
| `make_report.py` | builds the technical report from the experiment results |
| `Brooder_Controller_Report.docx` | model, validation, experiments, web app and account-page explanation |
| `make_slides.py` | builds the project presentation from the photo and experiment figures |
| `Smart_Brooder_Project_Slides.pptx` | editable project overview presentation |

## Keys in the simulation
| key | action | key | action |
|---|---|---|---|
| SPACE / R | pause / reset (cold start) | F1 / F2 | clear day 25 C / cold night 12 C |
| 1 / 2 | Euler / RK4 | F3 | rain on/off (raises heat loss) |
| [ / ] | halve / double step h | LEFT / RIGHT | ambient -/+1 C |
| - / = | slower / faster (sim-s per real-s) | Z / X | heater capacity -/+10 W |
| UP / DOWN | target +/-0.5 C | C / V | insulation R -/+0.02 K/W |
| M | mode P -> PI -> PID | B | heater fault on/off |
| Q / A, W / S, E / D | Kp, Ki, Kd up / down | N | anti-windup on/off |
| H | hide/show help | ESC | quit |

Screen: thermometer gauge (green = comfort band 33-37 C, black line = target), heater power bar,
ambient/rain, chicks, scrolling plot of T, target, ambient and heater power, live metrics
(peak deviation, recovery time, steady-state error after every disturbance), event log.

The motion of everything on screen comes from the integrated state: the heater glow from P(T, I, Tm),
the thermometer from T, the sky/rain from T_a(t), rain(t); each chick walks to a place chosen from the
numerical T (huddle under the lamp when cold, spread out when comfortable, flee to the walls when hot).

## Events / boundaries handled
heater saturation (cannot hold target), chicks chilled (T < 31) / heat stress (T > 38.5), target reached
(|e| < 0.5 K for 5 min), heater fault, anti-windup, heater power clipped to [0, P_max], and *numerical
instability* detection (e.g. Euler with a large step on the PID loop) which stops the run with a message.

## Suggested demo script (10 min)
1. Cold start with RK4: gauge rises, heater saturates then backs off. Explain the ODE and state variables.
2. F2 (cold night) then F3 (rain): watch peak deviation / recovery time / steady-state error.
3. M -> P-only: show the steady-state error; back to PI; vary Kp/Ki.
4. Z (small heater) and C (poor insulation): "HEATER SATURATED" - capacity/insulation limits.
5. Press 1 (Euler), M twice (PID), `]` repeatedly (h = 80 s, then 160 s): Euler shows a false 1-2 K offset/limit cycle and then the instability message, RK4 stays correct.
6. N (anti-windup off), raise Ki with W a few times, R (cold start): large overshoot while the heater is saturated.

---
## Web application details

The public home page at `http://127.0.0.1:5000` previews the simulation before visitors sign up. Select **Create account** to start using it. Passwords are stored as hashes, and each account has its own saved-run history. Existing unassigned runs are transferred to the first account created after this upgrade.

Select **Meet Pip** on the welcome, sign-in/up, or dashboard page for an illustrated step-by-step guide. Choose **Read aloud** to hear the current explanation using the browser's built-in speech; narration starts only when requested. The written explanation remains available if speech is unsupported.

Use **Dark mode** or **Light mode** on the welcome page or dashboard to change the theme. The selection is saved in this browser and also applies on the sign-in/up pages; the system preference is used until a choice is saved.

The welcome and sign-in/up pages use a local photo of chicks in a brooder by [ELTORO.VET](https://commons.wikimedia.org/wiki/File:Fuzzy_yellow_chicks_in_a_brooder.jpg), dedicated to the public domain under CC0.

All `/api` endpoints require a signed-in session. A development session key is generated at startup; set `BROODER_SECRET_KEY` in the environment if sessions should remain valid across server restarts.

| layer | what | where |
|---|---|---|
| Front end | public welcome page and chick photo; signed-in simulation form, animated brooder canvas, plots, metric cards, private saved-run table and illustrated spoken guide | `webapp/templates/landing.html`, `webapp/templates/auth.html`, `webapp/templates/index.html`, `webapp/templates/_talking_guide.html`, `webapp/static/chicks-in-brooder.jpg`, `webapp/static/talking-guide.css`, `webapp/static/talking-guide.js` |
| Back end  | Flask sign-up/sign-in, authenticated JSON API, per-user run history, validation, Euler/RK4 simulation and metrics | `webapp/app.py` |
| Database  | SQLite (`webapp/runs.db`, created automatically) stores password hashes and each user's run parameters, metrics and series | `webapp/app.py` |

API: `POST /api/simulate` (JSON parameters -> series + metrics, saved unless `"save": false`),
`GET /api/runs`, `GET /api/runs/<id>`, `DELETE /api/runs/<id>`.

Notes: the simulation runs on the server, then the browser plays the returned series back (so the animation is driven by
the numerical states). Step count is capped at 200,000 per request. Numerical blow-up (e.g. Euler, large h, PID) is
detected and reported in the page. For deployment use a production WSGI server (e.g. `gunicorn webapp.app:app`) and
turn `debug` off. The Pygame version (`brooder_sim.py`) is unchanged and still satisfies the course's "Pygame recommended" line.
