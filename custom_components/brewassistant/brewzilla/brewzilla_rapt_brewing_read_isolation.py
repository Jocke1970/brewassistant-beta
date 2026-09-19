"""Keep BrewTracker *brewing* observations out of an RAPT-owned brewday.

The Brewfather fermentation adapter is intentionally not touched. This is a
scoped compatibility boundary for existing callers while the older BrewTracker
adapter is gradually retired; it does not alter HA's own external integrations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..brewday import brewday_audit_autostart as audit
from ..brewday import brewday_runtime_core as core
from ..brewday import brewfather_ownership as ownership
from ..brewday import rapt_profile_runtime as rapt
from ..brewday.brewday_operator_abort import brewday_operator_abort_snapshot
from . import brewzilla_learning as learning

_INSTALLED = False
_ORIGINALS: dict[str, Callable[..., Any]] = {}
_BT_PREFIXES = ("sensor.brewfather_brew_tracker_", "sensor.brewfather_brewtracker_")


def _bt_entity(entity: Any) -> bool:
    """Identify only BrewTracker entities, never Brewfather fermentation."""
    if isinstance(entity, (tuple, list)):
        return bool(entity) and all(_bt_entity(item) for item in entity)
    return isinstance(entity, str) and entity.startswith(_BT_PREFIXES)


def rapt_owns_brewing(hass: Any) -> bool:
    """Read only RAPT profile and BA's handoff/ABORT state, never BT.

    An unavailable-after-active profile still owns the handoff. A persisted
    RAPT ABORT also keeps BT isolated even though normalized runtime is 'None'.
    """
    profile = rapt._profile_state(hass)
    store = rapt._store(hass)
    operator = brewday_operator_abort_snapshot(hass)
    return bool(
        rapt._active_contract(profile)
        or store.get("was_active")
        or store.get("stop_guard_active")
        or (operator.get("active") and operator.get("source") == rapt.RAPT_PROFILE_SOURCE)
    )


def _read_wrapper(name: str, blocked: Any) -> Callable[..., Any]:
    original = getattr(core, name)
    _ORIGINALS[f"core.{name}"] = original

    def guarded(hass: Any, entity: Any, *args: Any, **kwargs: Any) -> Any:
        if _bt_entity(entity) and rapt_owns_brewing(hass):
            # For state(), preserve the caller's default; never consult BT.
            if name == "state":
                return args[0] if args else kwargs.get("default", "")
            if name == "resolved_entity_id":
                candidates = core.entity_candidates(entity)
                return candidates[0]
            return blocked
        return original(hass, entity, *args, **kwargs)

    return guarded


def _learning_tracker_data(hass: Any) -> tuple[None, None] | Any:
    if rapt_owns_brewing(hass):
        return None, None
    return _ORIGINALS["learning._brewfather_tracker_data"](hass)


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
    """Discard BT events *before* the audit callback accesses their state.

    Keep normal BT event logging if BF is independently selected later.
    """
    def source_filtered(event: Any) -> Any:
        entity = event.data.get("entity_id")
        if _bt_entity(entity) and rapt_owns_brewing(hass):
            return None
        return callback(event)

    return _ORIGINALS["audit.async_track_state_change_event"](hass, entities, source_filtered)


def _batch_guard_bt_active(hass: Any) -> bool:
    if rapt_owns_brewing(hass):
        return False
    return _ORIGINALS["batch_guard._brewfather_tracker_is_active"](hass)


def install_rapt_brewing_read_isolation() -> None:
    """Install once, after source authority, before BA entities are polled."""
    global _INSTALLED
    if _INSTALLED:
        return
    for name, blocked in (("state", None), ("state_obj", None), ("attr", None),
                          ("resolved_entity_id", None)):
        setattr(core, name, _read_wrapper(name, blocked))

    _ORIGINALS["learning._brewfather_tracker_data"] = learning._brewfather_tracker_data
    learning._brewfather_tracker_data = _learning_tracker_data

    for name, replacement in (
        ("_brewfather_status", _audit_bt_status),
        ("_brewfather_backend_available", _audit_bt_available),
        ("_state_available", _audit_state_available),
        ("_entity_state", _audit_entity_state),
        ("async_track_state_change_event", _audit_state_subscription),
    ):
        _ORIGINALS[f"audit.{name}"] = getattr(audit, name)
        setattr(audit, name, replacement)

    # This optional legacy patch can otherwise read BT even after Learning's
    # batch-context reader is source-gated. Import after Learning initialization.
    from . import brewzilla_batch_context_guard as batch_guard
    _ORIGINALS["batch_guard._brewfather_tracker_is_active"] = batch_guard._brewfather_tracker_is_active
    batch_guard._brewfather_tracker_is_active = _batch_guard_bt_active

    # Future imports of the BF batch-phase function get an explicit observer
    # result; existing imports still go through source-gated core primitives.
    original_phase = ownership.brewfather_batch_phase

    def scoped_batch_phase(hass: Any) -> str:
        return "inactive" if rapt_owns_brewing(hass) else original_phase(hass)

    ownership.brewfather_batch_phase = scoped_batch_phase
    _INSTALLED = True
