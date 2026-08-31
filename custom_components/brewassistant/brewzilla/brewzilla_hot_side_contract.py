"""Consolidated Heatstrike -> Mash-In physical contract.

This is the single boundary adapter between the resolved hot-side temperature
roles, Clean Heatstrike and the Mash-In state machine.

It deliberately does not invent another heat profile. Clean Heatstrike remains
the pre-mash-in regulator. This module only makes controller inputs and the
operator handoff unambiguous:

* process_temperature = resolved mash/BLE process probe
* safety_temperature = BrewZilla internal/wort guard probe
* READY is operator-only; it must not replace Heatstrike target/heat/pump
* Mash-In Started is the only boundary that releases strike target and stops
  circulation for grain addition
* Mash-In Complete is only valid after Mash-In Started
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..brewday.brewday_audit import async_record_brewday_audit_event
from ..const import DOMAIN
from . import brewzilla_advice_control as advice_control
from . import brewzilla_clean_heat_strike_guard as clean
from . import brewzilla_mash_in_gate as gate
from . import brewzilla_orchestration as base
from .brewzilla_temperature import brewzilla_temperature_snapshot

_INSTALLED = False
_ORIGINAL_UNDER_CLEAN: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_GATE_AUGMENT: Callable[[HomeAssistant, dict[str, Any]], dict[str, Any]] | None = None
_ORIGINAL_CONFIRM_COMPLETE: Callable[[HomeAssistant], Awaitable[dict[str, Any]]] | None = None

_READY_STATE = gate.READY_STATE
_STARTED_STATE = gate.STARTED_STATE
_COMPLETE_STATE = gate._COMPLETE_STATE


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _temperature_roles(hass: HomeAssistant) -> dict[str, Any]:
    resolved = brewzilla_temperature_snapshot(hass)
    process = _num(resolved.get("mash_temperature"))
    safety = _num(resolved.get("wort_temperature"))
    return {
        "process_temperature": process,
        "process_temperature_entity": resolved.get("mash_temperature_entity"),
        "process_temperature_source": resolved.get("mash_temperature_source"),
        "process_temperature_available": process is not None,
        "mash_temperature": process,
        "mash_temperature_entity": resolved.get("mash_temperature_entity"),
        "mash_temperature_source": resolved.get("mash_temperature_source"),
        "safety_temperature": safety,
        "safety_temperature_entity": resolved.get("wort_temperature_entity"),
        "safety_temperature_source": resolved.get("wort_temperature_source"),
        "wort_temperature": safety,
        "wort_temperature_entity": resolved.get("wort_temperature_entity"),
        "wort_temperature_source": resolved.get("wort_temperature_source"),
        "temperature_delta_mash_wort": resolved.get("temperature_delta_mash_wort"),
        "process_temperature_source_lock_active": resolved.get("mash_temperature_source_lock_active"),
        "process_temperature_source_lock_degraded_reason": resolved.get(
            "mash_temperature_source_lock_degraded_reason"
        ),
    }


def _inject_roles(hass: HomeAssistant, snapshot: dict[str, Any]) -> dict[str, Any]:
    return {**snapshot, **_temperature_roles(hass)}


def _strict_clean_gate_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    value = _num(out.get("process_temperature"))
    if value is None:
        return None, None
    return value, "process_temperature"


def _canonical_safety_temperature(out: dict[str, Any]) -> tuple[float | None, str | None]:
    candidates: list[tuple[str, float]] = []
    for key in ("safety_temperature", "process_temperature"):
        value = _num(out.get(key))
        if value is not None:
            candidates.append((key, value))
    if not candidates:
        return None, None
    source, value = max(candidates, key=lambda item: item[1])
    return value, source


def _with_canonical_clean_heatstrike(
    hass: HomeAssistant,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Feed Clean Heatstrike exactly one process/safety role pair."""
    assert _ORIGINAL_UNDER_CLEAN is not None
    out = _inject_roles(hass, _ORIGINAL_UNDER_CLEAN(hass, snapshot))

    if (
        out.get("heat_strike_latch_active")
        and str(out.get("advice_physical_phase") or "").lower().startswith("pre_mash_in")
        and out.get("process_temperature") is None
    ):
        # Never silently promote the internal/wort probe to target-reached
        # authority. The target remains latched, but positive heat is blocked
        # until the owned process probe is healthy again.
        out.update(
            {
                "clean_heat_strike_process_temperature_missing": True,
                "clean_heat_strike_ready_allowed": False,
                "desired_heat_utilization": 0.0,
                "desired_heater_on": False,
                "heating_needed": False,
                "heat_utilization_action_needed": base._utilization_action_needed(
                    _num(out.get("heat_utilization")), 0.0
                ),
                "heater_action_needed": False,
                "heater_stop_needed": bool(out.get("heater_on")),
                "can_apply_target": True,
                "orchestration_mode": "direct-control",
                "control_reason": (
                    f"{out.get('control_reason') or 'Heatstrike active.'} "
                    "Canonical mash/BLE process temperature is unavailable; "
                    "readiness is blocked and heat is safely held at 0% until "
                    "the owned process probe returns."
                ),
            }
        )
        return out

    out = clean._apply_clean_heatstrike(out)
    out["clean_heat_strike_process_temperature_missing"] = False
    out["clean_heat_strike_ready_allowed"] = out.get("process_temperature") is not None
    return out


def _strict_gate_temperature(snapshot: dict[str, Any]) -> float | None:
    """Mash-In readiness may only use the canonical process probe."""
    return _num(snapshot.get("process_temperature"))


def _ready_is_pure_gate(snapshot: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    """Decorate READY without changing Heatstrike target, heat or circulation."""
    reason = str(snapshot.get("control_reason") or "Heatstrike control active.")
    return {
        **snapshot,
        **gate._gate_fields(store, snapshot, pending=True),
        "mash_in_ready_preserves_heatstrike_authority": True,
        "control_reason": (
            f"{reason}; Mash-In READY is operator-only. Heatstrike target/heat/pump "
            "remain authoritative until Mash-In Started is pressed."
        ),
    }


def _augment_with_process_roles(
    hass: HomeAssistant,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    assert _ORIGINAL_GATE_AUGMENT is not None
    return _ORIGINAL_GATE_AUGMENT(hass, _inject_roles(hass, snapshot))


def _started_heat_request(
    process_temperature: float | None,
    target: float | None,
) -> tuple[float, bool, str]:
    if process_temperature is None or target is None:
        return 0.0, False, "process_temperature_unavailable"
    delta = round(target - process_temperature, 2)
    if delta > 1.0:
        return gate.MASH_IN_STARTED_MAX_HEAT_UTILIZATION, True, "anti_drop_recovery"
    if delta > 0.2:
        return gate.MASH_IN_STARTED_COAST_HEAT_UTILIZATION, True, "anti_drop_coast"
    if delta >= -0.3:
        return gate.MASH_IN_STARTED_FEATHER_HEAT_UTILIZATION, True, "anti_drop_feather"
    return 0.0, False, "above_effective_target"


def _hard_transition_block(snapshot: dict[str, Any]) -> str | None:
    if snapshot.get("abort_lockout_active"):
        return "abort_lockout_active"
    if snapshot.get("completed_runtime"):
        return "completed_runtime"
    if not snapshot.get("connected", True):
        return "brewzilla_disconnected"
    return None


async def _set_if_present(
    hass: HomeAssistant,
    entity_id: str,
    value: float,
    actions: list[str],
    action: str,
) -> bool:
    if hass.states.get(entity_id) is None:
        actions.append(f"missing:{entity_id}")
        return False
    changed = await base._set_number(hass, entity_id, value)
    if changed:
        actions.append(f"{action}:{round(float(value), 1)}")
    return changed


async def async_mark_mash_in_started(hass: HomeAssistant) -> dict[str, Any]:
    """Perform the explicit READY -> STARTED physical handoff atomically."""
    store = gate._gate_store(hass)
    state = str(store.get("state") or "idle")

    if state == _COMPLETE_STATE or store.get("completed_once"):
        return {
            **gate.build_mash_in_gate_snapshot(hass),
            "apply_result": "mash_in_started_ignored_after_complete",
            "applied": False,
            "actions": [],
        }
    if state != _READY_STATE:
        return {
            **gate.build_mash_in_gate_snapshot(hass),
            "apply_result": f"mash_in_started_ignored_from:{state}",
            "applied": False,
            "actions": [],
        }

    snapshot = _inject_roles(hass, base.build_orchestration_snapshot(hass))
    blocked = _hard_transition_block(snapshot)
    if blocked is not None:
        return {
            **gate.build_mash_in_gate_snapshot(hass),
            "apply_result": f"mash_in_started_blocked:{blocked}",
            "applied": False,
            "actions": [f"blocked:{blocked}"],
        }

    effective, effective_source, next_target, next_source = gate._effective_mash_in_target(
        hass, snapshot
    )
    effective = _num(effective)
    if effective is None:
        return {
            **gate.build_mash_in_gate_snapshot(hass),
            "apply_result": "mash_in_started_blocked:missing_effective_target",
            "applied": False,
            "actions": ["blocked:missing_effective_target"],
        }

    started_at = dt_util.utcnow().isoformat()
    store.update(
        {
            "state": _STARTED_STATE,
            "started_at": started_at,
            "completed_once": False,
            "effective_target": effective,
            "effective_target_source": effective_source,
            "next_target": next_target,
            "next_target_source": next_source,
            "last_start_result": None,
        }
    )
    gate._update_gate_context(store, snapshot, trigger=_STARTED_STATE)

    actions: list[str] = ["mash_in_started"]
    applied = False

    # Grain-addition boundary: stop circulation first.
    if await _set_if_present(
        hass,
        base.BREWZILLA_PUMP_UTILIZATION,
        gate.PUMP_OFF_UTILIZATION,
        actions,
        "mash_in_started_set_pump_utilization",
    ):
        applied = True
    if hass.states.get(base.BREWZILLA_PUMP_SWITCH) is not None and gate._bool_state(
        hass, base.BREWZILLA_PUMP_SWITCH
    ):
        await base._call_switch(hass, "off", base.BREWZILLA_PUMP_SWITCH)
        actions.append("mash_in_started_pump_off")
        applied = True

    if await _set_if_present(
        hass,
        base.BREWZILLA_TARGET_NUMBER,
        round(effective, 1),
        actions,
        "mash_in_started_set_target",
    ):
        applied = True

    process = _num(snapshot.get("process_temperature"))
    desired_heat, desired_heater_on, heat_phase = _started_heat_request(process, effective)
    if await _set_if_present(
        hass,
        base.BREWZILLA_HEAT_UTILIZATION,
        desired_heat,
        actions,
        "mash_in_started_set_heat_utilization",
    ):
        applied = True

    heater_on = bool(snapshot.get("heater_on"))
    if desired_heater_on and not heater_on and hass.states.get(base.BREWZILLA_HEATER_SWITCH):
        await base._call_switch(hass, "on", base.BREWZILLA_HEATER_SWITCH)
        actions.append("mash_in_started_heater_on")
        applied = True
    elif not desired_heater_on and heater_on and hass.states.get(base.BREWZILLA_HEATER_SWITCH):
        await base._call_switch(hass, "off", base.BREWZILLA_HEATER_SWITCH)
        actions.append("mash_in_started_heater_off")
        applied = True

    result = {
        **snapshot,
        **gate._gate_fields(store, snapshot, pending=False),
        "source": "brewzilla_hot_side_contract",
        "applied": applied,
        "apply_result": "mash_in_started_handoff_applied",
        "actions": actions,
        "requested_target": round(effective, 1),
        "requested_target_source": "mash_in_started_effective_target",
        "desired_pump_on": False,
        "desired_pump_utilization": gate.PUMP_OFF_UTILIZATION,
        "desired_heat_utilization": desired_heat,
        "desired_heater_on": desired_heater_on,
        "mash_in_started_hold_phase": heat_phase,
        "mash_in_started_hold_active": True,
        "mash_in_started_process_temperature": process,
        "mash_in_started_process_temperature_source": snapshot.get("process_temperature_source"),
        "mash_in_started_process_temperature_entity": snapshot.get("process_temperature_entity"),
        "control_reason": (
            f"Mash-In Started: strike authority released to {round(effective, 1)}°C "
            f"({effective_source}); pump OFF/0%; anti-drop heat {desired_heat}% "
            f"({heat_phase}) from canonical process temperature."
        ),
        "executed_at": dt_util.utcnow().isoformat(),
    }
    store["last_start_result"] = {
        "apply_result": result["apply_result"],
        "actions": list(actions),
        "effective_target": round(effective, 1),
        "effective_target_source": effective_source,
        "next_target": next_target,
        "next_target_source": next_source,
        "process_temperature": process,
        "process_temperature_source": snapshot.get("process_temperature_source"),
        "executed_at": result["executed_at"],
    }
    hass.data.setdefault(DOMAIN, {})["brewzilla_last_apply_result"] = result

    await async_record_brewday_audit_event(
        hass,
        "mash_in_started",
        brewzilla_result=result,
        always_record=True,
    )
    return gate.build_mash_in_gate_snapshot(hass)


async def async_confirm_mash_in_complete(hass: HomeAssistant) -> dict[str, Any]:
    """Only STARTED may advance to COMPLETE and restart mash circulation."""
    assert _ORIGINAL_CONFIRM_COMPLETE is not None
    store = gate._gate_store(hass)
    state = str(store.get("state") or "idle")
    if state == _COMPLETE_STATE or store.get("completed_once"):
        return {
            **gate.build_mash_in_gate_snapshot(hass),
            "apply_result": "mash_in_complete_already_complete",
            "applied": False,
            "actions": [],
        }
    if state != _STARTED_STATE:
        return {
            **gate.build_mash_in_gate_snapshot(hass),
            "apply_result": f"mash_in_complete_blocked_from:{state}",
            "applied": False,
            "actions": [],
        }
    return await _ORIGINAL_CONFIRM_COMPLETE(hass)


def install_hot_side_contract() -> None:
    """Install the consolidated pre-mash-in physical contract."""
    global _INSTALLED
    global _ORIGINAL_UNDER_CLEAN
    global _ORIGINAL_GATE_AUGMENT
    global _ORIGINAL_CONFIRM_COMPLETE

    if _INSTALLED:
        return

    # Rebuild the Clean Heatstrike wrapper from the layer immediately below it,
    # injecting canonical process/safety roles before Clean makes decisions.
    _ORIGINAL_UNDER_CLEAN = clean._ORIGINAL_WITH_ADVICE
    if _ORIGINAL_UNDER_CLEAN is None:
        raise RuntimeError("Clean Heatstrike must be installed before hot-side contract")
    advice_control._with_advice = _with_canonical_clean_heatstrike
    clean._gate_temperature = _strict_clean_gate_temperature
    clean._safety_temperature = _canonical_safety_temperature

    # Keep the existing Mash-In FSM/store, but remove actuator decisions from
    # READY and make Started/Complete boundaries explicit and one-way.
    _ORIGINAL_GATE_AUGMENT = gate._augment_snapshot
    _ORIGINAL_CONFIRM_COMPLETE = gate.async_confirm_mash_in_complete
    gate._temperature_for_gate = _strict_gate_temperature
    gate._force_pump_pause = _ready_is_pure_gate
    gate._augment_snapshot = _augment_with_process_roles
    gate.async_mark_mash_in_started = async_mark_mash_in_started
    gate.async_confirm_mash_in_complete = async_confirm_mash_in_complete

    _INSTALLED = True
