"""Rule-based brooder advisor: turns the keeper's context and a simulated run
into prioritised, plain-language decisions.

Pure functions with no I/O, so every rule is unit-testable. The advisor never
trusts client-supplied metrics: the web layer re-runs the simulation on the
server and passes the fresh results in here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_AGE_DAYS = 70

# (last day of band, recommended brooding temperature in deg C)
_SETPOINT_BANDS = ((7, 35.0), (14, 32.0), (21, 29.0), (28, 26.0), (35, 23.0))
_FINAL_SETPOINT = 21.0

# Thresholds (named so the rules read clearly and are easy to tune).
SETPOINT_TOLERANCE_C = 2.0
LOW_HEADROOM_FRACTION = 0.8
SSE_TOLERANCE_K = 0.5
OVERSHOOT_LIMIT_PCT = 15.0
SLOW_RECOVERY_MIN = 30.0
CHILL_MINUTES_LIMIT = 15.0


@dataclass(frozen=True)
class Context:
    age_days: int
    n_chicks: int
    setpoint: float
    night_ambient_c: float
    heater_max_w: float
    insulation_r: float = 0.20      # K/W, so UA = 1/R
    rain_loss: float = 0.30         # extra fractional heat loss in rain
    q_chick: float = 0.4            # W of metabolic heat per chick
    power_reliable: bool = True


def validate(ctx: Context) -> None:
    """Raise ValueError on out-of-range input."""
    if not 0 <= ctx.age_days <= MAX_AGE_DAYS:
        raise ValueError(f"age_days must be between 0 and {MAX_AGE_DAYS}")
    if ctx.n_chicks < 0:
        raise ValueError("n_chicks must not be negative")
    if ctx.heater_max_w <= 0 or ctx.insulation_r <= 0:
        raise ValueError("heater_max_w and insulation_r must be positive")


def recommended_setpoint(age_days: int) -> float:
    """Brooding temperature (deg C) for a chick age in days."""
    for last_day, temp in _SETPOINT_BANDS:
        if age_days <= last_day:
            return temp
    return _FINAL_SETPOINT


def required_heater_w(ctx: Context, raining: bool = False) -> float:
    """Steady-state heater power needed on the coldest night (never below 0)."""
    loss_factor = 1.0 + (ctx.rain_loss if raining else 0.0)
    loss = loss_factor * (ctx.setpoint - ctx.night_ambient_c) / ctx.insulation_r
    return max(0.0, loss - ctx.n_chicks * ctx.q_chick)


@dataclass
class Advice:
    recommended_setpoint: float
    required_heater_w: float
    required_heater_rain_w: float
    findings: list = field(default_factory=list)

    def add(self, level: str, message: str) -> None:
        self.findings.append({"level": level, "message": message})

    def as_dict(self) -> dict:
        return {"recommended_setpoint_C": self.recommended_setpoint,
                "required_heater_W": round(self.required_heater_w, 1),
                "required_heater_rain_W": round(self.required_heater_rain_w, 1),
                "findings": self.findings}


def _check_setpoint(ctx, rec, advice):
    diff = ctx.setpoint - rec
    if diff < -SETPOINT_TOLERANCE_C:
        advice.add("critical", f"Target {ctx.setpoint:.1f} °C is too cold for day "
                   f"{ctx.age_days}; chicks may chill. Raise it to about {rec:.0f} °C.")
    elif diff > SETPOINT_TOLERANCE_C:
        advice.add("warning", f"Target {ctx.setpoint:.1f} °C is too warm for day "
                   f"{ctx.age_days}; chicks risk heat stress. Lower it to about {rec:.0f} °C.")
    else:
        advice.add("ok", f"Target {ctx.setpoint:.1f} °C suits a day-{ctx.age_days} flock.")


def _check_heater(ctx, advice):
    need, need_rain = advice.required_heater_w, advice.required_heater_rain_w
    if need_rain > ctx.heater_max_w:
        advice.add("critical", f"Heater too small: a rainy night at {ctx.night_ambient_c:.0f} °C "
                   f"needs about {need_rain:.0f} W but the heater delivers {ctx.heater_max_w:.0f} W. "
                   "Add heater capacity or insulation, or lower the target.")
    elif need_rain > LOW_HEADROOM_FRACTION * ctx.heater_max_w:
        advice.add("warning", f"Little spare heater power: a rainy night needs {need_rain:.0f} W "
                   f"of {ctx.heater_max_w:.0f} W. Consider extra insulation.")
    else:
        advice.add("ok", f"Heater has enough spare capacity (needs {need_rain:.0f} W "
                   f"of {ctx.heater_max_w:.0f} W on a rainy night).")


def _check_run(ctx, metrics, advice):
    if metrics.get("unstable"):
        advice.add("critical", "The simulation became numerically unstable. "
                   "Use RK4 or a smaller time step.")
        return
    sse = metrics.get("steady_state_error_K")
    if sse is not None and abs(sse) > SSE_TOLERANCE_K:
        if metrics.get("mode_name") == "P":
            advice.add("warning", f"Proportional-only control leaves a {abs(sse):.1f} °C "
                       "offset. Turn on integral action (Ki > 0).")
        else:
            advice.add("warning", f"The temperature ends {abs(sse):.1f} °C from target. "
                       "Check heater capacity or increase Ki.")
    overshoot = metrics.get("startup_overshoot_pct")
    if overshoot is not None and overshoot > OVERSHOOT_LIMIT_PCT:
        advice.add("warning", f"Warm-up overshoots by {overshoot:.0f} %. Lower Ki "
                   "or keep anti-windup switched on.")
    if metrics.get("peak_dev_K") is not None and "recovery_min" in metrics:
        rec_min = metrics["recovery_min"]
        if rec_min is None:
            advice.add("warning", "The brooder did not recover after the cold night. "
                       "It needs more heater power or insulation.")
        elif rec_min > SLOW_RECOVERY_MIN:
            advice.add("info", f"Recovery after the cold night took {rec_min:.0f} min. "
                       "A higher Kp speeds it up.")
    chilled = metrics.get("minutes_outside_33_37C")
    if chilled is not None and chilled > CHILL_MINUTES_LIMIT:
        advice.add("warning", f"Temperature was outside the 33–37 °C comfort band for "
                   f"{chilled:.0f} min; watch the chicks for huddling.")


def advise(ctx: Context, metrics: dict | None = None) -> Advice:
    """Produce prioritised findings from context and optional run metrics.

    Recognised metric keys (all optional): unstable, mode_name ('P'|'PI'|'PID'),
    steady_state_error_K, startup_overshoot_pct, recovery_min (None = never
    recovered), minutes_outside_33_37C.
    """
    validate(ctx)
    advice = Advice(recommended_setpoint=recommended_setpoint(ctx.age_days),
                    required_heater_w=required_heater_w(ctx),
                    required_heater_rain_w=required_heater_w(ctx, raining=True))
    _check_setpoint(ctx, advice.recommended_setpoint, advice)
    _check_heater(ctx, advice)
    if not ctx.power_reliable:
        advice.add("warning", "Power is unreliable: keep a battery or solar backup and extra "
                   "insulation so the brooder cools slowly during an outage.")
    _check_run(ctx, metrics or {}, advice)
    order = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
    advice.findings.sort(key=lambda f: order[f["level"]])
    return advice


def context_from_params(params: dict, age_days: int, power_reliable: bool = True) -> Context:
    """Build a Context from the simulator's validated parameter dict."""
    return Context(age_days=age_days, n_chicks=int(params["n_chicks"]),
                   setpoint=params["T_set"], night_ambient_c=params["amb_night"],
                   heater_max_w=params["P_max"], insulation_r=params["R"],
                   rain_loss=params["rain_loss"], q_chick=params["q_chick"],
                   power_reliable=power_reliable)


def metrics_for_advisor(params: dict, metrics: dict) -> dict:
    """Map simulator metrics onto the keys the advisor understands."""
    out = dict(metrics)
    out["mode_name"] = "P" if params["Ki"] <= 0 else "PI" if params["Kd"] <= 0 else "PID"
    if params["mode"] == "manual":   # open-loop run: control-tuning rules do not apply
        for key in ("steady_state_error_K", "startup_overshoot_pct", "recovery_min"):
            out.pop(key, None)
    return out
