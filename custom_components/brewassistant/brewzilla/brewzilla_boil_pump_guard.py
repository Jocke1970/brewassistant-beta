"""BOIL process power contract (0b11): heat 100%, pump OFF/0%.

This is a late, read-only-intent decorator over the normal orchestration
snapshot. Existing RCL source authority, identity, read-only, ABORT,
telemetry freshness, and supervised-apply guards remain the ONLY permission
to actuate. Missing RCL is not STOP and is never grounds for OFF/0 writes.

Cooling/ChillOut pump use belongs to Cooling Runtime/operator instead.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_orchestration as base
from . import brewzilla_temperature as temperature

_BASE_BUILD = None
_INSTALLED = False
_BAD_RUNTIME_STATES = {
    "idle", "unknown", "unavailable", "none", "resync_required",
    "source_unavailable", "completed", "aborted",
}
_RCL_SOURCE = "RAPT BrewZilla Profile"


def _current_boil(hass) -> bool:
    """Look at the CURRENT live Brewday/RCL step, never at next_step.

    This function also guards direct/learning pump-start requests. A stale
    BOIL label can block a positive start but can NEVER authorize OFF/0:
    the separate verified source-authority boundary handles that.
    """
    from ..brewday.brewday_runtime import build_brewday_runtime_snapshot

    runtime = build_brewday_runtime_snapshot(hass)
    state = str(runtime.get("runtime_state") or "unknown").lower()
    if state in _BAD_RUNTIME_STATES:
        return False

    source = str(runtime.get("source") or "")
    if source == _RCL_SOURCE:
        from ..brewday import rapt_profile_runtime
        profile = rapt_profile_runtime._profile_state(hass)
        if not rapt_profile_runtime._active_contract(profile):
            return False
        attrs = profile.attributes
        if attrs.get("profile_active") is not True or attrs.get("profile_contract_complete") is not True:
            return False
        return temperature._is_current_boil_label(attrs.get("step_name"))

    return any(temperature._is_current_boil_label(runtime.get(key))
               for key in ("stage", "step", "raw_step_name"))


def _boil_pump_snapshot(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Clamp active BOIL utilization intent without overriding any safety holds."""
    out = dict(snapshot)
    active_boil = _current_boil(hass)
    out["boil_pump_internal_only_policy"] = active_boil
    out["boil_pump_policy_name"] = "OFF / 0 %" if active_boil else None
    out["boil_heat_policy_name"] = "100 %" if active_boil else None

    # Fail-passive, unknown owner, resync, ABORT and cooling handoff must
    # retain their previous no-write decisions. No fallback OFF on source loss.
    blocked = (
        out.get("fail_passive_active")
        or out.get("fail_passive_no_new_writes")
        or out.get("abort_lockout_active")
        or out.get("rapt_cooling_handoff_active")
        or out.get("completed_runtime")
        or not out.get("connected")
        or not out.get("can_apply_target") and
            str(out.get("orchestration_mode") or "").lower() in
            {"blocked", "source-observer", "local-control"}
    )
    if not active_boil or blocked:
        return out

    # Treat unknown pump telemetry as unverified; never infer physically OFF.
    current = base._float(hass, base.BREWZILLA_PUMP_UTILIZATION)
    pump_entity = hass.states.get(base.BREWZILLA_PUMP_SWITCH)
    if current is None or pump_entity is None or pump_entity.state not in {"on", "off"}:
        out.update(
            boil_pump_readback_verified=False,
            boil_pump_policy_block_reason="pump_readback_unavailable",
            pump_recommended=False,
            desired_pump_on=None,
            desired_pump_utilization=None,
            pump_action_needed=False,
            pump_stop_needed=False,
            pump_utilization_action_needed=False,
            ba_owned_reassert_action_needed=False,
            can_apply_target=False,
            orchestration_mode="blocked",
            control_reason="BOIL pump OFF/0 required, but pump readback is unavailable; no new pump write",
        )
        return out

    pump_running = pump_entity.state == "on"
    needs_zero = abs(current) > base.UTILIZATION_TOLERANCE

    # Full heat utilization is a POWER CEILING, not heater ON or a target
    # override. BrewZilla/RAPT still owns the thermostat and actual heat switch.
    # An intentional safety heat-down, ABORT or source loss must always win.
    heat_raw = out.get("heat_utilization")
    try:
        heat_util = float(heat_raw) if heat_raw is not None else None
    except (TypeError, ValueError):
        heat_util = None
    heat_known = heat_util is not None and 0.0 <= heat_util <= 100.0
    safety_heat_down = (
        out.get("heater_stop_needed") is True
        or out.get("desired_heater_on") is False
        and out.get("heat_utilization_action_needed") is True
        and out.get("desired_heat_utilization") == 0.0
        or str(out.get("safety_state") or "").lower()
        in {"abort", "aborted", "emergency", "hard_stop", "hard-stop"}
    )
    full_heat_needed = bool(
        heat_known and not safety_heat_down
        and abs(heat_util - 100.0) > base.UTILIZATION_TOLERANCE
    )
    other_action = bool(
        out.get("target_sync_needed") or out.get("heater_action_needed")
        or out.get("heater_stop_needed")
    )
    # No earlier mash, BA Learning or owned utilization recommendation may
    # override a verified BOIL. Never clear an intentional heat safe-down.
    out.update(
        boil_stage=True,
        boil_pump_readback_verified=True,
        boil_pump_policy_block_reason=None,
        boil_heat_readback_verified=heat_known,
        boil_heat_safety_reduction_preserved=bool(safety_heat_down),
        pump_recommended=False,
        desired_pump_on=False,
        desired_pump_utilization=0.0,
        pump_action_needed=False,
        pump_stop_needed=pump_running,
        pump_utilization_action_needed=needs_zero,
        desired_heat_utilization=(
            100.0 if heat_known and not safety_heat_down
            else out.get("desired_heat_utilization") if safety_heat_down
            else None
        ),
        heat_utilization_action_needed=(
            out.get("heat_utilization_action_needed", False) if safety_heat_down
            else full_heat_needed
        ),
        ba_owned_reassert_action_needed=False,
        can_apply_target=bool(
            other_action or pump_running or needs_zero
            or full_heat_needed
            or safety_heat_down and out.get("heat_utilization_action_needed")
        ),
        control_reason=(
            "Active BOIL: retain explicit heat safety reduction and require pump OFF / 0%."
            if safety_heat_down else
            "Active BOIL: request heat utilization 100%, pump OFF / 0% through guarded RCL path."
            if heat_known else
            "Active BOIL: pump OFF / 0%; heat utilization readback unavailable – no heat change."
        ),
    )
    return out


def build_orchestration_snapshot(hass) -> dict[str, Any]:
    assert _BASE_BUILD is not None
    return _boil_pump_snapshot(hass, _BASE_BUILD(hass))


def install_boil_pump_guard() -> None:
    global _BASE_BUILD, _INSTALLED
    if _INSTALLED:
        return
    _BASE_BUILD = base.build_orchestration_snapshot
    base.build_orchestration_snapshot = build_orchestration_snapshot
    _INSTALLED = True
