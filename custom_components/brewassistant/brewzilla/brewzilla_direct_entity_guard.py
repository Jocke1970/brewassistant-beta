"""Reject alternative BrewZilla entity IDs in the BA direct writer boundary.

The source-authority writer recognizes five canonical entities. Older HA setups
may prefix their object IDs; such aliases must not bypass the final decision.
Preserve Manual's existing policy and all unrelated equipment/functionality.
"""

from __future__ import annotations

from typing import Any

from . import brewzilla_source_authority_runtime as source

_INSTALLED = False
_PREVIOUS_WRITE = None
_PROTECTED = frozenset((*source.BREWZILLA_ENTITIES, "switch.brewzilla"))


def _protected_entity(entity: Any) -> bool:
    if not isinstance(entity, str):
        return False
    normalized = entity.strip().lower()
    return any(
        normalized == canonical
        or (
            normalized.startswith(canonical.split(".", 1)[0] + ".")
            and normalized.endswith("_" + canonical.split(".", 1)[1])
        )
        for canonical in _PROTECTED
    )


def _write_allowed(
    hass: Any, entity: str, *, switch_action: str | None = None,
    value: float | None = None,
) -> bool:
    """Only canonical actuator destinations may use RAPT source authority."""
    assert _PREVIOUS_WRITE is not None
    if _protected_entity(entity) and entity not in source.BREWZILLA_ENTITIES:
        decision, _ = source._live_authority(hass)
        if decision.mode != "manual_legacy_unresolved":
            return False
    return _PREVIOUS_WRITE(
        hass, entity, switch_action=switch_action, value=value,
    )


def install_direct_entity_guard() -> None:
    """Wrap the live check, preserving existing source and Sparge restrictions."""
    global _INSTALLED, _PREVIOUS_WRITE
    if _INSTALLED:
        return
    _PREVIOUS_WRITE = source._write_allowed
    source._write_allowed = _write_allowed
    _INSTALLED = True
