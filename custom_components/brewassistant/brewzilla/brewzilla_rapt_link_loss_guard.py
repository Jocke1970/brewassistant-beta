"""Fail-passive BA/RCL handoff guard for issue #217.

RCL/BrewZilla keep operating without BA. Missing or old telemetry can revoke BA
write authority, but MUST NEVER be promoted to STOP or cause output commands.
An observed STOP updates BA's state only; explicit operator STOP/ABORT is a
separate command transaction through RCL and must not be replayed on readback.
Install last, after source authority and the RAPT identity guard.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..brewday import rapt_profile_runtime as runtime

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_BASE_CALL = None
_BASE_ACTIVE = None
_BASE_STOP = None
_MAX_AGE_SECONDS = 90
_LISTENER_ENTITY_KEY = "rapt_brewzilla_profile_runtime_listener_entity"
_AMBIGUOUS_ENTITY = "binary_sensor.brewzilla_profile_ambiguous"
# Active identity is learned only from a fresh, non-restored RCL ON state in
# this HA process; no cached/restored OFF state can grant STOP.
_OBSERVED_SESSIONS: dict[str, str] = {}


def _recent(state, *, changed: bool = False) -> bool:
    if state is None:
        return False
    timestamp = (getattr(state, "last_changed", None) if changed else
                 getattr(state, "last_reported", None) or getattr(state, "last_updated", None))
    if timestamp is None:
        return False
    try:
        age = (dt_util.utcnow() - dt_util.as_utc(timestamp)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return False
    return 0 <= age <= _MAX_AGE_SECONDS


def _profile_state(hass):
    """Find real entity by marker; keep restored/ambiguous ON as unverified.

    A restored ON must reach read-isolation's ownership lockout, even though
    _is_rcl_contract refuses it as actuation evidence. When multiple devices
    are indistinguishable, expose a *restored* unverified synthetic ON to the
    existing read-isolation guard. It cannot authorize active/STOP or be used
    as a real service target; do not subscribe to its synthetic entity ID.
    """
    previous = runtime._store(hass).get("last_known", {}).get("entity_id")
    try:
        candidates = [
            state for state in hass.states.async_all()
            if state.entity_id.startswith("binary_sensor.")
            and (
                state.attributes.get("ba_source") == runtime.RAPT_PROFILE_BA_SOURCE
                or state.entity_id == runtime.RAPT_PROFILE_ENTITY
                or (previous and state.entity_id == previous)
            )
        ]
    except (AttributeError, TypeError):
        candidates = []
    if previous:
        for state in candidates:
            if state.entity_id == previous:
                return state
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # This is an ownership LOCKOUT hint, not fabricated live telemetry.
        return SimpleNamespace(
            entity_id=_AMBIGUOUS_ENTITY,
            state="on",
            attributes={
                "ba_source": runtime.RAPT_PROFILE_BA_SOURCE,
                "restored": True,
                "profile_contract_complete": False,
                "ambiguous_profile_entities": [state.entity_id for state in candidates],
            },
        )
    return None


def _active_fresh(state):
    assert _BASE_ACTIVE is not None
    active = bool(_BASE_ACTIVE(state) and _recent(state))
    if active:
        session = str(state.attributes.get("profile_session_id") or "").strip()
        if session:
            _OBSERVED_SESSIONS[state.entity_id] = session
    return active


def _attested_stop(state):
    """OFF alone is not STOP; require fresh, matching RCL attestation."""
    assert _BASE_STOP is not None
    if not (_BASE_STOP(state) and _recent(state) and _recent(state, changed=True)):
        return False
    attrs = state.attributes
    identity = str(attrs.get("profile_stopped_session_id") or "").strip()
    return bool(attrs.get("profile_stop_confirmed") is True and identity
                and _OBSERVED_SESSIONS.get(state.entity_id) == identity)


def _ensure_transition_listener(hass):
    """Follow actual RCL entity, rebind on ID changes, never invent STOP."""
    data = hass.data.setdefault(DOMAIN, {})
    state = runtime._profile_state(hass)
    if state is not None and state.entity_id == _AMBIGUOUS_ENTITY:
        # Discard any prior listener; no arbitrary physical owner is chosen.
        previous_unsub = data.pop(runtime.LISTENER_KEY, None)
        if callable(previous_unsub):
            previous_unsub()
        data.pop(_LISTENER_ENTITY_KEY, None)
        return
    target = (state.entity_id if state is not None else
              runtime._store(hass).get("last_known", {}).get("entity_id"))
    if not target:
        return
    if data.get(_LISTENER_ENTITY_KEY) == target and runtime.LISTENER_KEY in data:
        return
    previous_unsub = data.pop(runtime.LISTENER_KEY, None)
    if callable(previous_unsub):
        previous_unsub()

    @callback
    def _state_changed(event):
        new = event.data.get("new_state")
        # None, unknown and unavailable enter the original no-write branch.
        # Only an attested, fresh, matching OFF may update STOP state.
        if new is not None and new.entity_id != target:
            return
        hass.async_create_task(runtime._async_process_transition(hass, new))

    data[runtime.LISTENER_KEY] = async_track_state_change_event(hass, [target], _state_changed)
    data[_LISTENER_ENTITY_KEY] = target


async def _guarded_safe_off_call(hass, domain, service, entity_id, data=None):
    """Retain proof validation for legacy callers; never infer OFF from loss."""
    assert _BASE_CALL is not None
    state = runtime._profile_state(hass)
    known = runtime._store(hass).get("last_known", {})
    if not runtime._fresh_stopped_contract(state):
        raise PermissionError("RCL STOP proof lost; no BA output write")
    stopped = state.attributes.get("profile_stopped_session_id")
    if not stopped or stopped != known.get("profile_session_id"):
        raise PermissionError("RCL STOP identity mismatch; no BA output write")
    return await _BASE_CALL(hass, domain, service, entity_id, data)


async def _observe_stop_without_output_commands(hass, token):
    """A delayed STOP readback is a state event, NOT another command intent.

    _mark_confirmed_stop already records STOP and clears BA-owned control.
    RCL handles operator STOP/ABORT as its own command; do not fire the old
    heater OFF / pump OFF / zero-utilization sequence on status propagation.
    An external RAPT STOP is likewise observational: no implicit actuator
    commands or claims that the physical outputs have been verified OFF.
    """
    store = runtime._store(hass)
    if store.get("safe_off_token") == token:
        return
    store["safe_off_token"] = token
    store["last_safe_off"] = {
        "token": token,
        "at": dt_util.utcnow().isoformat(),
        "actions": [],
        "errors": [],
        "ok": None,
        "reason": "observed_profile_stop_status_only_no_output_commands",
        "outputs_physically_off_verified": False,
    }
    _LOGGER.info("RAPT STOP observed; BA issued no additional BrewZilla output commands")


def install_rapt_link_loss_guard():
    """Install a fail-passive boundary without altering upstream RCL code."""
    global _INSTALLED, _BASE_CALL, _BASE_ACTIVE, _BASE_STOP
    if _INSTALLED:
        return
    _BASE_ACTIVE = runtime._active_contract
    _BASE_STOP = runtime._fresh_stopped_contract
    _BASE_CALL = runtime._async_call_if_entity_exists
    runtime._profile_state = _profile_state
    runtime._active_contract = _active_fresh
    runtime._fresh_stopped_contract = _attested_stop
    runtime._ensure_transition_listener = _ensure_transition_listener
    runtime._async_call_if_entity_exists = _guarded_safe_off_call
    # Last override intentionally supersedes the original four-command
    # post-STOP safe-off routine. Observed STOP must not replay an ABORT.
    runtime._async_safe_off_after_profile_stop = _observe_stop_without_output_commands
    _INSTALLED = True
    _LOGGER.info("RAPT link-loss guard installed; STOP readback is status-only")
