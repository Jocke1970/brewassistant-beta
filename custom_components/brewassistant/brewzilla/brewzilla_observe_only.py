"""Fail-closed operator observation for BrewZilla, independent of RCL (issue #220).

ON never sends OFF/zero; commands already dispatched cannot be recalled. The
physical BrewZilla controller and RCL remain independent of BrewAssistant.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, NAME
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
    # Absence of the switch during startup must block every BA output.
    return hass.data.setdefault(DOMAIN, {}).setdefault(
        DATA_KEY, {"enabled": True, "rearmed": False, "reason": "startup_fail_closed"},
    )


def observation_required(hass: Any) -> bool:
    data = _store(hass)
    return data.get("enabled") is not False or data.get("rearmed") is not True


def observation_reason(hass: Any) -> str:
    return "operator_observe_only" if _store(hass).get("enabled") is not False else "operator_rearm_required"


def _invalidate(hass: Any, reason: str) -> None:
    """Discard old intent; absolutely no BrewZilla service is sent here."""
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
    assert _PREVIOUS_SAFE_OFF is not None
    return False if context.get("observe_only") else _PREVIOUS_SAFE_OFF(decision, context)


def _protected(value: Any) -> bool:
    if isinstance(value, (list, tuple, set)):
        return any(_protected(item) for item in value)
    if not isinstance(value, str):
        return False
    value = value.strip().lower()
    return any(value == canonical or (
        value.startswith(canonical.split(".", 1)[0] + ".")
        and value.endswith("_" + canonical.split(".", 1)[1])
    ) for canonical in (*authority.BREWZILLA_ENTITIES, base.BREWZILLA_MAIN_SWITCH))


async def _policy_execute(hass: Any, action: dict[str, Any]):
    assert _PREVIOUS_POLICY_EXECUTE is not None
    payload = action.get("service_data")
    target = payload.get("entity_id") if isinstance(payload, Mapping) else None
    if observation_required(hass) and (_protected(target) or _protected(action.get("entity_id"))):
        from .. import control_policy
        return control_policy._store_policy_result(hass, {
            **action, "status": "observe_only_denied",
            "summary": "BrewZilla controlled locally: no BA actuator service sent.",
        })
    return await _PREVIOUS_POLICY_EXECUTE(hass, action)


def _build(hass: Any) -> dict[str, Any]:
    assert _PREVIOUS_BUILD is not None
    result = _PREVIOUS_BUILD(hass)
    store = _store(hass)
    observing = observation_required(hass)
    fields = dict(observe_only_enabled=store.get("enabled") is not False,
                  observe_only_effective=observing,
                  observe_only_rearm_required=store.get("enabled") is False and observing,
                  observe_only_service=f"{DOMAIN}.{REARM_SERVICE}")
    if observing:
        result = authority._observer_snapshot(result, HotSideAuthority(
            "blocked", False, observation_reason(hass),
        ))
        result.update(orchestration_mode="observe-only",
                      control_reason="Endast observation: BA skickar inga BrewZilla-kommandon. Kontrollera utgångarna lokalt.")
    result.update(fields)
    return result


async def _rapt_call(hass: Any, domain: str, service: str, entity_id: str,
                     data: dict[str, Any] | None = None):
    assert _PREVIOUS_RAPT_CALL is not None
    if observation_required(hass):
        raise PermissionError("BA observe-only blocks RAPT/BrewZilla output commands")
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
    """Separate explicit operator action; no cached pending plan may be reused."""
    store = _store(hass)
    if store.get("enabled") is not False:
        raise HomeAssistantError("Stäng först av switchen Endast observation.")
    if _PREVIOUS_AUTHORITY is None:
        raise HomeAssistantError("Styrspärren är inte installerad.")
    decision, _ = _PREVIOUS_AUTHORITY(hass)
    if decision.mode != "rapt_controller" or decision.may_write_brewzilla is not True:
        raise HomeAssistantError(f"RAPT-session och säkerhet är inte verifierade: {decision.reason}")
    readbacks = (base.BREWZILLA_TEMP_SENSOR, base.BREWZILLA_TARGET_NUMBER,
                 base.BREWZILLA_HEATER_SWITCH, base.BREWZILLA_PUMP_SWITCH,
                 base.BREWZILLA_HEAT_UTILIZATION, base.BREWZILLA_PUMP_UTILIZATION)
    if not all(_reported_fresh(hass, entity) for entity in readbacks):
        raise HomeAssistantError("Färsk BrewZilla-telemetri saknas; återaktivering nekad.")
    _invalidate(hass, "observe_only_rearm_old_plan_revoked")
    store.update(rearmed=True, reason="explicit_operator_rearm")
    from ..brewday.brewday_audit import async_record_brewday_audit_event
    await async_record_brewday_audit_event(hass, "brewzilla_observe_only_rearmed",
        note="Operator explicitly rearmed verified RAPT control. Old pending plans discarded.",
        always_record=True)


class BrewAssistantBrewZillaObserveOnlySwitch(RestoreEntity, SwitchEntity):
    """Self-contained entity to avoid importing the coordinator during package init."""

    _attr_has_entity_name = True
    _attr_name = "Endast observation – BrewZilla styrs lokalt"
    _attr_icon = "mdi:eye-outline"
    _attr_unique_id = "brewassistant_switch_brewzilla_observe_only"
    _attr_suggested_object_id = "brewassistant_brewzilla_observe_only"
    _attr_entity_id = ENTITY_ID

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self._attr_is_on = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": NAME, "manufacturer": "BrewAssistant", "model": "Python Core",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        restored = await self.async_get_last_state()
        self._attr_is_on = restored is None or restored.state != "off"
        _store(self.hass).update(enabled=self._attr_is_on, rearmed=False,
            reason="restored_observe_only" if self._attr_is_on else "startup_rearm_required")
        _invalidate(self.hass, "observe_only_startup")
        if not self.hass.services.has_service(DOMAIN, REARM_SERVICE):
            async def _handle_rearm(call: Any) -> None:
                await async_rearm(self.hass)
            self.hass.services.async_register(DOMAIN, REARM_SERVICE, _handle_rearm)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return bool(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        _store(self.hass).update(enabled=True, rearmed=False, reason="operator_observe_only")
        self._attr_is_on = True
        self.async_write_ha_state()
        _invalidate(self.hass, "observe_only_enabled")
        from ..brewday.brewday_audit import async_record_brewday_audit_event
        await async_record_brewday_audit_event(self.hass, "brewzilla_observe_only_enabled",
            note="BA outputs revoked; no OFF/zero sent. Verify BrewZilla locally.", always_record=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        _store(self.hass).update(enabled=False, rearmed=False, reason="operator_rearm_required")
        self._attr_is_on = False
        self.async_write_ha_state()
        _invalidate(self.hass, "observe_only_switch_off_rearm_required")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "ba_source": "brewassistant_brewzilla_observe_only",
            "effective_observe_only": observation_required(self.hass),
            "rearm_required": not self._attr_is_on and observation_required(self.hass),
            "rearm_service": f"{DOMAIN}.{REARM_SERVICE}",
            "ba_output_commands_allowed": not observation_required(self.hass),
            "physical_outputs_off_verified": False,
            "note": "ON sends no OFF/zero. OFF requires separate rearm; local BrewZilla controls are independent.",
        }


def install_observe_only_guard() -> None:
    """Install after identity/link-loss protection, before platform setup."""
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
