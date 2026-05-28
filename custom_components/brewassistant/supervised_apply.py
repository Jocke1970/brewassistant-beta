"""Generic supervised apply runtime for BrewAssistant."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DOMAIN_DATA = "brewassistant"
PENDING_KEY = "supervised_apply_pending_action"
LAST_RESULT_KEY = "supervised_apply_last_result"
MODE_ENTITY = "select.brewassistant_apply_mode"
READ_ONLY_MODE = "Read only"
SUPERVISED_MODE = "Supervised apply"
INVALID_STATES = {"unknown", "unavailable", "none", ""}


def _runtime_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return BrewAssistant hass.data bucket."""
    return hass.data.setdefault(DOMAIN_DATA, {})


def current_apply_mode(hass: HomeAssistant) -> str:
    """Return current global apply mode."""
    state = hass.states.get(MODE_ENTITY)
    if state is None or state.state in INVALID_STATES:
        return READ_ONLY_MODE
    if state.state != SUPERVISED_MODE:
        return READ_ONLY_MODE
    return SUPERVISED_MODE


def supervised_apply_enabled(hass: HomeAssistant) -> bool:
    """Return true when supervised apply mode is selected."""
    return current_apply_mode(hass) == SUPERVISED_MODE


def get_pending_action(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return pending supervised action."""
    pending = _runtime_data(hass).get(PENDING_KEY)
    if isinstance(pending, dict):
        return deepcopy(pending)
    return None


def get_last_result(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return last supervised action result."""
    result = _runtime_data(hass).get(LAST_RESULT_KEY)
    if isinstance(result, dict):
        return deepcopy(result)
    return None


def set_pending_action(hass: HomeAssistant, action: dict[str, Any]) -> dict[str, Any]:
    """Set or update pending supervised action."""
    now = dt_util.utcnow().isoformat()
    pending = deepcopy(action)
    pending.setdefault("id", f"{pending.get('source', 'brewassistant')}:{pending.get('kind', 'action')}:{pending.get('entity_id', 'unknown')}")
    pending.setdefault("created_at", now)
    pending["updated_at"] = now
    pending["status"] = "pending"
    pending["requires_confirmation"] = True
    _runtime_data(hass)[PENDING_KEY] = pending
    return deepcopy(pending)


def clear_pending_action(hass: HomeAssistant, *, reason: str = "cleared") -> dict[str, Any] | None:
    """Clear pending supervised action."""
    runtime = _runtime_data(hass)
    pending = runtime.pop(PENDING_KEY, None)
    if isinstance(pending, dict):
        result = deepcopy(pending)
        result["status"] = reason
        result["resolved_at"] = dt_util.utcnow().isoformat()
        runtime[LAST_RESULT_KEY] = result
        return deepcopy(result)
    return None


def clear_pending_action_from_source(hass: HomeAssistant, source: str) -> None:
    """Clear pending action if it belongs to a source."""
    pending = get_pending_action(hass)
    if pending is not None and pending.get("source") == source:
        clear_pending_action(hass, reason="cleared_by_source")


async def async_confirm_pending_action(hass: HomeAssistant) -> dict[str, Any]:
    """Confirm and execute the pending supervised action."""
    runtime = _runtime_data(hass)
    pending = get_pending_action(hass)
    if pending is None:
        result = {
            "status": "no_pending_action",
            "confirmed_at": dt_util.utcnow().isoformat(),
            "summary": "No pending supervised action",
        }
        runtime[LAST_RESULT_KEY] = result
        return deepcopy(result)

    domain = pending.get("domain")
    service = pending.get("service")
    service_data = pending.get("service_data")
    if not isinstance(domain, str) or not isinstance(service, str) or not isinstance(service_data, dict):
        result = deepcopy(pending)
        result["status"] = "invalid_action"
        result["confirmed_at"] = dt_util.utcnow().isoformat()
        runtime[LAST_RESULT_KEY] = result
        runtime.pop(PENDING_KEY, None)
        return deepcopy(result)

    result = deepcopy(pending)
    result["status"] = "executing"
    result["confirmed_at"] = dt_util.utcnow().isoformat()
    runtime[LAST_RESULT_KEY] = result

    try:
        await hass.services.async_call(
            domain,
            service,
            service_data,
            blocking=True,
        )
        result["status"] = "executed"
        result["executed_at"] = dt_util.utcnow().isoformat()
    except Exception as err:  # noqa: BLE001 - expose service failure in diagnostics
        result["status"] = "error"
        result["error"] = str(err)
        result["executed_at"] = dt_util.utcnow().isoformat()

    runtime[LAST_RESULT_KEY] = result
    runtime.pop(PENDING_KEY, None)
    return deepcopy(result)


def cancel_pending_action(hass: HomeAssistant) -> dict[str, Any] | None:
    """Cancel pending supervised action."""
    return clear_pending_action(hass, reason="cancelled")


def build_supervised_apply_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build supervised apply diagnostic snapshot."""
    pending = get_pending_action(hass)
    last_result = get_last_result(hass)
    mode = current_apply_mode(hass)
    return {
        "mode": mode,
        "supervised_apply_enabled": mode == SUPERVISED_MODE,
        "has_pending_action": pending is not None,
        "pending_action": pending,
        "pending_action_id": pending.get("id") if pending else None,
        "pending_source": pending.get("source") if pending else None,
        "pending_kind": pending.get("kind") if pending else None,
        "pending_summary": pending.get("summary") if pending else None,
        "last_result": last_result,
        "last_status": last_result.get("status") if last_result else None,
        "source": "python_supervised_apply_runtime",
    }
