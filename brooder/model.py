"""Lumped thermal model of a poultry brooder + heater controller, as a first-order ODE system.

Physics (lumped capacitance, one air/bedding temperature T):

    C dT/dt = P(t) + Q_chicks - g(t) * (T - T_a(t)),        g = (1 + k_rain*rain(t)) / R

  C        thermal capacity of air + bedding + enclosure          [J/K]
  R        thermal resistance of the insulation (to ambient)      [K/W]   (UA = 1/R)
  T_a(t)   outdoor/ambient temperature (external forcing)         [deg C]
  rain(t)  0..1 wetness/wind index; raises heat loss by k_rain    [-]
  Q_chicks metabolic heat from the chicks (n * q)                 [W]
  P        heater power = saturate(u, 0, P_max)                   [W]

Controller (PID, written explicitly as ODE states so Euler/RK4 integrate everything):

  e        = T_set - T
  I'       = e                      (+ back-calculation anti-windup)
  Tm'      = (T - Tm)/tau_d         (low-pass filter; (T - Tm)/tau_d ~ dT/dt)
  u        = Kp e + Ki I - Kd (T - Tm)/tau_d       (derivative on measurement)

State vector y = [T, I, Tm].
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class Plant:
    C: float = 8000.0        # J/K
    R: float = 0.20          # K/W  -> UA = 5 W/K
    rain_loss: float = 0.30  # fractional extra heat loss when rain = 1
    q_chick: float = 0.4     # W per chick
    n_chicks: int = 20
    P_max: float = 150.0     # W, heater capacity

    @property
    def Q_chicks(self):
        return self.q_chick * self.n_chicks


@dataclass
class Controller:
    T_set: float = 35.0      # deg C target
    Kp: float = 8.0          # W/K
    Ki: float = 0.01         # W/(K s)
    Kd: float = 0.0          # W s/K
    tau_d: float = 60.0      # s, derivative filter time constant
    antiwindup: bool = True
    heater_on: bool = True   # False models a power failure / heater fault
    mode: str = "automatic"
    manual_power_pct: float = 50.0

    @property
    def name(self):
        s = "P"
        if self.Ki > 0:
            s += "I"
        if self.Kd > 0:
            s += "D"
        return s


def control(ctrl, plant, T, I, Tm):
    """Return (e, u_raw, P): error, unsaturated command, saturated heater power."""
    e = ctrl.T_set - T
    d_est = (T - Tm) / ctrl.tau_d
    u_raw = (ctrl.manual_power_pct / 100.0 * plant.P_max if ctrl.mode == "manual"
             else ctrl.Kp * e + ctrl.Ki * I - ctrl.Kd * d_est)
    P = min(max(u_raw, 0.0), plant.P_max) if ctrl.heater_on else 0.0
    return e, u_raw, P


def make_rhs(plant, ctrl, ambient, rain=lambda t: 0.0):
    """Build f(t, y) for y = [T, I, Tm].  Parameters are read at every call, so
    the interactive program can change them live."""

    def f(t, y):
        T, I, Tm = y
        e, u_raw, P = control(ctrl, plant, T, I, Tm)
        g = (1.0 + plant.rain_loss * rain(t)) / plant.R
        dT = (P + plant.Q_chicks - g * (T - ambient(t))) / plant.C
        if ctrl.Ki > 0 and ctrl.mode == "automatic":
            dI = e
            if ctrl.antiwindup and ctrl.heater_on:
                # back-calculation with T_t = Ti = Kp/Ki  ->  I' = e + (P - u_raw)/Kp
                dI += (P - u_raw) / max(ctrl.Kp, 1e-9)
        else:
            dI = 0.0
        dTm = (T - Tm) / ctrl.tau_d
        return np.array([dT, dI, dTm])

    return f


def heater_power(plant, ctrl, y):
    return control(ctrl, plant, y[0], y[1], y[2])[2]


def required_power(plant, T_set, T_a, rain=0.0):
    """Steady-state heater power needed to hold T_set (may exceed P_max or be < 0)."""
    g = (1.0 + plant.rain_loss * rain) / plant.R
    return g * (T_set - T_a) - plant.Q_chicks


def equilibrium_T(plant, P, T_a, rain=0.0):
    """Open-loop equilibrium temperature for constant heater power P."""
    g = (1.0 + plant.rain_loss * rain) / plant.R
    return T_a + (P + plant.Q_chicks) / g
