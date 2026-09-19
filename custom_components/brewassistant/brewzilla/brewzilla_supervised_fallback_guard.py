"""Guard the generic Supervised Apply fallback immediately before HA dispatch.

A generic action can be imported by value before the BrewZilla adapters load.
Guard the synchronous execution-grant issuance, not the public async confirm
function: an earlier guard could be invalidated during awaited audit writes.
Existing registered executors are unaffected. Manual control and unrelated
supervised actions retain their existing behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import supervised_apply
from . import brewzilla_source_authority_runtime as authority

_INSTALLED = False
_PREVIOUS_ISSUE_GRANT = None


def _brewzilla_action(pending: Mapping[str, Any]) -> bool:
    """Check the real service payload as well as action metadata and aliases."""
    data = pending.get("service_data")
    candidates = [pending.get("entity_id")]
    if isinstance(data, Mapping):
        candidates.append(data.get("entity_id"))
    protected = (*authority.BREWZILLA_ENTITIES, "switch.brewzilla")

    def matching(value: Any) -> bool:
        if isinstance(value, (list, tuple, set)):
            return any(matching(item) for item in value)
        if not isinstance(value, str):
            return False
        entity_id = value.strip().lower()
        return any(
            entity_id == canonical
            or (
                entity_id.startswith(canonical.split(".", 1)[0] + ".")
                and entity_id.endswith("_" + canonical.split(".", 1)[1])
            )
            for canonical in protected
        )

    return any(matching(value) for value in candidates)


def _issue_checked_grant(hass: Any, pending: dict[str, Any]) -> dict[str, Any]:
    """Synchronous last check: no await before generic HA service dispatch."""
    assert _PREVIOUS_ISSUE_GRANT is not None
    if _brewzilla_action(pending):
        decision, _ = authority._live_authority(hass)
        if decision.mode != "manual_legacy_unresolved":
            raise PermissionError(
                "Generic Supervised Apply cannot write BrewZilla under "
                f"{decision.mode}; use source/session-bound BrewZilla control."
            )
    return _PREVIOUS_ISSUE_GRANT(hass, pending)


def install_supervised_fallback_guard() -> None:
    """Protect direct generic dispatch without removing any existing controls."""
    global _INSTALLED, _PREVIOUS_ISSUE_GRANT
    if _INSTALLED:
        return
    _PREVIOUS_ISSUE_GRANT = supervised_apply._issue_execution_grant
    supervised_apply._issue_execution_grant = _issue_checked_grant
    _INSTALLED = True
