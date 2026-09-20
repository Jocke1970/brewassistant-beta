"""Keep coalesced flight-recorder readbacks truthful when telemetry disappears.

The audit event compactor omits None. Without removing absent volatile keys,
coalescing a new tick retains the previous valid power/temperature as if it
were still measured. This patch is deliberately limited to readback fields.
"""

from __future__ import annotations

from . import brewday_audit as audit

_INSTALLED = False
_PREVIOUS_MERGE = None
_VOLATILE_READBACKS = frozenset({
    "brewzilla_current_temp", "brewzilla_effective_target",
    "brewzilla_device_target", "power_w", "main_power",
    "heater_state", "pump_state",
})


def _merge(existing: dict, event: dict) -> None:
    assert _PREVIOUS_MERGE is not None
    _PREVIOUS_MERGE(existing, event)
    for key in _VOLATILE_READBACKS:
        if key not in event:
            existing.pop(key, None)


def install_missing_readback_guard() -> None:
    global _INSTALLED, _PREVIOUS_MERGE
    if _INSTALLED:
        return
    _PREVIOUS_MERGE = audit._merge_repeated_event
    audit._merge_repeated_event = _merge
    _INSTALLED = True
