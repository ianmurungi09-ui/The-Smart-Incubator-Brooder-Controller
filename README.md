# Smart Incubator / Brooder Controller  (Project 14)

Interactive ODE simulation of a poultry brooder kept at its target temperature by a PI/PID-controlled
heater while the outdoor conditions change (cold night, rain). Python + Pygame; the numerical methods
(explicit Euler and classical RK4) are written by us in `brooder/solvers.py` - no ODE library or physics engine.

## Setup
```
python -m venv .venv
.venv\Scripts\activate          # Windows      (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python brooder_sim.py           # interactive simulation
python experiments.py           # regenerates every figure/table in ./results
python brooder_sim.py --selftest  # headless check of the simulation core (no window)
```

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
# Web application (full-stack version)

```
pip install -r requirements.txt
python -m webapp.app            # then open http://127.0.0.1:5000
python tests/test_api.py        # API tests
```

| layer | what | where |
|---|---|---|
| Front end | web form (plant, controller, weather scenario, solver, step size), animated brooder canvas (gauge, heater glow, chicks, rain), plots, metric cards, saved-run table with overlay | `webapp/templates/index.html` |
| Back end  | Flask JSON API; validates every field against `SPEC`; runs our own Euler/RK4 (`brooder/solvers.py`); computes recovery time, peak deviation, steady-state error, overshoot | `webapp/app.py` |
| Database  | SQLite (`webapp/runs.db`, created automatically) stores every run's parameters, metrics and series | `webapp/app.py` |

API: `POST /api/simulate` (JSON parameters -> series + metrics, saved unless `"save": false`),
`GET /api/runs`, `GET /api/runs/<id>`, `DELETE /api/runs/<id>`.

Notes: the simulation runs on the server, then the browser plays the returned series back (so the animation is driven by
the numerical states). Step count is capped at 200,000 per request. Numerical blow-up (e.g. Euler, large h, PID) is
detected and reported in the page. For deployment use a production WSGI server (e.g. `gunicorn webapp.app:app`) and
turn `debug` off. The Pygame version (`brooder_sim.py`) is unchanged and still satisfies the course's "Pygame recommended" line.
