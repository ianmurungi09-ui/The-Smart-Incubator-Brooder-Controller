"""Smart Incubator / Brooder Controller - interactive simulation (Python + Pygame).

Everything on screen is driven by the numerically integrated state y = [T, I, Tm]
(brooder temperature, PID integral, filtered temperature for the D-term).
The ODE solvers are our own Euler / RK4 (brooder/solvers.py) - no ODE library.

Run:   python brooder_sim.py            (press H in the program for the key list)
Test:  python brooder_sim.py --selftest (headless, no window)
"""
import math
import os
import random
import sys
from collections import deque

import numpy as np

from brooder.model import (Plant, Controller, make_rhs, control, required_power)
from brooder.solvers import STEPPERS

# ----------------------------------------------------------------- constants
WIN_W, WIN_H = 1180, 720
SCENE = (20, 20, 700, 380)          # x, y, w, h
PLOT = (20, 420, 700, 280)
BAND_LO, BAND_HI = 33.0, 37.0       # comfortable range for chicks (deg C)
CHILL_T, HEAT_T = 31.0, 38.5        # alarm thresholds
TOL = 0.5                           # K, "on target" tolerance
HOLD = 300.0                        # s the error must stay inside TOL to be "recovered"
SAMPLE_DT = 30.0                    # s between history samples for the plot
PLOT_SPAN = 6 * 3600.0              # s shown in the scrolling plot

WEATHER = {"day": 25.0, "night": 12.0}


# -------------------------------------------------------------- simulation core
class BrooderSim:
    """Model + solver + environment + event/metric bookkeeping (no graphics)."""

    def __init__(self):
        self.plant = Plant()
        self.ctrl = Controller(Kp=8.0, Ki=0.01, Kd=0.0)
        self.method = "rk4"
        self.h = 5.0                  # s, integration step
        self.speed = 600.0            # simulated seconds per real second
        self.paused = False
        self.f = make_rhs(self.plant, self.ctrl,
                          lambda t: self.amb_now, lambda t: self.rain_now)
        self.reset()

    # -- state ---------------------------------------------------------------
    def reset(self):
        self.t = 0.0
        self.amb_set, self.amb_now = 25.0, 25.0
        self.rain_set, self.rain_now = 0.0, 0.0
        self.y = np.array([self.amb_now, 0.0, self.amb_now])   # cold start
        self.carry = 0.0
        self.failed = None            # message if the numerics blow up
        self.hist = deque(maxlen=int(PLOT_SPAN / SAMPLE_DT) + 2)
        self.next_sample = 0.0
        self.err_hist = deque(maxlen=20)      # last 10 min of errors -> steady-state error
        self.sat_time = 0.0
        self.t_out_of_band = 0.0
        self.alarm = ""
        self.settled_time = 0.0
        self.events = deque(maxlen=5)
        self.mon_start("start-up")

    def log(self, msg):
        self.events.appendleft(f"{self.fmt_time()}  {msg}")

    def fmt_time(self):
        s = int(self.t)
        return f"d{s // 86400} {s % 86400 // 3600:02d}:{s % 3600 // 60:02d}"

    # -- disturbance / recovery monitor --------------------------------------
    def mon_start(self, why):
        self.mon = dict(t0=self.t, peak=0.0, last_out=self.t, recovery=None, why=why)
        self.log(f"disturbance: {why}")

    def mon_update(self, e):
        m = self.mon
        m["peak"] = max(m["peak"], abs(e))
        if abs(e) > TOL:
            m["last_out"] = self.t
            m["recovery"] = None
        elif m["recovery"] is None and self.t - m["last_out"] >= HOLD:
            m["recovery"] = m["last_out"] - m["t0"]
            self.log(f"recovered in {m['recovery'] / 60:.0f} min")

    # -- environment -----------------------------------------------------------
    def update_env(self, h):
        """Outdoor temperature and rain move gradually towards their set-points
        (1 K per 2 min, rain index over 5 min) - piecewise-constant over one step."""
        d = max(-h / 120.0, min(h / 120.0, self.amb_set - self.amb_now))
        self.amb_now += d
        dr = max(-h / 300.0, min(h / 300.0, self.rain_set - self.rain_now))
        self.rain_now += dr

    # -- one numerical step ----------------------------------------------------
    def step_once(self):
        self.update_env(self.h)
        self.y = STEPPERS[self.method](self.f, self.t, self.y, self.h)
        self.t += self.h
        T, I, Tm = self.y
        # boundary/event: numerical blow-up (e.g. explicit Euler with too large h)
        if (not np.all(np.isfinite(self.y))) or abs(Tm - T) > 500.0 or abs(T) > 500.0:
            self.failed = (f"NUMERICAL INSTABILITY ({self.method.upper()}, h = {self.h:g} s): "
                           "reduce h or switch to RK4")
            self.log("numerical instability - simulation stopped")
            return
        e, u_raw, P = control(self.ctrl, self.plant, T, I, Tm)
        self.mon_update(e)
        # heater saturation event
        if u_raw > self.plant.P_max and self.ctrl.heater_on:
            self.sat_time += self.h
        else:
            self.sat_time = 0.0
        # comfort / alarm events
        if T < BAND_LO or T > BAND_HI:
            self.t_out_of_band += self.h
        prev = self.alarm
        self.alarm = ("CHICKS CHILLED" if T < CHILL_T else
                      "HEAT STRESS" if T > HEAT_T else "")
        if self.alarm and self.alarm != prev:
            self.log(self.alarm)
        # target-reached event
        self.settled_time = self.settled_time + self.h if abs(e) < TOL else 0.0
        if self.settled_time >= HOLD and self.settled_time - self.h < HOLD:
            self.log("target reached (|e| < 0.5 K for 5 min)")
        # history for the plot
        if self.t >= self.next_sample:
            self.next_sample += SAMPLE_DT
            self.hist.append((self.t, T, self.amb_now, P, self.ctrl.T_set))
            self.err_hist.append(e)

    def advance(self, real_dt):
        if self.paused or self.failed:
            return
        budget = self.speed * real_dt + self.carry
        n = int(budget // self.h)
        self.carry = budget - n * self.h
        for _ in range(min(n, 4000)):
            self.step_once()
            if self.failed:
                break

    # -- derived read-outs -------------------------------------------------------
    @property
    def T(self):
        return float(self.y[0])

    def power(self):
        return control(self.ctrl, self.plant, *self.y)[2]

    def ss_error(self):
        return float(np.mean(self.err_hist)) if self.err_hist else 0.0

    # -- user actions ----------------------------------------------------------------
    def set_gain(self, name, value):
        """Change a gain while keeping the integral contribution Ki*I continuous."""
        c = self.ctrl
        if name == "Ki":
            if c.Ki > 0 and value > 0:
                self.y[1] *= c.Ki / value
            elif c.Ki == 0 and value > 0:           # bumpless start of integral action
                e, _, P = control(c, self.plant, *self.y)
                self.y[1] = (P - c.Kp * e) / value
        setattr(c, name, value)

    def cycle_mode(self):
        c = self.ctrl
        if c.name == "P":
            self.set_gain("Ki", 0.01)
        elif c.name == "PI":
            self.set_gain("Kd", 3000.0)
        else:
            self.set_gain("Kd", 0.0)
            self.set_gain("Ki", 0.0)
        self.mon_start(f"controller -> {c.name}")


def do_key(sim, key, K):
    """Map a key to a simulation action (K is the pygame key-constant namespace)."""
    c, p = sim.ctrl, sim.plant
    if key == K.K_SPACE:
        sim.paused = not sim.paused
    elif key == K.K_r:
        sim.reset()
    elif key == K.K_1:
        sim.method = "euler"
    elif key == K.K_2:
        sim.method = "rk4"
    elif key == K.K_LEFTBRACKET:
        sim.h = max(0.5, sim.h / 2)
    elif key == K.K_RIGHTBRACKET:
        sim.h = min(240.0, sim.h * 2)
    elif key == K.K_MINUS:
        sim.speed = max(30.0, sim.speed / 2)
    elif key == K.K_EQUALS:
        sim.speed = min(7200.0, sim.speed * 2)
    elif key == K.K_UP:
        c.T_set = min(40.0, c.T_set + 0.5); sim.mon_start(f"target {c.T_set:.1f} C")
    elif key == K.K_DOWN:
        c.T_set = max(25.0, c.T_set - 0.5); sim.mon_start(f"target {c.T_set:.1f} C")
    elif key == K.K_m:
        sim.cycle_mode()
    elif key == K.K_q:
        c.Kp = min(100.0, c.Kp * 1.25)
    elif key == K.K_a:
        c.Kp = max(0.5, c.Kp / 1.25)
    elif key == K.K_w:
        sim.set_gain("Ki", min(0.5, (c.Ki or 0.0033) * 1.5))
    elif key == K.K_s:
        sim.set_gain("Ki", max(0.0, c.Ki / 1.5) if c.Ki > 1e-4 else 0.0)
    elif key == K.K_e:
        c.Kd = (c.Kd * 1.5) if c.Kd > 0 else 1000.0
    elif key == K.K_d:
        c.Kd = (c.Kd / 1.5) if c.Kd > 1000 else 0.0
    elif key == K.K_n:
        c.antiwindup = not c.antiwindup
    elif key == K.K_F1:
        sim.amb_set = WEATHER["day"]; sim.mon_start("clear day 25 C")
    elif key == K.K_F2:
        sim.amb_set = WEATHER["night"]; sim.mon_start("cold night 12 C")
    elif key == K.K_F3:
        sim.rain_set = 0.0 if sim.rain_set > 0.5 else 1.0
        sim.mon_start("rain" if sim.rain_set > 0.5 else "rain stops")
    elif key == K.K_LEFT:
        sim.amb_set = max(-5.0, sim.amb_set - 1.0); sim.mon_start(f"ambient {sim.amb_set:.0f} C")
    elif key == K.K_RIGHT:
        sim.amb_set = min(40.0, sim.amb_set + 1.0); sim.mon_start(f"ambient {sim.amb_set:.0f} C")
    elif key == K.K_z:
        p.P_max = max(20.0, p.P_max - 10.0); sim.mon_start(f"heater capacity {p.P_max:.0f} W")
    elif key == K.K_x:
        p.P_max = min(400.0, p.P_max + 10.0); sim.mon_start(f"heater capacity {p.P_max:.0f} W")
    elif key == K.K_c:
        p.R = max(0.05, p.R - 0.02); sim.mon_start(f"insulation R = {p.R:.2f} K/W")
    elif key == K.K_v:
        p.R = min(0.80, p.R + 0.02); sim.mon_start(f"insulation R = {p.R:.2f} K/W")
    elif key == K.K_b:
        c.heater_on = not c.heater_on
        sim.mon_start("heater OFF (fault)" if not c.heater_on else "heater restored")


# --------------------------------------------------------------------- graphics
class Chick:
    """A chick's position relaxes towards a spot chosen from the *numerical* temperature:
    cold -> huddle under the heater, comfortable -> spread out, hot -> flee to the walls."""

    def __init__(self, rng, box):
        x, y, w, h = box
        self.home = (x + 40 + rng.random() * (w - 80), y + 110 + rng.random() * (h - 150))
        self.huddle_r = 10 + rng.random() * 38
        self.huddle_a = rng.random() * math.tau
        self.edge = (x + 25 if self.home[0] < x + w / 2 else x + w - 25,
                     self.home[1])
        self.phase = rng.random() * math.tau
        self.pos = list(self.home)

    def update(self, T, heater_xy, dt, clock):
        a = min(max((T - CHILL_T) / (35.0 - CHILL_T), 0.0), 1.0)     # 0 huddle .. 1 spread
        b = min(max((T - 36.5) / (40.0 - 36.5), 0.0), 1.0)           # 0 .. 1 flee to the walls
        hx = heater_xy[0] + math.cos(self.huddle_a) * self.huddle_r
        hy = heater_xy[1] + 70 + math.sin(self.huddle_a) * self.huddle_r * 0.5
        tx = hx + (self.home[0] - hx) * a
        ty = hy + (self.home[1] - hy) * a
        tx += (self.edge[0] - tx) * b
        ty += (self.edge[1] - ty) * b
        wob = 1.5 + 4.0 * (T < CHILL_T)                               # shivering when cold
        tx += math.sin(clock * 3 + self.phase) * wob
        ty += math.cos(clock * 2.3 + self.phase) * wob * 0.5
        k = min(1.0, 2.5 * dt)
        self.pos[0] += (tx - self.pos[0]) * k
        self.pos[1] += (ty - self.pos[1]) * k


def lerp_color(c1, c2, s):
    s = min(max(s, 0.0), 1.0)
    return tuple(int(a + (b - a) * s) for a, b in zip(c1, c2))


def run_gui():
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Smart Brooder Controller - ODE simulation")
    clock = pygame.time.Clock()
    f_big = pygame.font.Font(None, 30)
    f_med = pygame.font.Font(None, 22)
    f_sm = pygame.font.Font(None, 19)

    sim = BrooderSim()
    rng = random.Random(7)
    box = (SCENE[0] + 40, SCENE[1] + 60, SCENE[2] - 80, SCENE[3] - 90)
    chicks = [Chick(rng, box) for _ in range(sim.plant.n_chicks)]
    heater_xy = (box[0] + box[2] // 2, box[1] + 18)
    show_help = True
    tclock = 0.0

    def txt(s, pos, font=f_med, color=(30, 30, 30)):
        screen.blit(font.render(s, True, color), pos)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        tclock += dt
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_h:
                    show_help = not show_help
                else:
                    do_key(sim, ev.key, pygame)
        sim.advance(dt)
        T, P = sim.T, sim.power()
        for ch in chicks:
            ch.update(T, heater_xy, dt, tclock)

        # ---------------- background -------------------------------------------
        screen.fill((236, 238, 240))
        sx, sy, sw, sh = SCENE
        sky = lerp_color((40, 60, 110), (150, 200, 240), (sim.amb_now - 5) / 25)
        if sim.rain_now > 0.05:
            sky = lerp_color(sky, (90, 95, 105), sim.rain_now * 0.8)
        pygame.draw.rect(screen, sky, SCENE, border_radius=8)
        if sim.rain_now > 0.05:                       # rain streaks (cosmetic, driven by rain state)
            for i in range(int(60 * sim.rain_now)):
                rx = sx + (i * 97 + int(tclock * 300)) % sw
                ry = sy + (i * 53 + int(tclock * 500)) % (box[1] - sy)
                pygame.draw.line(screen, (170, 190, 230), (rx, ry), (rx - 3, ry + 10), 1)
        txt(f"Outdoor: {sim.amb_now:4.1f} C" + ("  RAIN" if sim.rain_now > 0.5 else ""),
            (sx + 12, sy + 10), f_big, (255, 255, 255))

        # brooder box, colour tinted by temperature
        wall = lerp_color((90, 120, 200), (230, 120, 80), (T - 25) / 15)
        pygame.draw.rect(screen, (222, 196, 140), box, border_radius=10)
        pygame.draw.rect(screen, wall, box, 6, border_radius=10)

        # heater lamp with glow proportional to heater power
        glow = pygame.Surface((300, 300), pygame.SRCALPHA)
        frac = P / sim.plant.P_max
        for r, a in ((140, 28), (100, 40), (60, 60)):
            pygame.draw.circle(glow, (255, 140, 40, int(a * frac)), (150, 150), r)
        screen.blit(glow, (heater_xy[0] - 150, heater_xy[1] - 130))
        pygame.draw.rect(screen, (70, 70, 75), (heater_xy[0] - 30, heater_xy[1] - 12, 60, 14), border_radius=4)
        pygame.draw.circle(screen, lerp_color((90, 60, 50), (255, 120, 30), frac),
                           heater_xy, 11)
        if not sim.ctrl.heater_on:
            txt("HEATER FAULT", (heater_xy[0] - 52, heater_xy[1] - 36), f_med, (220, 30, 30))

        # chicks
        for ch in chicks:
            cx, cy = int(ch.pos[0]), int(ch.pos[1])
            body = (250, 215, 60)
            if T < CHILL_T:
                body = lerp_color(body, (150, 190, 255), (CHILL_T - T) / 4)
            elif T > HEAT_T - 1.5:
                body = lerp_color(body, (255, 150, 90), (T - HEAT_T + 1.5) / 3)
            pygame.draw.circle(screen, body, (cx, cy), 9)
            pygame.draw.circle(screen, body, (cx + 7, cy - 6), 5)
            pygame.draw.polygon(screen, (230, 130, 30), [(cx + 11, cy - 7), (cx + 16, cy - 6), (cx + 11, cy - 4)])
            pygame.draw.circle(screen, (20, 20, 20), (cx + 8, cy - 7), 1)

        # alarm / failure banners
        if sim.failed:
            pygame.draw.rect(screen, (170, 20, 20), (sx + 20, sy + sh // 2 - 28, sw - 40, 56), border_radius=8)
            txt(sim.failed, (sx + 32, sy + sh // 2 - 8), f_med, (255, 255, 255))
        elif sim.alarm:
            txt(sim.alarm, (sx + sw - 220, sy + 12), f_big, (255, 80, 80))
        elif sim.sat_time > 120:
            txt("HEATER SATURATED - cannot hold target", (sx + sw - 345, sy + 12), f_med, (255, 220, 90))
        elif sim.settled_time >= HOLD:
            txt("ON TARGET", (sx + sw - 140, sy + 12), f_big, (120, 255, 150))

        # ---------------- scrolling plot ---------------------------------------
        px, py, pw, ph = PLOT
        pygame.draw.rect(screen, (255, 255, 255), PLOT, border_radius=6)
        pygame.draw.rect(screen, (190, 190, 190), PLOT, 1, border_radius=6)
        top = (px + 48, py + 24, pw - 62, int(ph * 0.58))
        bot = (px + 48, py + 24 + int(ph * 0.58) + 12, pw - 62, int(ph * 0.24))
        tmin, tmax = 5.0, 45.0
        def ty(v): return top[1] + top[3] - (v - tmin) / (tmax - tmin) * top[3]
        pygame.draw.rect(screen, (225, 245, 225), (top[0], int(ty(BAND_HI)), top[2], int(ty(BAND_LO) - ty(BAND_HI))))
        for v in (10, 20, 30, 40):
            pygame.draw.line(screen, (225, 225, 225), (top[0], ty(v)), (top[0] + top[2], ty(v)))
            txt(f"{v}", (px + 10, ty(v) - 6), f_sm, (100, 100, 100))
        pygame.draw.rect(screen, (170, 170, 170), top, 1)
        pygame.draw.rect(screen, (170, 170, 170), bot, 1)
        txt("T (red)   target (black)   ambient (blue)", (top[0] + 6, py + 5), f_sm, (80, 80, 80))
        txt(f"heater W (0..{sim.plant.P_max:.0f})  - last 6 h", (bot[0] + 6, bot[1] + 3), f_sm, (80, 80, 80))
        if len(sim.hist) > 1:
            t_now = sim.hist[-1][0]
            def tx(t): return top[0] + top[2] - (t_now - t) / PLOT_SPAN * top[2]
            pts = [(tx(r[0]), ty(r[1])) for r in sim.hist]
            amb = [(tx(r[0]), ty(r[2])) for r in sim.hist]
            tgt = [(tx(r[0]), ty(r[4])) for r in sim.hist]
            pwr = [(tx(r[0]), bot[1] + bot[3] - r[3] / sim.plant.P_max * bot[3]) for r in sim.hist]
            pygame.draw.lines(screen, (0, 0, 0), False, tgt, 1)
            pygame.draw.lines(screen, (60, 110, 220), False, amb, 2)
            pygame.draw.lines(screen, (215, 50, 40), False, pts, 2)
            pygame.draw.lines(screen, (240, 140, 20), False, pwr, 2)

        # ---------------- right-hand instrument panel ----------------------------
        gx, gy, gh = 770, 40, 290
        gmin, gmax = 15.0, 45.0
        def gyv(v): return gy + gh - (v - gmin) / (gmax - gmin) * gh
        pygame.draw.rect(screen, (255, 255, 255), (gx - 6, gy - 6, 40, gh + 12), border_radius=18)
        pygame.draw.rect(screen, (225, 245, 225), (gx, gyv(BAND_HI), 28, gyv(BAND_LO) - gyv(BAND_HI)))
        merc = lerp_color((60, 110, 230), (230, 50, 40), (T - 20) / 20)
        pygame.draw.rect(screen, merc, (gx + 8, gyv(min(max(T, gmin), gmax)), 12,
                                        gy + gh - gyv(min(max(T, gmin), gmax))))
        pygame.draw.circle(screen, merc, (gx + 14, gy + gh + 16), 17)
        pygame.draw.line(screen, (0, 0, 0), (gx - 12, gyv(sim.ctrl.T_set)), (gx + 38, gyv(sim.ctrl.T_set)), 2)
        for v in (20, 25, 30, 35, 40):
            txt(str(v), (gx + 42, gyv(v) - 6), f_sm, (90, 90, 90))
        txt(f"{T:5.2f} C", (gx - 14, gy + gh + 40), f_big, merc)

        x0, y0, dy = 880, 36, 21
        e = sim.ctrl.T_set - T
        c, p = sim.ctrl, sim.plant
        need = required_power(p, c.T_set, sim.amb_now, sim.rain_now)
        rec = sim.mon["recovery"]
        lines = [
            (f"t = {sim.fmt_time()}   x{sim.speed:g}   {'PAUSED' if sim.paused else ''}", f_med),
            (f"Solver: {sim.method.upper()}   h = {sim.h:g} s", f_med),
            (f"Controller: {c.name}   target {c.T_set:.1f} C", f_med),
            (f"Kp={c.Kp:.1f}  Ki={c.Ki:.4f}  Kd={c.Kd:.0f}", f_sm),
            (f"anti-windup: {'on' if c.antiwindup else 'off'}", f_sm),
            (f"Ambient {sim.amb_now:.1f} C  rain {sim.rain_now:.1f}", f_med),
            (f"Insulation R={p.R:.2f} K/W (UA={1 / p.R:.1f} W/K)", f_sm),
            (f"Heater {P:5.1f} / {p.P_max:.0f} W   need ~{need:.0f} W", f_med),
            (f"Error e = {e:+.2f} K   Ki*I = {c.Ki * sim.y[1]:+.1f} W", f_med),
            (f"Last disturbance: {sim.mon['why']}", f_sm),
            (f"  peak dev {sim.mon['peak']:.2f} K   recovery " +
             (f"{rec / 60:.0f} min" if rec is not None else "..."), f_sm),
            (f"Steady-state error (10 min mean): {sim.ss_error():+.3f} K", f_sm),
            (f"Time outside {BAND_LO:.0f}-{BAND_HI:.0f} C: {sim.t_out_of_band / 60:.0f} min", f_sm),
        ]
        for i, (s, fnt) in enumerate(lines):
            txt(s, (x0, y0 + i * dy), fnt)
        # heater power bar
        bx, by, bw, bh = 770, 400, 390, 20
        pygame.draw.rect(screen, (255, 255, 255), (bx, by, bw, bh))
        pygame.draw.rect(screen, (240, 140, 20), (bx, by, int(bw * P / p.P_max), bh))
        pygame.draw.rect(screen, (150, 150, 150), (bx, by, bw, bh), 1)
        txt("heater power", (bx + 4, by + 2), f_sm)
        # event log
        txt("Events:", (bx, 432), f_med)
        for i, s in enumerate(sim.events):
            txt(s, (bx, 454 + i * 17), f_sm, (60, 60, 60))
        # key help
        if show_help:
            keys = ["SPACE pause  R reset  H hide help  ESC quit",
                    "1/2 Euler/RK4   [ ] step h   -/= speed",
                    "UP/DOWN target   M mode P>PI>PID   N anti-windup",
                    "Q/A Kp  W/S Ki  E/D Kd",
                    "F1 clear day  F2 cold night  F3 rain on/off",
                    "LEFT/RIGHT ambient +-1 C",
                    "Z/X heater capacity -/+10 W",
                    "C/V insulation R -/+0.02 K/W   B heater fault"]
            for i, s in enumerate(keys):
                txt(s, (bx, 560 + i * 17), f_sm, (40, 40, 120))
        pygame.display.flip()
    pygame.quit()


# ----------------------------------------------------------------------- selftest
def selftest():
    """Headless run of the simulation core + every key handler."""
    import types
    K = types.SimpleNamespace()
    names = ("SPACE r 1 2 LEFTBRACKET RIGHTBRACKET MINUS EQUALS UP DOWN m q a w s e d n "
             "F1 F2 F3 LEFT RIGHT z x c v b").split()
    for i, n in enumerate(names):
        setattr(K, "K_" + n, i + 1000)
    sim = BrooderSim()
    for n in names:
        do_key(sim, getattr(K, "K_" + n), K)
        sim.advance(0.1)
        if n == "SPACE":
            do_key(sim, K.K_SPACE, K)           # unpause again
    sim.reset()
    for _ in range(600):
        sim.advance(1 / 60)
    print("selftest ok   T = %.2f C   P = %.1f W   t = %s" % (sim.T, sim.power(), sim.fmt_time()))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        run_gui()
