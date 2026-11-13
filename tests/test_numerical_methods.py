import numpy as np

from brooder.solvers import integrate
from webapp import app as webapp


def test_rk4_is_more_accurate_than_euler_for_exponential_growth():
    derivative = lambda _t, y: y
    exact = np.e

    _, euler_values = integrate(derivative, np.array([1.0]), 0.0, 1.0, 0.1, "euler")
    _, rk4_values = integrate(derivative, np.array([1.0]), 0.0, 1.0, 0.1, "rk4")

    assert euler_values[-1, 0] != rk4_values[-1, 0]
    assert abs(rk4_values[-1, 0] - exact) < abs(euler_values[-1, 0] - exact)


def test_simulation_metrics_use_full_resolution_when_chart_data_is_downsampled(monkeypatch):
    params, errors = webapp.parse({"method": "euler", "h": 2, "duration_h": 3})
    assert not errors

    monkeypatch.setattr(webapp, "MAX_POINTS", 10_000)
    full_series, full_metrics = webapp.simulate(params)
    monkeypatch.setattr(webapp, "MAX_POINTS", 20)
    downsampled_series, downsampled_metrics = webapp.simulate(params)

    assert len(downsampled_series["t"]) < len(full_series["t"])
    assert downsampled_metrics["peak_dev_K"] == full_metrics["peak_dev_K"]
    assert downsampled_metrics["recovery_min"] == full_metrics["recovery_min"]
    assert downsampled_metrics["steady_state_error_K"] == full_metrics["steady_state_error_K"]
