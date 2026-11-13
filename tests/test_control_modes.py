from webapp.app import parse, simulate


def test_manual_mode_uses_requested_heater_percentage():
    params, errors = parse({
        "mode": "manual",
        "manual_power_pct": 30,
        "duration_h": 0.5,
        "h": 300,
    })

    assert not errors
    series, _ = simulate(params)

    assert series["P"] == [45.0] * len(series["P"])


def test_manual_power_is_cut_off_at_heater_failure():
    params, errors = parse({
        "mode": "manual",
        "manual_power_pct": 80,
        "heater_fail_h": 0.25,
        "duration_h": 0.5,
        "h": 60,
    })

    assert not errors
    series, _ = simulate(params)

    assert any(power == 120.0 for power in series["P"])
    assert series["P"][-1] == 0.0


def test_parse_rejects_invalid_mode_and_manual_power():
    _, errors = parse({"mode": "remote", "manual_power_pct": 101})

    assert "mode" in errors
    assert "manual_power_pct" in errors


def test_automatic_mode_keeps_using_the_temperature_controller():
    params, errors = parse({"mode": "automatic", "manual_power_pct": ""})

    assert not errors
    series, _ = simulate(params)

    assert series["P"][0] == 80.0
