"""Reproduce every experiment/plot in the report.   Run:  python experiments.py
Outputs go to ./results (PNG figures + CSV tables)."""
import csv, os
from dataclasses import replace
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from brooder.model import (Plant, Controller, make_rhs, heater_power,
                           required_power, equilibrium_T)
from brooder.solvers import integrate
from brooder.analytic import (open_loop_T, pi_closed_loop, pi_poles)
from brooder.metrics import (recovery_time, steady_state_error, peak_deviation,
                             overshoot_pct, rise_time)

OUT = "results"
os.makedirs(OUT, exist_ok=True)
H = 3600.0
plt.rcParams.update({"figure.dpi": 130, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})


# ----------------------------------------------------------------- helpers
def ramp(t, t0, dur, a, b):
    """Piecewise-linear transition a -> b starting at t0 over dur seconds."""
    s = min(max((t - t0) / dur, 0.0), 1.0)
    return a + (b - a) * s


def settle(plant, ctrl, T_a, rain=0.0, hours=8, h=2.0):
    """Pre-run the loop to its equilibrium so a disturbance starts from steady state."""
    f = make_rhs(plant, ctrl, lambda t: T_a, lambda t: rain)
    _, Y = integrate(f, np.array([ctrl.T_set, 0.0, ctrl.T_set]), 0, hours * H, h, "rk4")
    return Y[-1]


def run(plant, ctrl, ambient, rain, y0, t_end, h=2.0, method="rk4"):
    f = make_rhs(plant, ctrl, ambient, rain)
    t, Y = integrate(f, y0, 0.0, t_end, h, method)
    P = np.array([heater_power(plant, ctrl, y) for y in Y])
    return t, Y, P


def save_csv(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def fmt_rec(x):
    return "never" if np.isnan(x) else f"{x/60:.0f}"


def cold_night(plant, ctrl, T_pre=25.0, T_night=12.0, rain_on=False, t_end=6 * H):
    """Standard disturbance: ambient falls T_pre -> T_night over 30 min (optionally with rain)."""
    y0 = settle(plant, ctrl, T_pre, 0.0)
    amb = lambda t: ramp(t, 0, 1800, T_pre, T_night)
    rn = (lambda t: ramp(t, 0, 300, 0.0, 1.0)) if rain_on else (lambda t: 0.0)
    t, Y, P = run(plant, ctrl, amb, rn, y0, t_end)
    return t, Y, P, amb


def metrics(plant, ctrl, t, Y, tol=0.5):
    e = ctrl.T_set - Y[:, 0]
    return (peak_deviation(t, e, 0), recovery_time(t, e, 0, tol),
            steady_state_error(t, e, 1800))


# ------------------------------------------------- Fig 1: baseline 12-hour day
def baseline():
    pl, c = Plant(), Controller(Kp=8, Ki=0.01, Kd=0)
    y0 = settle(pl, c, 25.0)
    amb = lambda t: (ramp(t, 2 * H, H, 25, 12) if t < 9 * H else ramp(t, 9 * H, H, 12, 22))
    rn = lambda t: ramp(t, 5 * H, 300, 0, 1) if t < 7 * H else ramp(t, 7 * H, 300, 1, 0)
    t, Y, P = run(pl, c, amb, rn, y0, 12 * H)
    fig, ax = plt.subplots(2, 1, figsize=(7, 4.6), sharex=True,
                           gridspec_kw={"height_ratios": [2, 1]})
    ax[0].plot(t / H, Y[:, 0], "C3", lw=1.8, label="brooder T")
    ax[0].axhline(c.T_set, color="k", ls="--", lw=0.8, label="target")
    ax[0].plot(t / H, [amb(x) for x in t], "C0", lw=1.2, label="ambient")
    ax[0].axvspan(5, 7, color="C9", alpha=0.25, label="rain")
    ax[0].set_ylabel("temperature (°C)"); ax[0].legend(ncol=4, loc="lower center", fontsize=8)
    ax[1].plot(t / H, P, "C1"); ax[1].axhline(pl.P_max, color="grey", ls=":")
    ax[1].set_ylabel("heater power (W)"); ax[1].set_xlabel("time (h)")
    ax[0].set_title("Baseline: day → cold night → rain → dawn  (PI, Kp=8, Ki=0.01, RK4)")
    fig.tight_layout(); fig.savefig(f"{OUT}/fig1_baseline.png"); plt.close(fig)


# ------------------------------------------- E1: P vs PI vs PID, two disturbances
def exp_controllers():
    pl = Plant()
    cases = {"P (Kp=8)": Controller(Kp=8, Ki=0, Kd=0),
             "PI (8, 0.01)": Controller(Kp=8, Ki=0.01, Kd=0),
             "PID (8, 0.01, 3000)": Controller(Kp=8, Ki=0.01, Kd=3000),
             "PI fast (20, 0.03)": Controller(Kp=20, Ki=0.03, Kd=0)}
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.0), sharey=True)
    for name, c in cases.items():
        for k, (label, kw) in enumerate([("cold night 25→12 °C", dict()),
                                         ("rain at 15 °C", dict(rain=True))]):
            if label.startswith("cold"):
                t, Y, P, _ = cold_night(pl, c)
            else:   # rain step at constant 15 deg C
                y0 = settle(pl, c, 15.0)
                t, Y, P = run(pl, c, lambda t: 15.0, lambda t: ramp(t, 0, 300, 0, 1), y0, 6 * H)
            pk, rec, sse = metrics(pl, c, t, Y)
            rows.append([name, label, round(pk, 2), fmt_rec(rec), round(sse, 3)])
            ax[k].plot(t / H, Y[:, 0], label=name)
            ax[k].set_title(label)
    for a in ax:
        a.axhline(35, color="k", ls="--", lw=0.8); a.set_xlabel("time (h)")
    ax[0].set_ylabel("brooder T (°C)"); ax[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig2_controllers.png"); plt.close(fig)
    save_csv("e1_controllers.csv",
             ["controller", "disturbance", "peak_dev_K", "recovery_min(|e|<0.5K)", "steady_err_K"], rows)
    return rows


# ------------------------------------------------------- E2: heater capacity
def exp_capacity():
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.0))
    for Pm in [60, 100, 150, 250]:
        pl, c = Plant(P_max=Pm), Controller(Kp=8, Ki=0.01)
        t, Y, P, amb = cold_night(pl, c, T_night=12.0, rain_on=True)
        pk, rec, sse = metrics(pl, c, t, Y)
        need = required_power(pl, c.T_set, 12.0, 1.0)
        rows.append([Pm, round(need, 1), round(pk, 2), fmt_rec(rec), round(sse, 2),
                     round(Y[-1, 0], 1)])
        ax[0].plot(t / H, Y[:, 0], label=f"P_max={Pm} W"); ax[1].plot(t / H, P)
    ax[0].axhline(35, color="k", ls="--", lw=0.8); ax[0].legend(fontsize=7)
    ax[0].set_ylabel("brooder T (°C)"); ax[1].set_ylabel("heater power (W)")
    for a in ax: a.set_xlabel("time (h)")
    ax[0].set_title("12 °C + rain: temperature"); ax[1].set_title("heater command (saturates)")
    fig.tight_layout(); fig.savefig(f"{OUT}/fig3_capacity.png"); plt.close(fig)
    save_csv("e2_capacity.csv", ["P_max_W", "power_needed_W", "peak_dev_K",
                                 "recovery_min", "steady_err_K", "final_T_C"], rows)
    return rows


# ------------------------------------------------------------- E3: insulation
def exp_insulation():
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.0))
    for R in [0.10, 0.20, 0.40]:
        pl, c = Plant(R=R), Controller(Kp=8, Ki=0.01)
        t, Y, P, _ = cold_night(pl, c, T_night=12.0)
        pk, rec, sse = metrics(pl, c, t, Y)
        need = required_power(pl, c.T_set, 12.0)
        tau = pl.R * pl.C
        # power-failure hold time: heater off at 35 C, ambient 12 C, time to reach 30 C
        Tinf = equilibrium_T(pl, 0.0, 12.0)
        t30 = -tau * np.log((30 - Tinf) / (35 - Tinf))
        rows.append([R, round(1 / R, 1), round(tau / 60), round(need, 1), round(pk, 2),
                     fmt_rec(rec), round(sse, 2), round(t30 / 60)])
        ax[0].plot(t / H, Y[:, 0], label=f"R={R} K/W"); ax[1].plot(t / H, P)
    ax[0].axhline(35, color="k", ls="--", lw=0.8); ax[0].legend(fontsize=7)
    ax[0].set_ylabel("brooder T (°C)"); ax[1].set_ylabel("heater power (W)")
    ax[0].set_title("cold night 12 °C: temperature"); ax[1].set_title("heater power")
    for a in ax: a.set_xlabel("time (h)")
    fig.tight_layout(); fig.savefig(f"{OUT}/fig4_insulation.png"); plt.close(fig)
    save_csv("e3_insulation.csv", ["R_K_per_W", "UA_W_per_K", "tau_min", "power_needed_W",
             "peak_dev_K", "recovery_min", "steady_err_K", "min_until_30C_if_heater_fails"], rows)
    return rows


# ------------------------------------------------------------ E4: tuning grid
def exp_tuning():
    pl = Plant()
    Kps, Kis = [2, 8, 20], [0.002, 0.01, 0.05]
    rec_grid = np.full((3, 3), np.nan); pk_grid = np.zeros((3, 3)); zeta = np.zeros((3, 3))
    rows = []
    for i, Kp in enumerate(Kps):
        for j, Ki in enumerate(Kis):
            c = Controller(Kp=Kp, Ki=Ki)
            t, Y, P, _ = cold_night(pl, c, t_end=8 * H)
            pk, rec, sse = metrics(pl, c, t, Y)
            _, wn, z = pi_poles(pl, c)
            rec_grid[i, j], pk_grid[i, j], zeta[i, j] = rec / 60, pk, z
            rows.append([Kp, Ki, round(z, 2), round(pk, 2), fmt_rec(rec), round(sse, 4)])
    fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.0))
    for a, G, ttl in [(ax[0], pk_grid, "peak deviation (K)"), (ax[1], rec_grid, "recovery time (min)")]:
        im = a.imshow(G, origin="lower", cmap="viridis_r")
        a.set_xticks(range(3)); a.set_xticklabels(Kis); a.set_yticks(range(3)); a.set_yticklabels(Kps)
        a.set_xlabel("Ki (W/(K·s))"); a.set_ylabel("Kp (W/K)"); a.set_title(ttl); a.grid(False)
        for (r, cc), v in np.ndenumerate(G):
            a.text(cc, r, "never" if np.isnan(v) else f"{v:.1f}" if G is pk_grid else f"{v:.0f}",
                   ha="center", va="center", fontsize=8,
                   color="k" if v < (np.nanmax(G) + np.nanmin(G)) / 2 else "w")
        fig.colorbar(im, ax=a, shrink=0.8)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig5_tuning.png"); plt.close(fig)
    save_csv("e4_tuning.csv", ["Kp", "Ki", "zeta_unsat", "peak_dev_K", "recovery_min", "steady_err_K"], rows)

    # Derivative term
    drows = []
    for Kd in [0, 3000, 12000]:
        c = Controller(Kp=8, Ki=0.01, Kd=Kd)
        t, Y, P, _ = cold_night(pl, c)
        pk, rec, sse = metrics(pl, c, t, Y)
        drows.append([Kd, round(pk, 2), fmt_rec(rec), round(sse, 4)])
    save_csv("e4_derivative.csv", ["Kd", "peak_dev_K", "recovery_min", "steady_err_K"], drows)
    return rows, drows


# ------------------------------------------------ E5: cold start & anti-windup
def exp_windup():
    pl = Plant()
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.0))
    for aw in [False, True]:
        c = Controller(Kp=8, Ki=0.05, antiwindup=aw)
        f = make_rhs(pl, c, lambda t: 20.0)
        t, Y = integrate(f, np.array([20.0, 0.0, 20.0]), 0, 6 * H, 2.0, "rk4")
        P = np.array([heater_power(pl, c, y) for y in Y])
        os_ = overshoot_pct(Y[:, 0], 20.0, c.T_set)
        e = c.T_set - Y[:, 0]
        rows.append(["on" if aw else "off", round(rise_time(t, Y[:, 0], 20, c.T_set) / 60),
                     round(os_, 1), round(Y[:, 0].max() - c.T_set, 2), fmt_rec(recovery_time(t, e, 0))])
        ax[0].plot(t / H, Y[:, 0], label=f"anti-windup {'on' if aw else 'off'}")
        ax[1].plot(t / H, P)
    ax[0].axhline(35, color="k", ls="--", lw=0.8); ax[0].legend(fontsize=7)
    ax[0].set_ylabel("brooder T (°C)"); ax[1].set_ylabel("heater power (W)")
    for a in ax: a.set_xlabel("time (h)")
    ax[0].set_title("cold start 20 → 35 °C (Ki=0.05)")
    fig.tight_layout(); fig.savefig(f"{OUT}/fig6_windup.png"); plt.close(fig)
    save_csv("e5_windup.csv", ["anti_windup", "rise_90pct_min", "overshoot_pct",
                               "peak_above_target_K", "recovery_min"], rows)
    return rows


# ------------------------------------------------ E6: Euler vs RK4 comparison
def exp_numerics():
    pl = Plant()
    # (a) PI loop vs exact analytical solution (unsaturated, constant ambient)
    c = Controller(Kp=8, Ki=0.01, Kd=0)
    Ta, T0, tend = 20.0, 30.0, 4 * H
    f = make_rhs(pl, c, lambda t: Ta)
    y0 = np.array([T0, 0.0, T0])
    rows, errs = [], {"euler": [], "rk4": []}
    hs = [300.0, 150.0, 75.0, 30.0]
    for m in ["euler", "rk4"]:
        prev, hprev = None, None
        for h in hs:
            t, Y = integrate(f, y0, 0, tend, h, m)
            ref = pi_closed_loop(t, T0, 0.0, pl, c, Ta)
            err = np.max(np.abs(Y[:, 0] - ref[:, 0]))
            order = "" if prev is None else f"{np.log(prev / err) / np.log(hprev / h):.2f}"
            rows.append([m, h, f"{err:.3e}", order]); errs[m].append(err); prev, hprev = err, h
    save_csv("e6a_convergence_PI.csv", ["method", "h_s", "max_error_K", "observed_order"], rows)

    # (b) PID (derivative filter) vs refined RK4 reference (h = 0.1 s)
    cd = Controller(Kp=8, Ki=0.01, Kd=3000, tau_d=60.0)
    fd = make_rhs(pl, cd, lambda t: Ta)
    tref, Yref = integrate(fd, y0, 0, tend, 0.1, "rk4")
    rows2 = []
    for m in ["euler", "rk4"]:
        for h in [40.0, 20.0, 10.0, 5.0]:
            t, Y = integrate(fd, y0, 0, tend, h, m)
            ref = np.interp(t, tref, Yref[:, 0])
            rows2.append([m, h, f"{np.max(np.abs(Y[:, 0] - ref)):.3e}"])
    save_csv("e6b_convergence_PID.csv", ["method", "h_s", "max_error_K"], rows2)

    fig, ax = plt.subplots(1, 2, figsize=(7.5, 3.0))
    ax[0].loglog(hs, errs["euler"], "o-", label="Euler"); ax[0].loglog(hs, errs["rk4"], "s-", label="RK4")
    ax[0].loglog(hs, 0.0017 * np.array(hs), "k:", lw=0.8, label="slope 1")
    ax[0].loglog(hs, 4.5e-10 * np.array(hs) ** 4, "k--", lw=0.8, label="slope 4")
    ax[0].set_xticks(hs); ax[0].set_xticklabels([int(x) for x in hs]); ax[0].minorticks_off()
    ax[0].set_xlabel("step size h (s)"); ax[0].set_ylabel("max |T - T_exact| (K)")
    ax[0].set_title("convergence vs exact PI solution"); ax[0].legend(fontsize=7)

    # (c) stability: derivative filter makes the system stiff -> Euler needs h < 2*tau_d
    for m, h, col in [("euler", 100.0, "C3"), ("rk4", 100.0, "C2")]:
        t, Y = integrate(fd, y0, 0, 3 * H, h, m)
        ax[1].plot(t / H, Y[:, 0], col, label=f"{m}, h={h:.0f} s")
    ax[1].plot(tref[tref <= 3 * H] / H, Yref[tref <= 3 * H, 0], "k--", lw=0.8, label="reference")
    ax[1].set_ylim(25, 45); ax[1].set_xlabel("time (h)"); ax[1].set_ylabel("T (°C)")
    ax[1].set_title("PID (tau_d = 60 s): Euler fails at h = 100 s"); ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig7_numerics.png"); plt.close(fig)
    return rows, rows2


# ----------------------------------------------- validation: open loop exact
def validation():
    pl = Plant()
    f = make_rhs(pl, Controller(Kp=0, Ki=0, Kd=0), lambda t: 15.0)
    # open loop with constant 100 W: make heater constant by Kp trick -> use direct ODE instead
    g = 1.0 / pl.R
    rhs = lambda t, y: np.array([(100.0 + pl.Q_chicks - g * (y[0] - 15.0)) / pl.C])
    rows = []
    for m in ["euler", "rk4"]:
        for h in [600.0, 300.0, 150.0]:
            t, Y = integrate(rhs, np.array([20.0]), 0, 4 * H, h, m)
            ex = open_loop_T(t, 20.0, pl, 100.0, 15.0)
            rows.append([m, h, f"{np.max(np.abs(Y[:, 0] - ex)):.3e}"])
    save_csv("validation_open_loop.csv", ["method", "h_s", "max_error_K"], rows)
    return rows


if __name__ == "__main__":
    baseline()
    out = {"E1": exp_controllers(), "E2": exp_capacity(), "E3": exp_insulation(),
           "E4": exp_tuning(), "E5": exp_windup(), "E6": exp_numerics(),
           "VAL": validation()}
    for k, v in out.items():
        print("==", k)
        for r in (v if isinstance(v, list) else v):
            print(r)
    print("figures and tables written to ./results")
