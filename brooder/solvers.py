"""Hand-written explicit Euler and classical RK4 integrators (no black-box ODE solver).

Both advance dy/dt = f(t, y) by one step of size h.  `y` is a NumPy array.
Only NumPy array arithmetic is used - the numerical schemes are written out here.
"""
import numpy as np


def euler_step(f, t, y, h):
    """Explicit (forward) Euler, global order 1:  y_{n+1} = y_n + h f(t_n, y_n)."""
    return y + h * f(t, y)


def rk4_step(f, t, y, h):
    """Classical 4th-order Runge-Kutta, global order 4."""
    k1 = f(t, y)
    k2 = f(t + 0.5 * h, y + 0.5 * h * k1)
    k3 = f(t + 0.5 * h, y + 0.5 * h * k2)
    k4 = f(t + h, y + h * k3)
    return y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


STEPPERS = {"euler": euler_step, "rk4": rk4_step}


def integrate(f, y0, t0, t_end, h, method="rk4"):
    """Integrate from t0 to t_end with (nearly) fixed step h.

    The last step is shortened so that the final time is hit exactly.
    Returns (t, Y) with Y.shape == (len(t), len(y0)).
    """
    step = STEPPERS[method]
    n = int(np.ceil((t_end - t0) / h - 1e-12))
    t = np.empty(n + 1)
    Y = np.empty((n + 1, len(y0)))
    t[0], Y[0] = t0, y0
    for i in range(n):
        hi = min(h, t_end - t[i])
        Y[i + 1] = step(f, t[i], Y[i], hi)
        t[i + 1] = t[i] + hi
    return t, Y
