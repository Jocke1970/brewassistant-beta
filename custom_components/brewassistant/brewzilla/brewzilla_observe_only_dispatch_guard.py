"""Additional last-boundary protection for BA observation-only operation.

This is deliberately scoped to BA's own policy router and direct BrewZilla
writer. It never intercepts RCL or Home Assistant calls from the operator or
other integrations. Observing does not send OFF, zero or profile commands.
"""

from __future__ import annotations

from typing import Any

from .. import control_policy
from . import brewzilla_observe_only as observer
from . import brewzilla_source_authority_runtime as authority

_INSTALLED = False
_PREVIOUS_REQUEST = None
_PREVIOUS_WRITE_ALLOWED = None


def _action_is_brewzilla(action: dict[str, Any]) -> bool:
    """Check the actual destination as well as the advertised one."""
    payload = action.get("service_data")
    target = payload.get("entity_id") if isinstance(payload, dict) else None
    return observer._protected(target) or observer._protected(action.get("entity_id"))


async def _request_action(
    hass: Any, *, section: str, command: str, value: Any = None,
    source: str = control_policy.SOURCE_MANUAL,
    reason: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Do not create a misleading pending confirmation while observing."""
    assert _PREVIOUS_REQUEST is not None
    if observer.observation_required(hass):
        action = control_policy.build_action(
            section=section, command=command, value=value,
            source=source, reason=reason, context=context,
        )
        if _action_is_brewzilla(action):
            return control_policy._store_policy_result(hass, {
                **action,
                "status": "observe_only_denied",
                "summary": "Endast observation: ingen ny BrewZilla-kvittens skapades.",
            })
    return await _PREVIOUS_REQUEST(
        hass, section=section, command=command, value=value,
        source=source, reason=reason, context=context,
    )


def _write_allowed(
    hass: Any, entity: str, *, switch_action: str | None = None,
    value: float | None = None,
) -> bool:
    """Include the master switch and prefixed entity IDs in BA's last guard."""
    assert _PREVIOUS_WRITE_ALLOWED is not None
    if observer.observation_required(hass) and observer._protected(entity):
        return False
    return _PREVIOUS_WRITE_ALLOWED(
        hass, entity, switch_action=switch_action, value=value,
    )


def install_observe_only_dispatch_guard() -> None:
    """Install after source, identity and observation guards."""
    global _INSTALLED, _PREVIOUS_REQUEST, _PREVIOUS_WRITE_ALLOWED
    if _INSTALLED:
        return
    _PREVIOUS_REQUEST = control_policy.request_action
    _PREVIOUS_WRITE_ALLOWED = authority._write_allowed
    control_policy.request_action = _request_action
    authority._write_allowed = _write_allowed
    _INSTALLED = True
