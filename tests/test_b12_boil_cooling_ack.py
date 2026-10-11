"""BOIL CFC operator acknowledgement and RCL timeline are no-hardware gates."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import math

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "custom_components/brewassistant/brewzilla/brewzilla_boil_cooling_gate.py"


def runner():
    source = FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"_timestamp", "_identities", "observe", "select"}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {f.name for f in functions} == wanted
    ns = dict(datetime=datetime, timezone=timezone, math=math,
              DOMAIN="brewassistant", DATA_KEY="brewzilla_boil_cooling_choice",
              READY="cfc_ready", NO_COOLING="no_cooling", PENDING="pending",
              CHILL_WINDOW_SECONDS=900, MAX_OBSERVATION_AGE_SECONDS=90)
    ns["build_brewday_runtime_snapshot"] = lambda hass: hass.runtime
    ns["temperature"] = SimpleNamespace(
        _is_current_boil_label=lambda value: str(value).lower() in {"boil", "boil hold"}
    )
    ns["rapt_profile_runtime"] = SimpleNamespace(
        RAPT_PROFILE_SOURCE="RAPT BrewZilla Profile",
        _profile_state=lambda hass: hass.profile,
        _active_contract=lambda profile: profile.state == "on",
    )
    astmod = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *functions
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(astmod), str(FILE), "exec"), ns)
    return ns


def kettle(*, minutes_elapsed=40, now=None):
    now = now or datetime.now(timezone.utc)
    attrs = {
        "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
        "profile_contract_complete": True, "profile_active": True,
        "profile_session_id": "current-session",
        "profile_id": "current-profile", "step_id": "boil-step-1",
        "step_name": "Boil", "step_end_type": "Duration",
        "step_duration_type": "Start", "step_length": 3600,
        "profile_observed_at": now.isoformat(),
        "profile_step_transition_observed_at": (
            now - timedelta(minutes=minutes_elapsed)).isoformat(),
    }
    return SimpleNamespace(
        data={}, profile=SimpleNamespace(state="on", attributes=attrs),
        runtime={"source": "RAPT BrewZilla Profile"}, at=now,
    )


def choose(ns, hass, choice="cfc_ready"):
    attrs = hass.profile.attributes
    return ns["select"](
        hass, choice=choice, confirmed=True,
        expected_session_id=attrs["profile_session_id"],
        expected_profile_id=attrs["profile_id"],
        expected_step_id=attrs["step_id"],
        expected_transition_at=attrs["profile_step_transition_observed_at"],
        active_boil=True,
    )


def test_no_choice_and_no_cooling_keep_pump_off():
    ns, hass = runner(), kettle()
    first = ns["observe"](hass, active_boil=True)
    assert first["boil_cooling_choice"] == "pending"
    assert first["boil_cooling_recirc_allowed"] is False
    choice = choose(ns, hass, "no_cooling")
    assert choice["boil_cooling_choice"] == "no_cooling"
    assert choice["boil_cooling_recirc_allowed"] is False
    assert choice["boil_cooling_reason"] == "operator_no_cooling"


def test_ready_selection_waits_for_last_fifteen_minutes():
    ns, hass = runner(), kettle(minutes_elapsed=40)
    choice = choose(ns, hass)
    assert choice["boil_cooling_choice"] == "cfc_ready"
    assert choice["boil_cooling_timer_verified"] is True
    assert choice["boil_cooling_recirc_allowed"] is False
    assert choice["boil_cooling_remaining_seconds_estimate"] >= 900

    # Fresh new RCL observation for SAME session/step/observed transition.
    later = hass.at + timedelta(minutes=5, seconds=1)
    hass.profile.attributes["profile_observed_at"] = later.isoformat()
    observed = ns["observe"](hass, active_boil=True, now=later)
    assert observed["boil_cooling_recirc_allowed"] is True
    assert observed["boil_cooling_remaining_seconds_estimate"] <= 900


@pytest.mark.parametrize("field,value,reason", [
    ("step_duration_type", "Target", "timer_not_start_based"),
    ("step_end_type", "Manual", "timer_not_start_based"),
    ("step_length", None, "timer_unavailable"),
])
def test_non_start_based_or_missing_timer_never_turns_pump_on(field, value, reason):
    ns, hass = runner(), kettle(minutes_elapsed=50)
    choose(ns, hass)
    hass.profile.attributes[field] = value
    out = ns["observe"](hass, active_boil=True)
    assert out["boil_cooling_choice"] == "cfc_ready"
    assert out["boil_cooling_recirc_allowed"] is False
    assert out["boil_cooling_reason"] == reason


def test_stale_profile_and_unknown_step_do_not_authorize_positive_pump():
    ns, hass = runner(), kettle(minutes_elapsed=50)
    choose(ns, hass)
    hass.profile.attributes["profile_observed_at"] = (
        hass.at - timedelta(minutes=3)).isoformat()
    assert ns["observe"](hass, active_boil=True)["boil_cooling_recirc_allowed"] is False
    hass.profile.attributes["profile_observed_at"] = hass.at.isoformat()
    hass.profile.attributes["step_id"] = "another-step"
    assert ns["observe"](hass, active_boil=True)["boil_cooling_recirc_allowed"] is False
    hass.profile.attributes["step_id"] = "boil-step-1"
    hass.profile.attributes["step_name"] = "Cooling"
    assert ns["observe"](hass, active_boil=True)["boil_cooling_recirc_allowed"] is False
    assert ns["observe"](hass, active_boil=False)["boil_cooling_recirc_allowed"] is False


def test_reconnect_new_session_restart_and_wrong_owner_never_reuse_confirmation():
    ns, hass = runner(), kettle(minutes_elapsed=50)
    choose(ns, hass)
    assert ns["observe"](hass, active_boil=True)["boil_cooling_recirc_allowed"] is True

    reboot = kettle(minutes_elapsed=50, now=hass.at)
    assert ns["observe"](reboot, active_boil=True)["boil_cooling_recirc_allowed"] is False
    hass.profile.attributes["profile_session_id"] = "next-session"
    assert ns["observe"](hass, active_boil=True)["boil_cooling_recirc_allowed"] is False
    hass.profile.attributes["profile_session_id"] = "current-session"
    hass.runtime["source"] = "Brewfather Brew Tracker"
    assert ns["observe"](hass, active_boil=True)["boil_cooling_recirc_allowed"] is False


def test_choice_requires_explicit_confirmation_and_same_current_identity():
    ns, hass = runner(), kettle(minutes_elapsed=50)
    attrs = hass.profile.attributes
    with pytest.raises(ValueError, match="Explicit"):
        ns["select"](
            hass, choice="cfc_ready", confirmed=False,
            expected_session_id="current-session", expected_profile_id="current-profile",
            expected_step_id="boil-step-1",
            expected_transition_at=attrs["profile_step_transition_observed_at"],
            active_boil=True,
        )
    with pytest.raises(ValueError, match="identity changed"):
        ns["select"](
            hass, choice="cfc_ready", confirmed=True,
            expected_session_id="old-session", expected_profile_id="current-profile",
            expected_step_id="boil-step-1",
            expected_transition_at=attrs["profile_step_transition_observed_at"],
            active_boil=True,
        )
    assert "brewzilla_boil_cooling_choice" not in hass.data.get("brewassistant", {})


def test_module_never_calls_hardware_and_cards_have_confirmed_backend_actions():
    src = FILE.read_text(encoding="utf-8")
    auth = (ROOT / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_runtime.py").read_text(encoding="utf-8")
    impl = (ROOT / "custom_components/brewassistant/__init__.py").read_text(encoding="utf-8")
    sensor = (ROOT / "custom_components/brewassistant/brewzilla/brewzilla_orchestration_sensor.py").read_text(encoding="utf-8")
    assert "hass.services.async_call" not in src
    assert "cooling_gate.observe(hass, active_boil=True)" in auth
    assert "if not recirculate" in auth
    assert "SERVICE_BOIL_COOLING_CHOICE" in impl
    assert '"brewzilla_boil_cooling_status"' in sensor
    for name in ("brewday_control_status_sv.yaml", "brewday_control_status.yaml"):
        card = (ROOT / "dashboard/cards" / name).read_text(encoding="utf-8")
        assert "brewassistant.boil_cooling_choice" in card
        assert "choice: 'cfc_ready'" in card
        assert "choice: 'no_cooling'" in card
        assert "expected_session_id" in card and "expected_step_id" in card
        assert "confirmation:" in card
