"""Builds Brooder_Controller_Report.docx from the results/ tables and figures."""
import csv
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

R = "results/"
def rows(name):
    with open(R + name, newline="") as fh:
        return list(csv.reader(fh))

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for m in ("left_margin", "right_margin"): setattr(sec, m, Cm(1.7))
sec.top_margin, sec.bottom_margin = Cm(1.4), Cm(1.3)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(9.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st.paragraph_format.space_after = Pt(3); st.paragraph_format.space_before = Pt(0)
st.paragraph_format.line_spacing = 1.0

def para(text="", bold=False, italic=False, size=None, align=None, after=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text); r.bold, r.italic = bold, italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = RGBColor(*color)
    if align: p.alignment = align
    if after is not None: p.paragraph_format.space_after = Pt(after)
    return p

def rich(parts, after=None):
    """parts: list of (text, bold)"""
    p = doc.add_paragraph()
    for t, b in parts:
        r = p.add_run(t); r.bold = b
    if after is not None: p.paragraph_format.space_after = Pt(after)
    return p

def heading(text):
    p = para(text, bold=True, size=11, after=2, color=(31, 78, 121))
    p.paragraph_format.space_before = Pt(5); p.paragraph_format.keep_with_next = True
    return p

def eq(text):
    p = para(text, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    return p

def shade(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), hexcol)
    tcPr.append(shd)

def table(data, widths, size=8, header=True):
    t = doc.add_table(rows=len(data), cols=len(data[0]))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(data):
        for j, val in enumerate(row):
            c = t.cell(i, j); c.width = Cm(widths[j])
            c.text = ""
            p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(0)
            r = p.add_run(str(val)); r.font.size = Pt(size)
            if header and i == 0:
                r.bold = True; shade(c, "DCE6F1")
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return t

def figure(path, width_cm, caption):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(R + path, width=Cm(width_cm)); p.paragraph_format.space_after = Pt(0)
    para(caption, italic=True, size=8, align=WD_ALIGN_PARAGRAPH.CENTER, after=3)

# ------------------------------------------------------------------ title
para("Smart Incubator / Brooder Controller - Technical Report", bold=True, size=15, after=0, color=(31, 78, 121))
para("Differential Equations Group Project 14  |  Group members: ____________________  |  Code: brooder_sim.py, webapp/app.py, experiments.py",
     size=8.5, after=4)

# ------------------------------------------------------------------ 1
heading("1. Problem, assumptions and governing ODEs")
para("Objective: keep a poultry brooder near a target temperature (35 °C for day-old chicks) with a heater under PI/PID "
     "control while the outdoor temperature falls at night and rain increases the heat loss. Assumptions: (i) one "
     "well-mixed temperature T for air and bedding (lumped capacitance); (ii) heat loss to ambient proportional to "
     "T - Ta (Newton cooling) with the loss coefficient raised by a factor (1 + k·rain) in rain/wind; (iii) chicks add "
     "a constant metabolic heat Q = n·q; (iv) the heater is ideal (no lag) but limited to 0 <= P <= Pmax and cannot cool; "
     "(v) the sensor is ideal; (vi) controller is evaluated continuously (its states are integrated with the plant).", after=3)
eq("C dT/dt = P + Q - g(t)(T - Ta(t)),    g = (1 + k·rain(t))/R,    P = clip(u, 0, Pmax)")
eq("dI/dt = e + (P - u)/Kp,    dTm/dt = (T - Tm)/τd,    u = Kp e + Ki I - Kd (T - Tm)/τd,    e = Tset - T")
para("State vector y = [T, I, Tm]: brooder temperature (°C), integral of error (K·s) and low-pass-filtered temperature "
     "(°C), so (T - Tm)/τd is a noise-free estimate of dT/dt (derivative on the measurement, no set-point kick). The "
     "term (P - u)/Kp is back-calculation anti-windup (Tt = Ti = Kp/Ki). Parameters (illustrative, simplified): "
     "C = 8000 J/K, R = 0.20 K/W (UA = 5 W/K, plant time constant RC = 27 min), k = 0.3, Q = 20 × 0.4 = 8 W, Pmax = 150 W, "
     "Tset = 35 °C, Kp = 8 W/K, Ki = 0.01 W/(K·s), Kd = 0, τd = 60 s. Initial conditions: cold start T(0) = Ta = 25 °C, "
     "I(0) = 0; for disturbance tests the loop is first run to steady state. Without control and with constant P the "
     "exact solution is T = T∞ + (T0 - T∞)e^(-t/τ). With Kd = 0, constant Ta and no saturation, [T, I] obeys a linear "
     "system x' = Ax + b with exact solution found by eigen-decomposition; its characteristic equation "
     "C s² + (Kp + g)s + Ki = 0 gives ωn = √(Ki/C) and ζ = (Kp + g)/(2√(C·Ki)) (ζ = 0.73 for the defaults). "
     "Steady-state heater power needed: Preq = g(Tset - Ta) - Q (e.g. 107 W at 12 °C, 141.5 W at 12 °C with rain).", after=2)

# ------------------------------------------------------------------ 2
heading("2. Numerical methods and validation")
para("Explicit Euler (yn+1 = yn + h f) and classical RK4 were implemented by us (brooder/solvers.py) and used for the "
     "whole coupled system; no ODE library is used. Reference solutions: the exact PI-loop solution above "
     "(T0 = 30 °C, Ta = 20 °C, 4 h, heater unsaturated) and, for the PID loop, a refined RK4 run with h = 0.1 s.", after=3)
conv = rows("e6a_convergence_PI.csv")
tbl = [["h (s)", "Euler max error (K)", "order", "RK4 max error (K)", "order"]]
for k in range(4):
    e, r = conv[1 + k], conv[5 + k]
    tbl.append([e[1].replace(".0", ""), e[2], e[3] or "-", r[2], r[3] or "-"])
table(tbl, [2.0, 3.6, 2.0, 3.6, 2.0])
para("Observed orders are ≈1 for Euler and ≈4 for RK4, as theory predicts; at h = 300 s Euler is off by 0.52 K but RK4 by "
     "0.0004 K. Against the refined reference on the PID loop (h = 40/20/10/5 s) the Euler error halves each time "
     "(5.9e-2 → 7.2e-3 K) while the RK4 error drops from 3.4e-5 to 4.2e-9 K. Open-loop validation against "
     "T(t) = T∞ + (T0 - T∞)e^(-t/τ) gave the same orders. Stability (numerical, not physical): the derivative filter "
     "(τd = 60 s) makes the PID loop stiff; explicit Euler needs h < 2τd = 120 s just for the filter and in "
     "the loop it already produces a false ≈1–2 K limit cycle at h = 100 s (Fig. 1, right) and diverges "
     "(|Tm - T| ~ 10⁶ K) at h = 130 s, while RK4 remains accurate. The physical system is stable for all gains "
     "used, so this behaviour is purely a numerical artefact; the program detects it and stops with a message.", after=2)
figure("fig7_numerics.png", 15.5, "Fig. 1  Left: error vs step size against the exact PI solution (slopes 1 and 4). Right: PID loop, h = 100 s - Euler wrong, RK4 matches the reference.")

# ------------------------------------------------------------------ 3
heading("3. Experiments and physical interpretation")
para("Disturbances: cold night = ambient ramps 25 → 12 °C in 30 min (loop starts at steady state); rain = loss coefficient "
     "×1.3 at Ta = 15 °C. Measures: peak deviation |e|max, recovery time (|e| < 0.5 K from then on), steady-state error "
     "(mean e over the last 30 min). RK4, h = 2 s.", after=3)
para("E1 - controller type and tuning (Fig. 2). ", bold=True, after=1)
e1 = rows("e1_controllers.csv")
t1 = [["controller", "cold night: peak / recovery / SSE", "rain: peak / recovery / SSE"]]
for k in range(1, len(e1), 2):
    a, b = e1[k], e1[k + 1]
    t1.append([a[0], f"{a[2]} K / {a[3]} min / {a[4]} K", f"{b[2]} K / {b[3]} min / {b[4]} K"])
table(t1, [4.2, 6.4, 6.4])
para("P-only control cannot remove the load: the heater only works when e ≠ 0, so a steady error "
     "e = Preq/(Kp + g) = 107/13 ≈ 8.2 K remains (cold night, no rain). Integral action drives the error to zero at the price of slower "
     "recovery; recovery is governed mainly by Ki and the peak mainly by Kp (grid in Fig. 5: peak 6.3 → 0.8 K and recovery "
     "168 → 37 min across Kp = 2–20, Ki = 0.002–0.05). Large Ki lowers ζ (0.18 for Kp = 2, Ki = 0.05) and makes "
     "temperature oscillate; small Ki with large Kp is over-damped but takes hours (372 min). The D-term brings no "
     "benefit here (peak 2.77 → 2.67 K but recovery 70 → 75 min; Kd = 12000 is slower still): the plant is first-order "
     "and slow, so there is little to anticipate and D only amplifies sensor noise in a real system.", after=2)
figure("fig2_controllers.png", 15.0, "Fig. 2  Response to a cold night (left) and to rain (right) for P, PI, PID and a faster PI.")
para("E2 - heater capacity (Fig. 3) and E3 - insulation (Fig. 4), cold night 12 °C (+ rain in E2). ", bold=True, after=1)
e2, e3 = rows("e2_capacity.csv"), rows("e3_insulation.csv")
t2 = [["Pmax (W)", "needed (W)", "peak (K)", "recovery", "SSE (K)"]] + [[r[0], r[1], r[2], (r[3] + " min") if r[3] != "never" else "never", r[4]] for r in e2[1:]]
t3 = [["R (K/W)", "RC (min)", "needed (W)", "peak (K)", "recovery", "SSE (K)", "30 °C after heater fails"]] + \
     [[r[0], r[2], r[3], r[4], (r[5] + " min") if r[5] != "never" else "never", r[6], r[7] + " min"] for r in e3[1:]]
table(t2, [2.2, 2.4, 2.2, 2.4, 2.2], size=8)
table(t3, [1.9, 1.9, 2.3, 1.9, 2.1, 1.8, 3.6], size=8)
para("A heater whose capacity is below the steady load (141.5 W at 12 °C with rain) cannot hold the target however it is "
     "tuned: the command saturates and T settles at the open-loop equilibrium Ta + (Pmax + Q)/g (22.5 °C for 60 W, "
     "28.6 °C for 100 W) - a steady-state error caused by actuator saturation, not by the controller. Above the needed "
     "power more capacity does not help (150 W and 250 W give identical results): recovery is then limited by the "
     "loop gains. Insulation acts on both sides: R = 0.1 K/W needs 222 W and fails; R = 0.4 K/W needs only 49.5 W, "
     "reduces the peak (1.55 K) and gives a 16 min grace period after a heater failure (3 min for R = 0.1), at the "
     "cost of slower passive response (RC = 53 min).", after=2)
para("E4 - start-up and integral windup (Fig. 6). ", bold=True, after=1)
e5 = rows("e5_windup.csv")
para(f"Cold start 20 → 35 °C with Ki = 0.05: the heater saturates while e is large, so without anti-windup the integral "
     f"keeps growing and the temperature overshoots by {e5[1][3]} K ({e5[1][2]} %, i.e. ≈ 42 °C, heat stress for chicks) and needs "
     f"{e5[1][4]} min to settle; with back-calculation the overshoot is {e5[2][3]} K ({e5[2][2]} %) and settling takes {e5[2][4]} min.", after=2)
# 2x2 figure grid
g = doc.add_table(rows=2, cols=2); g.alignment = WD_TABLE_ALIGNMENT.CENTER
caps = {(0, 0): ("fig3_capacity.png", "Fig. 3  Heater capacity"), (0, 1): ("fig4_insulation.png", "Fig. 4  Insulation"),
        (1, 0): ("fig5_tuning.png", "Fig. 5  Kp-Ki grid, cold night"), (1, 1): ("fig6_windup.png", "Fig. 6  Anti-windup")}
for (i, j), (f, c) in caps.items():
    cell = g.cell(i, j); p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(R + f, width=Cm(8.4)); p.paragraph_format.space_after = Pt(0)
    q = cell.add_paragraph(); r = q.add_run(c); r.italic = True; r.font.size = Pt(8)
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER; q.paragraph_format.space_after = Pt(2)

# ------------------------------------------------------------------ 4
heading("4. Events, approximations and limitations")
para("Events/boundaries implemented in the program: heater power clipped to [0, Pmax]; heater-saturation warning; chick "
     "chilling (T < 31 °C) and heat-stress (T > 38.5 °C) alarms; target-reached (|e| < 0.5 K for 5 min); heater fault; "
     "automatic recovery-time/peak/steady-state measurement after each disturbance; numerical-instability stop. Limitations: "
     "single-node thermal model (no air/bedding/box gradients, no humidity, ventilation or ambient radiation); constant "
     "k and Q; ideal sensor and heater without lag or noise; continuous-time controller (a sampled controller would add a "
     "delay); parameters are illustrative and should be fitted to a measured cooling curve (T(t) = T∞ + (T0 - T∞)e^(-t/RC) gives "
     "RC and, with a known heater power, R); the clip and the rain/ambient step changes make the right-hand side only piecewise "
     "smooth, so RK4 order degrades slightly across them; chick positions on screen are an illustration driven by T, not part of "
     "the ODE model. Conclusion: a PI controller with anti-windup removes the steady-state error for a first-order thermal "
     "plant, performance is bounded by heater capacity and insulation rather than by tuning, and RK4 is the safer solver "
     "(accuracy and stability) at step sizes up to the 100 s range, where explicit Euler gives physically wrong answers.", after=0)

# ------------------------------------------------------------------ 5
heading("5. Browser application: architecture and user journey")
para("The Flask web application provides a browser interface to the same brooder model and numerical methods described "
     "above. Flask renders the pages and validates requests, the Python model computes simulation results on the server, "
     "and SQLite stores accounts and saved runs. The web app is educational software; it does not connect to or control "
     "physical brooder equipment.", after=3)
table([
    ["Page or route", "Purpose"],
    ["GET /", "Public welcome page with a local chick photo, sample readings, account links, theme switch and Pip guide."],
    ["GET/POST /signup and /login", "Create an account or start a session. Both routes use the shared auth.html template."],
    ["GET /app", "Protected dashboard for beginner setup, optional advanced settings, simulation playback, charts, metrics and saved runs."],
    ["POST /api/simulate", "Validate input, run the model and return parameters, metrics and time series; save the run when requested."],
    ["GET /api/runs and GET/DELETE /api/runs/<id>", "List, load or remove the signed-in user's runs. Each query is scoped to the current account."]
], [4.0, 13.6], size=7.5)

heading("5.1 Account page: auth.html")
para("webapp/templates/auth.html is one Jinja template used by both the sign-up and sign-in routes. Flask supplies a mode "
     "value, any validation error, and the submitted username. The mode controls the page title, heading, helper text, "
     "password hints, submit label and link to the other account flow, so the two pages stay visually consistent without "
     "duplicating the form. A successful account action establishes a session and redirects to the protected dashboard.", after=2)
para("The form posts to the current route and includes a hidden CSRF token from the Flask session. Labels are associated "
     "with their inputs; browser autocomplete hints identify username, new-password and current-password fields. Sign-up "
     "requires a 3–32 character username and an 8–128 character password. The server independently checks these limits, "
     "the allowed username characters and case-insensitive uniqueness. Browser attributes improve usability but are not "
     "the security boundary. Validation errors are announced with role=alert, the username is preserved, and the password "
     "is never returned to the page.", after=2)
para("Passwords are stored as Werkzeug password hashes, not readable text. Sign-in checks the submitted password against "
     "the stored hash and uses a generic invalid-username-or-password message. The CSRF guard validates state-changing "
     "requests, and the login-required wrapper protects the dashboard and API. Saved-run reads and deletes include the "
     "current user ID, preventing one account from accessing another account's records.", after=2)

heading("5.2 Appearance, accessibility and guided help")
para("On wide screens, auth.html uses a split story-and-form layout. Below 850 px the form is placed first so it is "
     "reachable before the decorative story on smaller screens. The story panel includes the local chick photograph, "
     "descriptive alternative text, a source credit and a CC0 dedication. The footer reminds visitors that this is a "
     "learning simulation and real brooders still need careful monitoring.", after=2)
para("The welcome page and dashboard expose Dark mode / Light mode controls. They save the selection in the browser's "
     "brooder-theme local-storage key. The account page reads the saved choice and, before one is saved, follows the "
     "system color preference. This is a browser-side presentation setting; it does not change model parameters or "
     "server-side account data.", after=2)
para("The shared Meet Pip guide explains the welcome page, account forms and dashboard. Its written instructions remain "
     "available as a fallback; speech synthesis starts only after the visitor chooses Read aloud. The interface uses "
     "semantic form labels, keyboard-focus styling and responsive layouts to support first-time users.", after=2)

heading("5.3 Persistence, configuration and limitations")
para("The default SQLite database is webapp/runs.db; BROODER_DB can point to a separate database for testing or "
     "deployment. User rows contain a username and password hash. Saved runs contain their label, parameters, metrics, "
     "time series and owning user ID. A new account receives legacy unassigned runs once, when it is the first account "
     "created after the migration.", after=2)
para("All simulation API routes require a signed-in session. The session secret is generated at startup for local use; "
     "set BROODER_SECRET_KEY to a stable, private value when sessions must survive restarts. Deployments should use a "
     "production WSGI server and appropriate secure-cookie and HTTPS settings. The numerical model remains simplified "
     "and must not be used as a substitute for sensors, alarms or supervision on a real brooder.", after=0)

doc.save("Brooder_Controller_Report.docx")
print("saved")
