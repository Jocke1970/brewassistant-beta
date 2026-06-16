"""Section-scoped BrewAssistant control policy router.

This module keeps production logic and test-batch logic on the same path:
runtime intent -> section policy -> optional confirmation -> real HA service call.

No YAML helpers are required. The entities are created from select.py, switch.py,
sensor/orchestration sensors and button.py.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .supervised_apply import (
    get_last_result as get_supervised_last_result,
    get_pending_action,
    set_pending_action,
)

DOMAIN_DATA = "brewassistant"

READ_ONLY_POLICY = "Read-only"
APPLY_WITH_CONFIRM_POLICY = "Apply with confirm"
DIRECT_ACTION_POLICY = "Direct action"
POLICY_OPTIONS = [READ_ONLY_POLICY, APPLY_WITH_CONFIRM_POLICY, DIRECT_ACTION_POLICY]

SOURCE_BREW_TRACKER = "brew_tracker"
SOURCE_QUICK_SELECT = "quick_select"
SOURCE_MANUAL = "manual"
SOURCE_BACKEND = "backend"

ROUTER_SOURCE = "brewassistant_policy_router"
LAST_POLICY_RESULT_KEY = "control_policy_last_result"

BREWZILLA_TARGET_NUMBER = "number.brewzilla_target_temperature"
BREWZILLA_HEATER_SWITCH = "switch.brewzilla_heater"
BREWZILLA_PUMP_SWITCH = "switch.brewzilla_pump"
KEGERATOR_FAN_SWITCH = "switch.kegerator_fan"
KEGERATOR_SWITCH = "switch.kegerator"

BAD_STATES = {"unknown", "unavailable", "none", ""}

SECTION_CONFIG: dict[str, dict[str, Any]] = {
    "target": {
        "name": "Target temperature",
        "policy_entity": "select.brewassistant_brewzilla_target_policy",
        "direct_unlock_entity": "switch.brewassistant_brewzilla_target_direct_unlocked",
        "default_policy": APPLY_WITH_CONFIRM_POLICY,
        "default_direct_unlocked": True,
    },
    "heater": {
        "name": "Heater",
        "policy_entity": "select.brewassistant_brewzilla_heater_policy",
        "direct_unlock_entity": "switch.brewassistant_brewzilla_heater_direct_unlocked",
        "default_policy": APPLY_WITH_CONFIRM_POLICY,
        "default_direct_unlocked": False,
    },
    "pump": {
        "name": "Pump",
        "policy_entity": "select.brewassistant_brewzilla_pump_policy",
        "direct_unlock_entity": "switch.brewassistant_brewzilla_pump_direct_unlocked",
        "default_policy": APPLY_WITH_CONFIRM_POLICY,
        "default_direct_unlocked": False,
    },
    "boil": {
        "name": "Boil mode",
        "policy_entity": "select.brewassistant_brewzilla_boil_policy",
        "direct_unlock_entity": "switch.brewassistant_brewzilla_boil_direct_unlocked",
        "default_policy": READ_ONLY_POLICY,
        "default_direct_unlocked": False,
    },
    "stage": {
        "name": "Stage advance",
        "policy_entity": "select.brewassistant_brewzilla_stage_policy",
        "direct_unlock_entity": "switch.brewassistant_brewzilla_stage_direct_unlocked",
        "default_policy": APPLY_WITH_CONFIRM_POLICY,
        "default_direct_unlocked": False,
    },
    "cleaning": {
        "name": "Cleaning",
        "policy_entity": "select.brewassistant_brewzilla_cleaning_policy",
        "direct_unlock_entity": "switch.brewassistant_brewzilla_cleaning_direct_unlocked",
        "default_policy": READ_ONLY_POLICY,
        "default_direct_unlocked": False,
    },
    "brew_tracker_feed": {
        "name": "Brew Tracker feed",
        "policy_entity": "select.brewassistant_brew_tracker_feed_policy",
        "direct_unlock_entity": "switch.brewassistant_brew_tracker_feed_direct_unlocked",
        "default_policy": APPLY_WITH_CONFIRM_POLICY,
        "default_direct_unlocked": False,
    },
    "kegerator_fan": {
        "name": "Kegerator fan",
        "policy_entity": "select.brewassistant_kegerator_fan_policy",
        "direct_unlock_entity": "switch.brewassistant_kegerator_fan_direct_unlocked",
        "default_policy": DIRECT_ACTION_POLICY,
        "default_direct_unlocked": True,
    },
    "kegerator_guard": {
        "name": "Kegerator guard",
        "policy_entity": "select.brewassistant_kegerator_guard_policy",
        "direct_unlock_entity": "switch.brewassistant_kegerator_guard_direct_unlocked",
        "default_policy": DIRECT_ACTION_POLICY,
        "default_direct_unlocked": True,
    },
}

SECTION_ALIASES = {
    "target_temperature": "target",
    "temperature": "target",
    "heat": "heater",
    "boil_mode": "boil",
    "stage_advance": "stage",
    "advance": "stage",
    "brewtracker": "brew_tracker_feed",
    "brew_tracker": "brew_tracker_feed",
    "tracker": "brew_tracker_feed",
    "fan": "kegerator_fan",
    "kegeratorfan": "kegerator_fan",
    "kegerator_fan_auto": "kegerator_fan",
    "guard": "kegerator_guard",
    "kegerator_power": "kegerator_guard",
    "kegerator_compressor": "kegerator_guard",
    "compressor": "kegerator_guard",
}


def _runtime_data(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN_DATA, {})


def normalize_section(section: str | None) -> str:
    raw = (section or "").strip().lower()
    return SECTION_ALIASES.get(raw, raw)


def _resolve_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Resolve exact entity id, or same suffix with HA area/prefix added."""
    if hass.states.get(entity_id) is not None:
        return entity_id

    if "." not in entity_id:
        return entity_id

    domain, object_id = entity_id.split(".", 1)
    wanted_suffix = f"_{object_id}"

    for state in hass.states.async_all(domain):
        candidate_object_id = state.entity_id.split(".", 1)[1]
        if candidate_object_id == object_id or candidate_object_id.endswith(wanted_suffix):
            return state.entity_id

    return entity_id


def _state(hass: HomeAssistant, entity_id: str, default: str | None = None) -> str | None:
    resolved = _resolve_entity_id(hass, entity_id)
    obj = hass.states.get(resolved)
    if obj is None or obj.state in BAD_STATES:
        return default
    return obj.state


def _bool(hass: HomeAssistant, entity_id: str, default: bool = False) -> bool:
    raw = _state(hass, entity_id, "on" if default else "off")
    return str(raw).lower() == "on"


def _section_config(section: str) -> dict[str, Any] | None:
    return SECTION_CONFIG.get(normalize_section(section))


def section_policy(hass: HomeAssistant, section: str) -> str:
    config = _section_config(section)
    if config is None:
        return READ_ONLY_POLICY
    policy = _state(hass, str(config["policy_entity"]), str(config["default_policy"]))
    return policy if policy in POLICY_OPTIONS else str(config["default_policy"])


def direct_unlocked(hass: HomeAssistant, section: str) -> bool:
    config = _section_config(section)
    if config is None:
        return False
    return _bool(
        hass,
        str(config["direct_unlock_entity"]),
        bool(config.get("default_direct_unlocked", False)),
    )


def _policy_rank(policy: str) -> int:
    if policy == READ_ONLY_POLICY:
        return 0
    if policy == APPLY_WITH_CONFIRM_POLICY:
        return 1
    if policy == DIRECT_ACTION_POLICY:
        return 2
    return 0


def _rank_policy(rank: int) -> str:
    if rank <= 0:
        return READ_ONLY_POLICY
    if rank == 1:
        return APPLY_WITH_CONFIRM_POLICY
    return DIRECT_ACTION_POLICY


def effective_policy(hass: HomeAssistant, *, section: str, source: str | None = None) -> dict[str, Any]:
    normalized = normalize_section(section)
    main_policy = section_policy(hass, normalized)
    feed_policy = None

    source_normalized = (source or "").strip().lower()
    if source_normalized in {SOURCE_BREW_TRACKER, "brewfather", "brewfather_brew_tracker"}:
        feed_policy = section_policy(hass, "brew_tracker_feed")

    policies = [main_policy]
    if feed_policy is not None:
        policies.append(feed_policy)

    effective = _rank_policy(min(_policy_rank(policy) for policy in policies))
    return {
        "section": normalized,
        "source": source,
        "section_policy": main_policy,
        "feed_policy": feed_policy,
        "effective_policy": effective,
        "direct_unlocked": direct_unlocked(hass, normalized),
        "feed_direct_unlocked": direct_unlocked(hass, "brew_tracker_feed") if feed_policy else None,
    }


def _target_summary(value: Any) -> str:
    try:
        return f"{float(value):.1f} °C"
    except (TypeError, ValueError):
        return str(value)


def build_action(
    *,
    section: str,
    command: str,
    value: Any = None,
    source: str = SOURCE_MANUAL,
    reason: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_section(section)
    rounded_value = round(float(value), 1) if command == "set_target_temperature" and value is not None else value

    domain: str | None = None
    service: str | None = None
    service_data: dict[str, Any] | None = None
    summary = reason or command.replace("_", " ").title()

    if command == "set_target_temperature":
        domain = "number"
        service = "set_value"
        service_data = {"entity_id": BREWZILLA_TARGET_NUMBER, "value": rounded_value}
        summary = reason or f"Set BrewZilla target to {_target_summary(rounded_value)}"

    elif command == "heater_on":
        domain = "switch"
        service = "turn_on"
        service_data = {"entity_id": BREWZILLA_HEATER_SWITCH}
        summary = reason or "Start BrewZilla heater"

    elif command == "heater_off":
        domain = "switch"
        service = "turn_off"
        service_data = {"entity_id": BREWZILLA_HEATER_SWITCH}
        summary = reason or "Stop BrewZilla heater"

    elif command == "pump_on":
        domain = "switch"
        service = "turn_on"
        service_data = {"entity_id": BREWZILLA_PUMP_SWITCH}
        summary = reason or "Start BrewZilla pump"

    elif command == "pump_off":
        domain = "switch"
        service = "turn_off"
        service_data = {"entity_id": BREWZILLA_PUMP_SWITCH}
        summary = reason or "Stop BrewZilla pump"

    elif command == "kegerator_fan_on":
        domain = "switch"
        service = "turn_on"
        service_data = {"entity_id": KEGERATOR_FAN_SWITCH}
        summary = reason or "Start kegerator circulation fan"

    elif command == "kegerator_fan_off":
        domain = "switch"
        service = "turn_off"
        service_data = {"entity_id": KEGERATOR_FAN_SWITCH}
        summary = reason or "Stop kegerator circulation fan"

    elif command == "kegerator_guard_on":
        domain = "homeassistant"
        service = "turn_on"
        service_data = {"entity_id": KEGERATOR_SWITCH}
        summary = reason or "Start kegerator power relay"

    elif command == "kegerator_guard_off":
        domain = "homeassistant"
        service = "turn_off"
        service_data = {"entity_id": KEGERATOR_SWITCH}
        summary = reason or "Stop kegerator power relay"

    action = {
        "source": ROUTER_SOURCE,
        "kind": command,
        "section": normalized,
        "command": command,
        "value": rounded_value,
        "request_source": source,
        "reason": reason,
        "summary": summary,
        "context": dict(context or {}),
    }
    if domain and service and service_data:
        action.update({
            "domain": domain,
            "service": service,
            "service_data": service_data,
        })
        if "entity_id" in service_data:
            action["entity_id"] = service_data["entity_id"]
    return action


def _store_policy_result(hass: HomeAssistant, result: dict[str, Any]) -> dict[str, Any]:
    stored = deepcopy(result)
    stored.setdefault("updated_at", dt_util.utcnow().isoformat())
    _runtime_data(hass)[LAST_POLICY_RESULT_KEY] = stored
    return deepcopy(stored)


def get_last_policy_result(hass: HomeAssistant) -> dict[str, Any] | None:
    result = _runtime_data(hass).get(LAST_POLICY_RESULT_KEY)
    return deepcopy(result) if isinstance(result, dict) else None


async def execute_action(hass: HomeAssistant, action: dict[str, Any]) -> dict[str, Any]:
    domain = action.get("domain")
    service = action.get("service")
    service_data = action.get("service_data")
    result = deepcopy(action)
    result["executed_at"] = dt_util.utcnow().isoformat()

    if not isinstance(domain, str) or not isinstance(service, str) or not isinstance(service_data, dict):
        result["status"] = "unsupported_action"
        result["summary"] = f"Unsupported action: {action.get('command')}"
        return _store_policy_result(hass, result)

    try:
        await hass.services.async_call(domain, service, service_data, blocking=True)
        result["status"] = "executed"
    except Exception as err:  # noqa: BLE001 - expose HA service failures as diagnostics
        result["status"] = "error"
        result["error"] = str(err)

    return _store_policy_result(hass, result)


async def request_action(
    hass: HomeAssistant,
    *,
    section: str,
    command: str,
    value: Any = None,
    source: str = SOURCE_MANUAL,
    reason: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Route an intent through section policy and direct-action locks."""
    normalized = normalize_section(section)
    action = build_action(
        section=normalized,
        command=command,
        value=value,
        source=source,
        reason=reason,
        context=context,
    )
    policy = effective_policy(hass, section=normalized, source=source)
    action["policy"] = policy

    if policy["effective_policy"] == READ_ONLY_POLICY:
        result = {
            **action,
            "status": "read_only",
            "summary": f"Read-only recommendation: {action['summary']}",
            "updated_at": dt_util.utcnow().isoformat(),
        }
        return _store_policy_result(hass, result)

    if policy["effective_policy"] == APPLY_WITH_CONFIRM_POLICY:
        pending = set_pending_action(hass, action)
        result = {
            **pending,
            "status": "pending_confirmation",
            "summary": pending.get("summary"),
            "updated_at": dt_util.utcnow().isoformat(),
        }
        return _store_policy_result(hass, result)

    if not policy["direct_unlocked"]:
        result = {
            **action,
            "status": "direct_action_locked",
            "summary": f"Direct action locked for {normalized}: {action['summary']}",
            "updated_at": dt_util.utcnow().isoformat(),
        }
        return _store_policy_result(hass, result)

    if policy.get("feed_policy") == DIRECT_ACTION_POLICY and not policy.get("feed_direct_unlocked"):
        result = {
            **action,
            "status": "direct_action_locked",
            "summary": f"Direct action locked for Brew Tracker feed: {action['summary']}",
            "updated_at": dt_util.utcnow().isoformat(),
        }
        return _store_policy_result(hass, result)

    return await execute_action(hass, action)


def build_control_policy_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    pending = get_pending_action(hass)
    last_policy_result = get_last_policy_result(hass)
    last_supervised_result = get_supervised_last_result(hass)
    sections = {
        section: {
            "name": str(config["name"]),
            "policy": section_policy(hass, section),
            "direct_unlocked": direct_unlocked(hass, section),
            "policy_entity": _resolve_entity_id(hass, str(config["policy_entity"])),
            "policy_entity_configured": str(config["policy_entity"]),
            "direct_unlock_entity": _resolve_entity_id(hass, str(config["direct_unlock_entity"])),
            "direct_unlock_entity_configured": str(config["direct_unlock_entity"]),
        }
        for section, config in SECTION_CONFIG.items()
    }
    return {
        "source": "python_control_policy",
        "sections": sections,
        "has_pending_action": pending is not None,
        "pending_action": pending,
        "pending_action_id": pending.get("id") if pending else None,
        "pending_section": pending.get("section") if pending else None,
        "pending_command": pending.get("command") if pending else None,
        "pending_summary": pending.get("summary") if pending else None,
        "pending_value": pending.get("value") if pending else None,
        "last_policy_result": last_policy_result,
        "last_policy_status": last_policy_result.get("status") if last_policy_result else None,
        "last_policy_summary": last_policy_result.get("summary") if last_policy_result else None,
        "last_supervised_result": last_supervised_result,
    }
