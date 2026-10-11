"""BOIL process pump interlock (0b11): OFF and utilization 0%.

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
        for entity in hass.states.async_all("binary_sensor"):
            attrs = getattr(entity, "attributes", {}) or {}
            if attrs.get("ba_source") != "rapt_cloud_link_brewzilla_profile_runtime":
                continue
            if str(entity.state).lower() != "on":
                continue
            if attrs.get("profile_active") is not True:
                continue
            return temperature._is_current_boil_label(attrs.get("step_name"))
        return False

    return any(temperature._is_current_boil_label(runtime.get(key))
               for key in ("stage", "step", "raw_step_name"))


def _boil_pump_snapshot(hass, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Clamp valid BOIL process intent without ever overriding safety holds."""
    out = dict(snapshot)
    active_boil = _current_boil(hass)
    out["boil_pump_internal_only_policy"] = active_boil
    out["boil_pump_policy_name"] = "OFF / 0 %" if active_boil else None

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
            control_reason="BOIL pump OFF/0 required, but pump readback is unavailable; no new pump write",
        )
        return out

    pump_running = pump_entity.state == "on"
    needs_zero = abs(current) > base.UTILIZATION_TOLERANCE
    other_action = bool(
        out.get("target_sync_needed") or out.get("heater_action_needed")
        or out.get("heater_stop_needed") or out.get("heat_utilization_action_needed")
    )
    # No previous mash, owned advice or learning recommendation may override BOIL.
    out.update(
        boil_stage=True,
        boil_pump_readback_verified=True,
        boil_pump_policy_block_reason=None,
        pump_recommended=False,
        desired_pump_on=False,
        desired_pump_utilization=0.0,
        pump_action_needed=False,
        pump_stop_needed=pump_running,
        pump_utilization_action_needed=needs_zero,
        ba_owned_reassert_action_needed=False,
        can_apply_target=bool(other_action or pump_running or needs_zero),
        control_reason="Active BOIL: request pump OFF and utilization 0% through existing guarded RCL path",
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
