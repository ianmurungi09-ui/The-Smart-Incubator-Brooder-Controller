import pytest

from brooder.advisor import (Context, advise, context_from_params, metrics_for_advisor,
                             recommended_setpoint, required_heater_w)


def make(**kw):
    base = dict(age_days=3, n_chicks=20, setpoint=35.0, night_ambient_c=25.0,
                heater_max_w=150.0)
    base.update(kw)
    return Context(**base)


def levels(advice):
    return {f["level"] for f in advice.findings}


def text(advice):
    return " ".join(f["message"] for f in advice.findings)


@pytest.mark.parametrize("age,expected", [(0, 35), (7, 35), (8, 32), (21, 29),
                                          (35, 23), (60, 21)])
def test_setpoint_by_age(age, expected):
    assert recommended_setpoint(age) == expected


def test_required_power_matches_model():
    # UA = 5 W/K, dT = 10 K -> 50 W loss, minus 8 W from 20 chicks
    assert required_heater_w(make()) == pytest.approx(42.0)


def test_rain_increases_required_power():
    assert required_heater_w(make(), raining=True) == pytest.approx(57.0)


def test_required_power_never_negative():
    assert required_heater_w(make(night_ambient_c=40, setpoint=30)) == 0.0


def test_ok_for_correct_setup():
    assert levels(advise(make())) == {"ok"}


def test_too_cold_for_age_is_critical():
    assert "critical" in levels(advise(make(setpoint=29.0)))


def test_too_hot_for_age_warns():
    assert "warning" in levels(advise(make(age_days=30, setpoint=30.0)))


def test_undersized_heater_critical():
    assert "Heater too small" in text(advise(make(night_ambient_c=5.0, heater_max_w=60.0)))


def test_low_headroom_warning():
    assert "spare heater power" in text(advise(make(heater_max_w=65.0)))


def test_unreliable_power_flagged():
    assert "backup" in text(advise(make(power_reliable=False)))


def test_findings_sorted_most_severe_first():
    adv = advise(make(setpoint=29.0, power_reliable=False))
    assert adv.findings[0]["level"] == "critical"
    assert adv.findings[-1]["level"] in {"ok", "warning"}


def test_p_only_offset_recommends_integral_action():
    adv = advise(make(), {"mode_name": "P", "steady_state_error_K": 1.2})
    assert "integral" in text(adv)


def test_overshoot_recommends_antiwindup():
    assert "anti-windup" in text(advise(make(), {"startup_overshoot_pct": 40}))


def test_unstable_run_flagged():
    assert "RK4" in text(advise(make(), {"unstable": True}))


def test_never_recovered_flagged_only_after_a_disturbance():
    assert "did not recover" in text(advise(make(), {"peak_dev_K": 4.0, "recovery_min": None}))
    assert "did not recover" not in text(advise(make(), {"peak_dev_K": None, "recovery_min": None}))


def test_manual_mode_drops_tuning_rules():
    params = dict(Ki=0.01, Kd=0.0, mode="manual")
    out = metrics_for_advisor(params, {"steady_state_error_K": 3.0, "recovery_min": 99})
    assert "steady_state_error_K" not in out and "recovery_min" not in out


def test_context_from_params_maps_fields():
    ctx = context_from_params(dict(n_chicks=30, T_set=33, amb_night=10, P_max=90, R=0.25,
                                   rain_loss=0.2, q_chick=0.5), age_days=12)
    assert (ctx.n_chicks, ctx.setpoint, ctx.heater_max_w, ctx.age_days) == (30, 33, 90, 12)


@pytest.mark.parametrize("kw", [dict(age_days=-1), dict(age_days=500), dict(n_chicks=-1),
                                dict(heater_max_w=0), dict(insulation_r=0)])
def test_invalid_input_rejected(kw):
    with pytest.raises(ValueError):
        advise(make(**kw))
