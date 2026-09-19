"""Reject mismatched/aliased BrewZilla service targets at the policy boundary.

Normal policy actions include matching canonical entity IDs in their metadata
and service payload. A stale or malformed action must not evade the existing
source guard by disguising its actual HA service target. Unrelated entities and
legacy Manual policy retain the original router behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import control_policy
from . import brewzilla_source_authority_runtime as authority

_INSTALLED = False
_PREVIOUS_EXECUTE = None
_PROTECTED = frozenset((*authority.BREWZILLA_ENTITIES, "switch.brewzilla"))


def _protected(value: Any) -> bool:
    if isinstance(value, (tuple, list, set)):
        return any(_protected(item) for item in value)
    if not isinstance(value, str):
        return False
    entity = value.strip().lower()
    return any(
        entity == canonical or (
            entity.startswith(canonical.split(".", 1)[0] + ".")
            and entity.endswith("_" + canonical.split(".", 1)[1])
        )
        for canonical in _PROTECTED
    )


async def _execute_checked(hass: Any, action: dict[str, Any]) -> dict[str, Any]:
    """Do not trust top-level metadata as the hardware service destination."""
    assert _PREVIOUS_EXECUTE is not None
    data = action.get("service_data")
    payload_entity = data.get("entity_id") if isinstance(data, Mapping) else None
    advertised = action.get("entity_id")
    if _protected(payload_entity) or _protected(advertised):
        decision, _ = authority._live_authority(hass)
        if decision.mode != "manual_legacy_unresolved":
            # Valid canonical actions retain the existing source/Sparge checks.
            # Aliases, list targets and discrepancies are not a safe authority
            # identity, even when HA could resolve them to a physical device.
            if (
                not isinstance(payload_entity, str)
                or payload_entity not in authority.BREWZILLA_ENTITIES
                or advertised != payload_entity
            ):
                return control_policy._store_policy_result(hass, {
                    **action, "status": "source_authority_denied",
                    "summary": "BrewZilla policy target missing, aliased or inconsistent; no HA service call.",
                })
    return await _PREVIOUS_EXECUTE(hass, action)


def install_policy_payload_guard() -> None:
    """Install after source policy; preserve original execution for other devices."""
    global _INSTALLED, _PREVIOUS_EXECUTE
    if _INSTALLED:
        return
    _PREVIOUS_EXECUTE = control_policy.execute_action
    control_policy.execute_action = _execute_checked
    _INSTALLED = True
