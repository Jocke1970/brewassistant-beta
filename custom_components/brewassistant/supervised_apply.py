"""Generic supervised apply runtime for BrewAssistant."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

DOMAIN_DATA = "brewassistant"
PENDING_KEY = "supervised_apply_pending_action"
LAST_RESULT_KEY = "supervised_apply_last_result"
EXECUTION_GRANT_KEY = "supervised_apply_execution_grant"
MODE_ENTITY = "select.brewassistant_apply_mode"
PENDING_SENSOR = "sensor.brewassistant_brewzilla_pending_action"
SAFETY_SENSOR = "sensor.brewassistant_brewzilla_safety_state"
READ_ONLY_MODE = "Read only"
SUPERVISED_MODE = "Supervised apply"
INVALID_STATES = {"unknown", "unavailable", "none", ""}

SupervisedExecutor = Callable[[HomeAssistant, dict[str, Any]], Awaitable[dict[str, Any]]]
_EXECUTORS: dict[tuple[str, str], SupervisedExecutor] = {}


def _runtime_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return BrewAssistant hass.data bucket."""
    return hass.data.setdefault(DOMAIN_DATA, {})


def register_supervised_executor(source: str, kind: str, executor: SupervisedExecutor) -> None:
    """Register a direct confirmation executor for one pending-action type.

    Registered executors are invoked only by the explicit CONFIRM button. This
    avoids opening a temporary execution window that an unrelated coordinator
    tick could accidentally consume.
    """
    _EXECUTORS[(source, kind)] = executor


def _executor_for(action: dict[str, Any]) -> SupervisedExecutor | None:
    source = str(action.get("source") or "")
    kind = str(action.get("kind") or "")
    return _EXECUTORS.get((source, kind))


def _schedule_pending_sensor_refresh(hass: HomeAssistant) -> None:
    """Refresh dashboard-facing supervised state without waiting for coordinator cadence."""
    if not hass.services.has_service("homeassistant", "update_entity"):
        return
    hass.async_create_task(
        hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": [PENDING_SENSOR, SAFETY_SENSOR]},
            blocking=False,
        )
    )


async def _record_supervised_event(
    hass: HomeAssistant,
    event_type: str,
    action: dict[str, Any] | None,
    *,
    note: str | None = None,
) -> None:
    """Write high-signal confirmation events into the Brewday flight recorder."""
    try:
        from .brewday.brewday_audit import async_record_brewday_audit_event

        payload = action or {}
        await async_record_brewday_audit_event(
            hass,
            event_type,
            brewzilla_result={
                "apply_result": event_type,
                "actions": [],
            },
            note=note or payload.get("summary"),
            always_record=True,
        )
    except Exception:  # noqa: BLE001 - audit logging must never block safety control
        return


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


def get_execution_grant(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return the currently issued fallback one-shot execution grant, if any."""
    grant = _runtime_data(hass).get(EXECUTION_GRANT_KEY)
    if isinstance(grant, dict):
        return deepcopy(grant)
    return None


def _issue_execution_grant(hass: HomeAssistant, pending: dict[str, Any]) -> dict[str, Any]:
    """Issue a one-shot grant for generic actions without a registered executor."""
    grant = {
        "id": pending.get("id"),
        "source": pending.get("source"),
        "issued_at": dt_util.utcnow().isoformat(),
    }
    _runtime_data(hass)[EXECUTION_GRANT_KEY] = grant
    return deepcopy(grant)


def consume_execution_grant(
    hass: HomeAssistant,
    *,
    action_id: str,
    source: str,
) -> bool:
    """Consume the exact fallback one-shot grant required for execution."""
    runtime = _runtime_data(hass)
    grant = runtime.get(EXECUTION_GRANT_KEY)
    if not isinstance(grant, dict):
        return False
    if grant.get("id") != action_id or grant.get("source") != source:
        return False
    runtime.pop(EXECUTION_GRANT_KEY, None)
    return True


def set_pending_action(hass: HomeAssistant, action: dict[str, Any]) -> dict[str, Any]:
    """Set or update pending supervised action."""
    now = dt_util.utcnow().isoformat()
    pending = deepcopy(action)
    pending.setdefault("id", f"{pending.get('source', 'brewassistant')}:{pending.get('kind', 'action')}:{pending.get('entity_id', 'unknown')}")
    pending.setdefault("created_at", now)
    pending["updated_at"] = now
    pending["status"] = "pending"
    pending["requires_confirmation"] = True
    runtime = _runtime_data(hass)
    runtime[PENDING_KEY] = pending
    # A changed/re-created plan can never inherit a fallback grant from an older action.
    grant = runtime.get(EXECUTION_GRANT_KEY)
    if isinstance(grant, dict) and (
        grant.get("id") != pending.get("id") or grant.get("source") != pending.get("source")
    ):
        runtime.pop(EXECUTION_GRANT_KEY, None)
    _schedule_pending_sensor_refresh(hass)
    return deepcopy(pending)


def clear_pending_action(hass: HomeAssistant, *, reason: str = "cleared") -> dict[str, Any] | None:
    """Clear pending supervised action."""
    runtime = _runtime_data(hass)
    pending = runtime.pop(PENDING_KEY, None)
    runtime.pop(EXECUTION_GRANT_KEY, None)
    if isinstance(pending, dict):
        result = deepcopy(pending)
        result["status"] = reason
        result["resolved_at"] = dt_util.utcnow().isoformat()
        runtime[LAST_RESULT_KEY] = result
        _schedule_pending_sensor_refresh(hass)
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
        await _record_supervised_event(hass, "supervised_no_pending_action", result)
        return deepcopy(result)

    result = deepcopy(pending)
    result["status"] = "executing"
    result["confirmed_at"] = dt_util.utcnow().isoformat()
    runtime[LAST_RESULT_KEY] = result
    await _record_supervised_event(hass, "supervised_confirmed", pending)

    executor = _executor_for(pending)
    if executor is not None:
        try:
            execution_result = await executor(hass, pending)
            result["execution_result"] = deepcopy(execution_result)
            if execution_result.get("supervised_confirmation_consumed"):
                result["status"] = "executed"
                result["executed_at"] = dt_util.utcnow().isoformat()
                await _record_supervised_event(
                    hass,
                    "supervised_executed",
                    pending,
                    note=f"{pending.get('summary')} · {execution_result.get('apply_result')}",
                )
            else:
                result["status"] = "not_executed"
                result["executed_at"] = dt_util.utcnow().isoformat()
                result["reason"] = execution_result.get("apply_result") or "live_plan_not_accepted"
                await _record_supervised_event(
                    hass,
                    "supervised_not_executed",
                    pending,
                    note=f"Confirmed plan was not executed: {result['reason']}",
                )
        except Exception as err:  # noqa: BLE001 - expose service failure in diagnostics
            result["status"] = "error"
            result["error"] = str(err)
            result["executed_at"] = dt_util.utcnow().isoformat()
            await _record_supervised_event(hass, "supervised_error", result, note=str(err))
        finally:
            runtime.pop(EXECUTION_GRANT_KEY, None)
            runtime.pop(PENDING_KEY, None)
            _schedule_pending_sensor_refresh(hass)

        runtime[LAST_RESULT_KEY] = result
        return deepcopy(result)

    # Generic fallback path for supervised actions without a registered direct
    # executor. These retain the one-shot grant behavior.
    domain = pending.get("domain")
    service = pending.get("service")
    service_data = pending.get("service_data")
    if not isinstance(domain, str) or not isinstance(service, str) or not isinstance(service_data, dict):
        result["status"] = "invalid_action"
        runtime[LAST_RESULT_KEY] = result
        runtime.pop(PENDING_KEY, None)
        runtime.pop(EXECUTION_GRANT_KEY, None)
        _schedule_pending_sensor_refresh(hass)
        await _record_supervised_event(hass, "supervised_invalid_action", result)
        return deepcopy(result)

    try:
        _issue_execution_grant(hass, pending)
        await hass.services.async_call(
            domain,
            service,
            service_data,
            blocking=True,
        )
        grant_remaining = get_execution_grant(hass)
        if grant_remaining is None:
            result["status"] = "executed"
            result["executed_at"] = dt_util.utcnow().isoformat()
            await _record_supervised_event(hass, "supervised_executed", pending)
        else:
            result["status"] = "not_executed"
            result["executed_at"] = dt_util.utcnow().isoformat()
            result["reason"] = "execution_grant_not_consumed"
            await _record_supervised_event(
                hass,
                "supervised_not_executed",
                pending,
                note="Confirmed plan was not executed because the live plan no longer matched.",
            )
    except Exception as err:  # noqa: BLE001 - expose service failure in diagnostics
        result["status"] = "error"
        result["error"] = str(err)
        result["executed_at"] = dt_util.utcnow().isoformat()
        await _record_supervised_event(hass, "supervised_error", result, note=str(err))
    finally:
        runtime.pop(EXECUTION_GRANT_KEY, None)
        runtime.pop(PENDING_KEY, None)
        _schedule_pending_sensor_refresh(hass)

    runtime[LAST_RESULT_KEY] = result
    return deepcopy(result)


def cancel_pending_action(hass: HomeAssistant) -> dict[str, Any] | None:
    """Cancel pending supervised action."""
    pending = get_pending_action(hass)
    result = clear_pending_action(hass, reason="cancelled")
    if pending is not None:
        hass.async_create_task(_record_supervised_event(hass, "supervised_cancelled", pending))
    return result


def build_supervised_apply_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Build supervised apply diagnostic snapshot."""
    pending = get_pending_action(hass)
    last_result = get_last_result(hass)
    grant = get_execution_grant(hass)
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
        "execution_grant_active": grant is not None,
        "execution_grant_action_id": grant.get("id") if grant else None,
        "last_result": last_result,
        "last_status": last_result.get("status") if last_result else None,
        "source": "python_supervised_apply_runtime",
    }
