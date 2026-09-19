"""Prevent BA preboil heat from competing with RAPT's local step regulator.

Preserve existing Sparge, dashboard, BF/BT, and fermentation functionality.
An active manual RAPT Sparge step can retain its own temperature target. BA
must not request 95 C or positive heat against a distinct RAPT target (such as
78 C), even after lift and Supervised Apply confirmation. This additive final
boundary rejects positive writes and removes only the conflicting *proposal*;
it leaves OFF/zero actions and all informational sensors intact. An HA service
result alone never proves that physical outputs are OFF.
"""

from __future__ import annotations

import math
from typing import Any

from ..brewday import rapt_profile_runtime as rapt
from . import brewzilla_orchestration as base
from . import brewzilla_rapt_sparge_controller as sparge
from . import brewzilla_sparge_execution_guard as execution
from . import brewzilla_source_authority_runtime as source

_INSTALLED = False
_PREVIOUS_DECORATE = None
_PREVIOUS_WRITE = None
TARGET_TOLERANCE_C = 0.1


def _profile_target_agrees(hass: Any) -> tuple[bool, float | None]:
    """Require a verified current RAPT Sparge step with the same local target."""
    profile = rapt._profile_state(hass)
    if profile is None or not rapt._active_contract(profile):
        return False, None
    attrs = getattr(profile, "attributes", None)
    if not isinstance(attrs, dict) or attrs.get("profile_contract_complete") is not True:
        return False, None
    if not sparge.state_machine.is_sparge_step(attrs.get("step_name")):
        return False, None
    raw = attrs.get("step_target_temperature")
    try:
        target = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        target = None
    if target is None or not math.isfinite(target):
        return False, None
    return abs(target - sparge.PREBOIL_TARGET_C) <= TARGET_TOLERANCE_C, target


def _decorate(hass: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Display truthful blocked intent; do not hide or remove any sensors."""
    assert _PREVIOUS_DECORATE is not None
    result = _PREVIOUS_DECORATE(hass, snapshot)
    if not result.get("rapt_sparge_active") or result.get("rapt_sparge_phase") != "heat_to_boil":
        return result
    agrees, local_target = _profile_target_agrees(hass)
    out = dict(result)
    out.update(rapt_sparge_local_target_c=local_target,
               rapt_sparge_local_target_agrees=agrees)
    if agrees:
        return out
    reason = ("RAPT Sparge target unavailable" if local_target is None else
              f"RAPT Sparge local target {local_target:.1f} C")
    conflict = (f"{reason} differs from BA preboil {sparge.PREBOIL_TARGET_C:.1f} C; "
                "positive BA heating blocked to avoid competing regulators. "
                "Keep physical outputs under local observation; edit/verify the RAPT profile "
                "target before requesting supervised preboil heat.")
    # Preserve stricter abort/disconnect/fail-passive decisions and their actions.
    if out.get("abort_lockout_active") or out.get("fail_passive_active") or not out.get("connected"):
        out["control_reason"] = f"{out.get('control_reason') or ''} {conflict}".strip()
        return out

    heater, _ = sparge._readback(hass, base.BREWZILLA_HEATER_SWITCH)
    utilization, _ = sparge._readback(hass, base.BREWZILLA_HEAT_UTILIZATION)
    heat = sparge._num(utilization)
    heater_stop = (heater != "off" and hass.states.get(base.BREWZILLA_HEATER_SWITCH) is not None)
    heat_zero = ((heat is None or heat > 0.1) and
                 hass.states.get(base.BREWZILLA_HEAT_UTILIZATION) is not None)
    safe_down = bool(heater_stop or heat_zero or out.get("pump_stop_needed")
                     or out.get("pump_utilization_action_needed"))
    out.update(requested_target=None,
               requested_target_source="rapt_sparge_local_target_conflict_blocked",
               target_sync_needed=False, heating_needed=False,
               desired_heater_on=False, desired_heat_utilization=0.0,
               heater_action_needed=False, heater_stop_needed=heater_stop,
               heat_utilization_action_needed=heat_zero,
               can_apply_target=safe_down,
               orchestration_mode="sparge-local-target-conflict-blocked",
               control_reason=conflict)
    return out


def _write_allowed(hass: Any, entity: str, *, switch_action: str | None = None,
                   value: float | None = None) -> bool:
    """Last actuator boundary: recheck agreement for EACH positive write."""
    assert _PREVIOUS_WRITE is not None
    decision, _ = source._live_authority(hass)
    if decision.mode == "rapt_controller" and sparge._observe(hass).phase == "heat_to_boil":
        if execution._positive_sparge_write(entity, switch_action=switch_action, value=value):
            agrees, _ = _profile_target_agrees(hass)
            if not agrees:
                return False
    return _PREVIOUS_WRITE(hass, entity, switch_action=switch_action, value=value)


def install_sparge_local_target_guard() -> None:
    """Install after the supervised task gate; leave every existing path in place."""
    global _INSTALLED, _PREVIOUS_DECORATE, _PREVIOUS_WRITE
    if _INSTALLED:
        return
    _PREVIOUS_DECORATE = sparge._decorate
    _PREVIOUS_WRITE = source._write_allowed
    sparge._decorate = _decorate
    source._write_allowed = _write_allowed
    _INSTALLED = True
