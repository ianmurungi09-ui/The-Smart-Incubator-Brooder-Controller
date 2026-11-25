"""Performance measures for regulation: recovery time, steady-state error, peak deviation."""
import numpy as np


def recovery_time(t, e, t_dist, tol=0.5):
    """Time after t_dist after which |e| stays within tol.  nan if it never settles."""
    t, e = np.asarray(t), np.asarray(e)
    m = t >= t_dist
    tt, ee = t[m], e[m]
    out = np.where(np.abs(ee) > tol)[0]
    if len(out) == 0:
        return 0.0
    if out[-1] == len(tt) - 1:
        return float("nan")
    return float(tt[out[-1] + 1] - t_dist)


def steady_state_error(t, e, window):
    """Mean error over the last `window` seconds."""
    t, e = np.asarray(t), np.asarray(e)
    return float(np.mean(e[t >= t[-1] - window]))


def peak_deviation(t, e, t_dist):
    t, e = np.asarray(t), np.asarray(e)
    m = t >= t_dist
    return float(np.max(np.abs(e[m])))


def overshoot_pct(T, T0, T_set):
    """Overshoot of a heat-up (set-point) response, % of the step size."""
    return float(max(0.0, (np.max(T) - T_set) / (T_set - T0)) * 100.0)


def rise_time(t, T, T0, T_set, frac=0.9):
    idx = np.where(np.asarray(T) >= T0 + frac * (T_set - T0))[0]
    return float(t[idx[0]]) if len(idx) else float("nan")
