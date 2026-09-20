"""Operator-owned, fail-closed BrewZilla observation mode (issue #220).

This blocks BA-originated writes; it never turns BrewZilla outputs OFF when
observation is selected. RCL and BrewZilla remain separate integrations and
physical control is never intercepted. A service call already dispatched before
the toggle cannot be recalled: use the physical controls to verify outputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..entity import BrewAssistantEntity
from ..supervised_apply import clear_pending_action
from . import brewzilla_orchestration as base
from . import brewzilla_source_authority_runtime as authority
from .brewzilla_source_authority_contract import HotSideAuthority
from .brewzilla_owned_control import clear_owned_control
from . import brewzilla_local_control_lease_v2 as local_lease

ENTITY_ID = "switch.brewassistant_brewzilla_observe_only"
REARM_SERVICE = "brewzilla_rearm_after_observe"
DATA_KEY = "brewzilla_observe_only_runtime"
MAX_REARM_AGE_SECONDS = 90
_INSTALLED = False
_PREVIOUS_AUTHORITY = None
_PREVIOUS_SAFE_OFF = None
_PREVIOUS_POLICY_EXECUTE = None
_PREVIOUS_BUILD = None
_PREVIOUS_RAPT_CALL = None


def _store(hass: Any) -> dict[str, Any]:
    # Missing state during HA startup MUST NOT authorize writes.
    return hass.data.setdefault(DOMAIN, {}).setdefault(
        DATA_KEY, {"enabled": True, "rearmed": False, "reason": "startup_fail_closed"},
    )


def observation_required(hass: Any) -> bool:
    state = _store(hass)
    return state.get("enabled") is not False or state.get("rearmed") is not True


def observation_reason(hass: Any) -> str:
    state = _store(hass)
    return "operator_observe_only" if state.get("enabled") is not False else "operator_rearm_required"


def _invalidate(hass: Any, reason: str) -> None:
    """Clear BA intent without emitting actuator services, including OFF/zero."""
    clear_pending_action(hass, reason=reason)
    clear_owned_control(hass, reason=reason)
    lease = local_lease._store(hass)
    lease["previous_lease"] = lease.get("lease")
    lease["lease"] = None
    lease["cleared_at"] = dt_util.utcnow().isoformat()
    lease["clear_reason"] = reason


def _live_authority(hass: Any):
    assert _PREVIOUS_AUTHORITY is not None
    if observation_required(hass):
        return HotSideAuthority("blocked", False, observation_reason(hass)), {
            "runtime": {"source": "None"}, "operator": {"active": False},
            "observe_only": True,
        }
    return _PREVIOUS_AUTHORITY(hass)


def _safe_off_allowed(decision: Any, context: dict[str, Any]) -> bool:
    """No implicit safe-down: OFF/zero is still an actuator command."""
    assert _PREVIOUS_SAFE_OFF is not None
    if context.get("observe_only"):
        return False
    # Re-evaluate the current switch to cover a toggle after the authority read.
    if context.get("hass_observe_only"):
        return False
    return _PREVIOUS_SAFE_OFF(decision, context)


def _protected(value: Any) -> bool:
    """Check actual service payload as well as advertised metadata and aliases."""
    if isinstance(value, (list, tuple, set)):
        return any(_protected(item) for item in value)
    if not isinstance(value, str):
        return False
    item = value.strip().lower()
    protected = (*authority.BREWZILLA_ENTITIES, base.BREWZILLA_MAIN_SWITCH)
    return any(item == canonical or (
        item.startswith(canonical.split(".", 1)[0] + ".")
        and item.endswith("_" + canonical.split(".", 1)[1])
    ) for canonical in protected)


async def _policy_execute(hass: Any, action: dict[str, Any]):
    assert _PREVIOUS_POLICY_EXECUTE is not None
    data = action.get("service_data")
    target = data.get("entity_id") if isinstance(data, Mapping) else None
    if observation_required(hass) and (_protected(target) or _protected(action.get("entity_id"))):
        from .. import control_policy
        return control_policy._store_policy_result(hass, {
            **action, "status": "observe_only_denied",
            "summary": "BrewZilla controlled locally: BA emitted no actuator service.",
        })
    return await _PREVIOUS_POLICY_EXECUTE(hass, action)


def _build(hass: Any) -> dict[str, Any]:
    assert _PREVIOUS_BUILD is not None
    result = _PREVIOUS_BUILD(hass)
    observing = observation_required(hass)
    result.update(
        observe_only_enabled=_store(hass).get("enabled") is not False,
        observe_only_effective=observing,
        observe_only_rearm_required=not _store(hass).get("enabled") and observing,
        observe_only_service=f"{DOMAIN}.{REARM_SERVICE}",
    )
    if observing:
        result = authority._observer_snapshot(result, HotSideAuthority(
            "blocked", False, observation_reason(hass),
        ))
        result.update(
            orchestration_mode="observe-only",
            observe_only_enabled=_store(hass).get("enabled") is not False,
            observe_only_effective=True,
            observe_only_rearm_required=_store(hass).get("enabled") is False,
            observe_only_service=f"{DOMAIN}.{REARM_SERVICE}",
            control_reason=(
                "Endast observation: BA skickar inga BrewZilla-kommandon. "
                "Styr lokalt och verifiera värme/pump på bryggverket."
            ),
        )
    return result


async def _rapt_call(hass: Any, domain: str, service: str, entity_id: str,
                     data: dict[str, Any] | None = None):
    assert _PREVIOUS_RAPT_CALL is not None
    if observation_required(hass):
        raise PermissionError("RAPT/BrewZilla output call blocked: BA observe-only")
    return await _PREVIOUS_RAPT_CALL(hass, domain, service, entity_id, data)


def _reported_fresh(hass: Any, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    if state is None or str(state.state).strip().lower() in {"unknown", "unavailable", "none", ""}:
        return False
    reported = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if reported is None:
        return False
    age = (dt_util.utcnow() - dt_util.as_utc(reported)).total_seconds()
    return 0 <= age <= MAX_REARM_AGE_SECONDS


async def async_rearm(hass: Any) -> None:
    """Explicit second action after switch OFF, with fresh RAPT readback proof."""
    state = _store(hass)
    if state.get("enabled") is not False:
        raise HomeAssistantError("Stäng först av switchen Endast observation.")
    if _PREVIOUS_AUTHORITY is None:
        raise HomeAssistantError("BrewZilla-styrspärren är inte installerad.")
    decision, context = _PREVIOUS_AUTHORITY(hass)
    if decision.mode != "rapt_controller" or decision.may_write_brewzilla is not True:
        raise HomeAssistantError(f"RAPT-källa, session eller säkerhet inte verifierad: {decision.reason}")
    required = (
        base.BREWZILLA_TEMP_SENSOR, base.BREWZILLA_TARGET_NUMBER,
        base.BREWZILLA_HEATER_SWITCH, base.BREWZILLA_PUMP_SWITCH,
        base.BREWZILLA_HEAT_UTILIZATION, base.BREWZILLA_PUMP_UTILIZATION,
    )
    if not all(_reported_fresh(hass, entity) for entity in required):
        raise HomeAssistantError("Färsk BrewZilla-telemetri saknas. Återaktivering nekad.")
    # Clear old plan, output ownership and local lease before making authority visible.
    _invalidate(hass, "observe_only_rearmed_old_plan_revoked")
    state["rearmed"] = True
    state["reason"] = "explicit_operator_rearm"
    from ..brewday.brewday_audit import async_record_brewday_audit_event
    await async_record_brewday_audit_event(hass, "brewzilla_observe_only_rearmed",
        note="Operator explicitly rearmed RAPT hot-side control; new commands may follow."
             " Previously pending commands were discarded.", always_record=True)


class BrewAssistantBrewZillaObserveOnlySwitch(BrewAssistantEntity, RestoreEntity, SwitchEntity):
    """Persistent operator switch; ON is passive and OFF alone never rearms."""

    _attr_has_entity_name = True
    _attr_name = "Endast observation – BrewZilla styrs lokalt"
    _attr_icon = "mdi:eye-outline"
    _attr_unique_id = "brewassistant_switch_brewzilla_observe_only"
    _attr_suggested_object_id = "brewassistant_brewzilla_observe_only"
    _attr_entity_id = ENTITY_ID

    def __init__(self, coordinator: Any) -> None:
        super().__init__(coordinator, "brewzilla_observe_only")
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        restored = await self.async_get_last_state()
        self._attr_is_on = restored is None or restored.state != "off"
        state = _store(self.coordinator.hass)
        state.update(enabled=self._attr_is_on, rearmed=False,
                     reason="restored_observe_only" if self._attr_is_on else "startup_rearm_required")
        _invalidate(self.coordinator.hass, "observe_only_startup")
        hass = self.coordinator.hass
        if not hass.services.has_service(DOMAIN, REARM_SERVICE):
            async def _handle_rearm(call: Any) -> None:
                await async_rearm(hass)
            hass.services.async_register(DOMAIN, REARM_SERVICE, _handle_rearm)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return bool(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        state = _store(self.coordinator.hass)
        state.update(enabled=True, rearmed=False, reason="operator_observe_only")
        self._attr_is_on = True
        self.async_write_ha_state()
        _invalidate(self.coordinator.hass, "observe_only_enabled")
        from ..brewday.brewday_audit import async_record_brewday_audit_event
        await async_record_brewday_audit_event(self.coordinator.hass,
            "brewzilla_observe_only_enabled",
            note="BA actuator writes revoked; no OFF or zero issued. Verify physical BrewZilla locally.",
            always_record=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        state = _store(self.coordinator.hass)
        state.update(enabled=False, rearmed=False, reason="operator_rearm_required")
        self._attr_is_on = False
        self.async_write_ha_state()
        _invalidate(self.coordinator.hass, "observe_only_switch_off_rearm_required")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "ba_source": "brewassistant_brewzilla_observe_only",
            "effective_observe_only": observation_required(self.coordinator.hass),
            "rearm_required": self._attr_is_on is False and observation_required(self.coordinator.hass),
            "rearm_service": f"{DOMAIN}.{REARM_SERVICE}",
            "ba_output_commands_allowed": not observation_required(self.coordinator.hass),
            "physical_outputs_off_verified": False,
            "note": "ON does not send OFF/zero. OFF needs separate explicit rearm; local BrewZilla controls remain independent.",
        }


def install_observe_only_guard() -> None:
    """Last boundary, after RAPT identity/link-loss installation."""
    global _INSTALLED, _PREVIOUS_AUTHORITY, _PREVIOUS_SAFE_OFF
    global _PREVIOUS_POLICY_EXECUTE, _PREVIOUS_BUILD, _PREVIOUS_RAPT_CALL
    if _INSTALLED:
        return
    from .. import control_policy
    from ..brewday import rapt_profile_runtime
    _PREVIOUS_AUTHORITY = authority._live_authority
    _PREVIOUS_SAFE_OFF = authority._safe_off_allowed
    _PREVIOUS_POLICY_EXECUTE = control_policy.execute_action
    _PREVIOUS_BUILD = base.build_orchestration_snapshot
    _PREVIOUS_RAPT_CALL = rapt_profile_runtime._async_call_if_entity_exists
    authority._live_authority = _live_authority
    authority._safe_off_allowed = _safe_off_allowed
    control_policy.execute_action = _policy_execute
    base.build_orchestration_snapshot = _build
    rapt_profile_runtime._async_call_if_entity_exists = _rapt_call
    _INSTALLED = True
