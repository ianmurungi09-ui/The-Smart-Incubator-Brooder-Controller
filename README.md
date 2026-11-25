# Smart Brooder Assistant

A web assistant that helps small-scale poultry keepers brood chicks safely. It combines a
physics-based simulation of the brooder (our own Euler and RK4 solvers, no ODE library) with
a **rule-based advisor** that turns the keeper's situation into clear, prioritised actions.

**Live demo:** _add your Cloud Run URL here_

## Chosen vertical

**Livestock care / smallholder poultry farming.** The persona is a farmer raising a batch of
day-old chicks in a heated brooder, who needs to know *what temperature to hold, whether the
heater is big enough, and what to fix* without being a control engineer.

## How it works

1. **Describe the brooder** in the form: number of chicks, insulation, heater size, target
   temperature, and the night/rain weather you expect.
2. **Run the simulation.** The server integrates the thermal model with a PID-controlled heater
   and returns the temperature history and metrics. The browser replays it as an animation.
3. **Ask the advisor.** Enter the chick's age and whether mains power is reliable. The server
   re-runs the simulation with your validated settings and applies the rules below.

### Advisor logic (`brooder/advisor.py`)

| Context / result | Decision |
|---|---|
| Chick age in days | Recommended target: 35 °C (week 1), 32, 29, 26, 23, then 21 °C. Warns if the target is more than 2 °C too cold (critical) or too warm. |
| Flock size, insulation, night temperature, rain | Heater power needed on a rainy night vs. heater capacity: critical if too small, warning if under 20 % spare. |
| Unreliable power | Recommends battery/solar backup and extra insulation. |
| Run results | P-only offset → add integral action; overshoot → lower Ki / keep anti-windup; never recovered after the cold night → more heat or insulation; long time outside 33–37 °C; numerical instability → use RK4. |

Findings are sorted critical → warning → note → all good and are labelled with text, not colour alone.

### Architecture

```
brooder/          model, solvers (Euler, RK4), metrics, advisor  (pure Python, no I/O)
webapp/app.py     Flask JSON API, auth, validation, SQLite run history
webapp/templates  landing, login/signup, dashboard (canvas animation + advisor panel)
tests/            pytest: advisor rules, numerics, control modes, HTTP API
docs/SIMULATION.md  full model description and the original Pygame desktop simulator guide
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m webapp.app                                    # http://127.0.0.1:5000
pytest                                                  # 46 tests
```

## Deploy to Google Cloud Run

```bash
gcloud run deploy smart-brooder --source . --region <region> --allow-unauthenticated \
  --set-env-vars BROODER_SECRET_KEY=<long-random-string>
```

The `Dockerfile` listens on `$PORT`, runs gunicorn as an unprivileged user with one worker and
eight threads, and installs only the four runtime dependencies.

## Security

- Passwords hashed (Werkzeug); sessions are HttpOnly, SameSite=Lax and Secure on Cloud Run.
- CSRF token required on every state-changing request; all API routes require login.
- Every numeric field is range-checked server-side; request bodies capped at 64 KB;
  simulation steps capped at 50,000 per request; 100 saved runs per user.
- Per-IP rate limits on login, signup, simulate and advise (429 when exceeded).
- Security headers: CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `no-store` on the API.
- Secrets come from environment variables; the database file is git-ignored.
- The advisor never trusts client-supplied metrics. Metrics are recomputed on the server.
- All dynamic text inserted into the page is HTML-escaped.

## Accessibility

Skip link, labelled inputs, visible focus outlines, live regions for results and errors, a
text summary of each simulation for screen readers (the canvas animation has a text
alternative), light/dark themes, responsive layout, and severity shown as text labels.

## Testing

`pytest` runs 46 tests: advisor rules and edge cases, solver accuracy, control modes, and the
HTTP layer (auth, CSRF, validation, per-user isolation, step cap, rate limiting, headers).

## Assumptions and limits

- Brooding temperatures follow common practice for broilers and layers (35 °C in week 1,
  falling about 3 °C per week). Real flocks vary, so watch the chicks' behaviour.
- The model is a single-zone lumped thermal model with a fixed 0.4 W of heat per chick.
- Data lives in SQLite. On Cloud Run the container filesystem is ephemeral, so saved runs
  and accounts reset when the instance restarts. Use Cloud SQL or Firestore for persistence.
- The in-memory rate limiter is per process, which is why the container runs a single worker.
- This is decision support and a learning tool, not a substitute for monitoring a real brooder.
