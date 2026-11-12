"""Analytical reference solutions used to validate Euler/RK4.

1. Open loop, constant power and constant ambient (scalar linear ODE):
       T(t) = T_inf + (T0 - T_inf) exp(-t/tau),   tau = C/g,  T_inf = T_a + (P+Q)/g

2. Closed loop with PI control, constant ambient/rain, heater NOT saturated, Kd = 0.
   Then x = [T, I] obeys the linear system x' = A x + b, solved exactly through
   the eigen-decomposition  x(t) = x_ss + V exp(Lambda t) V^-1 (x0 - x_ss).
"""
import numpy as np


def open_loop_T(t, T0, plant, P, T_a, rain=0.0):
    g = (1.0 + plant.rain_loss * rain) / plant.R
    tau = plant.C / g
    T_inf = T_a + (P + plant.Q_chicks) / g
    return T_inf + (T0 - T_inf) * np.exp(-np.asarray(t) / tau)


def pi_matrices(plant, ctrl, T_a, rain=0.0):
    g = (1.0 + plant.rain_loss * rain) / plant.R
    C = plant.C
    A = np.array([[-(ctrl.Kp + g) / C, ctrl.Ki / C],
                  [-1.0, 0.0]])
    b = np.array([(ctrl.Kp * ctrl.T_set + g * T_a + plant.Q_chicks) / C,
                  ctrl.T_set])
    return A, b


def pi_closed_loop(t, T0, I0, plant, ctrl, T_a, rain=0.0):
    """Exact [T(t), I(t)] for the unsaturated PI loop. Returns array (len(t), 2)."""
    A, b = pi_matrices(plant, ctrl, T_a, rain)
    x_ss = -np.linalg.solve(A, b)
    lam, V = np.linalg.eig(A)
    c = np.linalg.solve(V, np.array([T0, I0]) - x_ss)
    t = np.asarray(t)
    X = (V @ (c[:, None] * np.exp(np.outer(lam, t)))).real.T + x_ss
    return X


def pi_poles(plant, ctrl, rain=0.0):
    """Closed-loop poles, natural frequency and damping ratio of the unsaturated PI loop."""
    A, _ = pi_matrices(plant, ctrl, 0.0, rain)
    lam = np.linalg.eigvals(A)
    wn = np.sqrt(ctrl.Ki / plant.C)
    g = (1.0 + plant.rain_loss * rain) / plant.R
    zeta = (ctrl.Kp + g) / (2.0 * np.sqrt(plant.C * ctrl.Ki))
    return lam, wn, zeta
