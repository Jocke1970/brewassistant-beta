"""Keep BrewTracker out of RAPT-owned *brewing decisions*, not out of HA.

BT is our Brewfather-derived brewing extension. Its sensors and BT-specific
informational views may continue to work while RAPT is selected; they must not
supply the normalized RAPT runtime, Learning control context or audit session
selection. The independent Brewfather fermentation adapter is untouched.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..brewday import brewday_audit_autostart as audit
from ..brewday import brewday_runtime_core as core
from ..brewday import rapt_profile_runtime as rapt
from ..brewday.brewday_operator_abort import brewday_operator_abort_snapshot
from . import brewzilla_learning as learning

_INSTALLED = False
_ORIGINALS: dict[str, Callable[..., Any]] = {}
_BT_PREFIXES = ("sensor.brewfather_brew_tracker_", "sensor.brewfather_brewtracker_")


def _bt_entity(entity: Any) -> bool:
    """Identify BT brewing entities without matching BF fermentation entities."""
    if isinstance(entity, (tuple, list)):
        return bool(entity) and all(_bt_entity(item) for item in entity)
    return isinstance(entity, str) and entity.startswith(_BT_PREFIXES)


def _unverified_rapt_profile_on(profile: Any) -> bool:
    """An ON RAPT profile is a competing process even before its contract verifies.

    During startup or a restored/partially published RCL entity, the canonical
    RAPT profile sensor may be ON without the BA marker or a complete step.
    Never let that ambiguous ON state silently promote BT or Manual to an
    actuator-controlling fallback. The marker also supports renamed sensors.
    """
    if profile is None or str(getattr(profile, "state", "")).lower() != "on":
        return False
    if getattr(profile, "entity_id", None) == rapt.RAPT_PROFILE_ENTITY:
        return True
    attrs = getattr(profile, "attributes", {}) or {}
    return attrs.get("ba_source") == rapt.RAPT_PROFILE_BA_SOURCE


def rapt_owns_brewing(hass: Any) -> bool:
    """Resolve active, unverified, lost or stopped RAPT ownership without BT."""
    profile = rapt._profile_state(hass)
    store = rapt._store(hass)
    operator = brewday_operator_abort_snapshot(hass)
    return bool(
        rapt._active_contract(profile)
        or _unverified_rapt_profile_on(profile)
        or store.get("was_active")
        or store.get("stop_guard_active")
        or (operator.get("active") and operator.get("source") == rapt.RAPT_PROFILE_SOURCE)
    )


def _rapt_runtime_snapshot(hass: Any) -> dict[str, Any] | None:
    """Fail closed on an ON profile with missing RCL contract, including startup.

    The RAPT adapter normally returns None before its source marker verifies;
    returning None here would let the old resolver select BT or Manual. Do not
    set was_active, pretend to have a valid step, or send an OFF command.
    """
    previous = _ORIGINALS["rapt.build_rapt_profile_runtime_snapshot"](hass)
    if previous is not None:
        return previous
    profile = rapt._profile_state(hass)
    if not _unverified_rapt_profile_on(profile):
        return None
    return {
        "source": rapt.RAPT_PROFILE_SOURCE,
        "status": "unavailable",
        "source_status": "unverified",
        "runtime_state": "source_unverified",
        "stage": "RAPT Profile",
        "step": "Unverified RAPT profile",
        "raw_step_name": None,
        "next_step": "None",
        "target_temperature": None,
        "target_temperature_source": None,
        "time_remaining_seconds": None,
        "time_remaining_minutes": None,
        "profile_active": None,
        "profile_contract_complete": False,
        "profile_session_id": None,
        "profile_step_id": None,
        "profile_step_number": None,
        "profile_source_available": False,
        "direct_brewzilla_control_allowed": False,
        "control_owner": "unknown_preserve_rapt_handoff",
        "summary": "RAPT profile ON but source/step contract unverified; no BT fallback or new BA commands.",
    }


def _runtime_core_source(hass: Any) -> str:
    """Only the selected process source may enter the normalized runtime."""
    if rapt_owns_brewing(hass):
        return "None"
    return _ORIGINALS["core.source"](hass)


def _runtime_core_snapshot(hass: Any) -> dict[str, Any]:
    """Prevent BT process fields from leaking through legacy core fallbacks.

    Normal Brewday routing checks RAPT first and builds the RAPT snapshot. The
    inactive core result is for older callers and the operator ABORT route;
    it is NEVER a claim that the physical BrewZilla is switched off.
    """
    if rapt_owns_brewing(hass):
        return core.inactive_snapshot()
    return _ORIGINALS["core.build_core_snapshot"](hass)


def _learning_tracker_data(hass: Any) -> tuple[None, None] | Any:
    """Do not silently substitute BT recipe/mash values in RAPT Learning."""
    if rapt_owns_brewing(hass):
        return None, None
    return _ORIGINALS["learning._brewfather_tracker_data"](hass)


def _audit_session_active(hass: Any) -> bool:
    """A BT update cannot start or rotate an RAPT flight-recorder session."""
    if rapt_owns_brewing(hass):
        return False
    return _ORIGINALS["audit.brewfather_session_active"](hass)


def _audit_bt_status(hass: Any) -> str | None:
    if rapt_owns_brewing(hass):
        return None
    return _ORIGINALS["audit._brewfather_status"](hass)


def _audit_bt_available(hass: Any) -> bool:
    if rapt_owns_brewing(hass):
        return False
    return _ORIGINALS["audit._brewfather_backend_available"](hass)


def _audit_state_available(hass: Any, entity: str) -> bool:
    if _bt_entity(entity) and rapt_owns_brewing(hass):
        return False
    return _ORIGINALS["audit._state_available"](hass, entity)


def _audit_entity_state(hass: Any, entity: str) -> Any:
    if _bt_entity(entity) and rapt_owns_brewing(hass):
        return None
    return _ORIGINALS["audit._entity_state"](hass, entity)


def _audit_state_subscription(hass: Any, entities: Any, callback: Callable[..., Any]) -> Any:
    """Ignore BT event *as a brewday trigger* without blocking its HA sensor."""
    def source_filtered(event: Any) -> Any:
        entity = event.data.get("entity_id")
        if _bt_entity(entity) and rapt_owns_brewing(hass):
            return None
        return callback(event)

    return _ORIGINALS["audit.async_track_state_change_event"](hass, entities, source_filtered)


def _batch_guard_bt_active(hass: Any) -> bool:
    """BT cannot assert a competing hot-side batch-control context."""
    if rapt_owns_brewing(hass):
        return False
    return _ORIGINALS["batch_guard._brewfather_tracker_is_active"](hass)


def install_rapt_brewing_read_isolation() -> None:
    """Install process-boundary adapters after the BrewZilla source guard."""
    global _INSTALLED
    if _INSTALLED:
        return

    # This must be in place before the runtime chooses a BT/Manual fallback.
    # It only changes ambiguous RAPT ON and does not forge a verified step.
    _ORIGINALS["rapt.build_rapt_profile_runtime_snapshot"] = rapt.build_rapt_profile_runtime_snapshot
    rapt.build_rapt_profile_runtime_snapshot = _rapt_runtime_snapshot

    # Do NOT monkey-patch core.state/attr/state_obj/resolved_entity_id or
    # brewfather_batch_phase: they are useful in independent BT information
    # views. Only the normalized process-source and snapshot routes are gated.
    _ORIGINALS["core.source"] = core.source
    core.source = _runtime_core_source
    _ORIGINALS["core.build_core_snapshot"] = core.build_core_snapshot
    core.build_core_snapshot = _runtime_core_snapshot

    _ORIGINALS["learning._brewfather_tracker_data"] = learning._brewfather_tracker_data
    learning._brewfather_tracker_data = _learning_tracker_data

    # audit.brewfather_session_active was imported by value: patch that
    # consumer explicitly instead of globally changing the core BT observer.
    _ORIGINALS["audit.brewfather_session_active"] = audit.brewfather_session_active
    audit.brewfather_session_active = _audit_session_active
    for name, replacement in (
        ("_brewfather_status", _audit_bt_status),
        ("_brewfather_backend_available", _audit_bt_available),
        ("_state_available", _audit_state_available),
        ("_entity_state", _audit_entity_state),
        ("async_track_state_change_event", _audit_state_subscription),
    ):
        _ORIGINALS[f"audit.{name}"] = getattr(audit, name)
        setattr(audit, name, replacement)

    from . import brewzilla_batch_context_guard as batch_guard
    _ORIGINALS["batch_guard._brewfather_tracker_is_active"] = batch_guard._brewfather_tracker_is_active
    batch_guard._brewfather_tracker_is_active = _batch_guard_bt_active
    _INSTALLED = True
