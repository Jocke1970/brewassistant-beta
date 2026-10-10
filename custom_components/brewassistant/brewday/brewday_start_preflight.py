"""Operator-confirmed Brewday START gate (0b6; RCL attach pilot).

Yellow: not startable; green: current RCL session is verified and can be
explicitly armed; blue: operator START is validating; red: same verified
session has started BA assist. START is NEVER ABORT and never guesses a
loaded-but-not-yet-active RAPT profile's ID. No silent resume after restart.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

DATA_KEY = "brewday_start_preflight"
FRESH_SECONDS = 90
RCL_SOURCE = "RAPT BrewZilla Profile"
RCL_MODE = "RCL Brewing"
RCL_MARKER = "rapt_cloud_link_brewzilla_profile_runtime"


def _store(hass: Any) -> dict[str, Any]:
    return hass.data.setdefault(DOMAIN, {}).setdefault(
        DATA_KEY, {"starting": False, "started_identity": None, "lock": asyncio.Lock()},
    )


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "unknown", "unavailable", "none", "null"}


def _finite(value: Any, minimum: float, maximum: float) -> bool:
    if _bad(value):
        return False
    try:
        number = float(value)
        return math.isfinite(number) and minimum <= number <= maximum
    except (TypeError, ValueError):
        return False


def _fresh(state: Any) -> bool:
    if state is None or _bad(state.state):
        return False
    timestamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if timestamp is None:
        return False
    try:
        age = (dt_util.utcnow() - dt_util.as_utc(timestamp)).total_seconds()
        return 0 <= age <= FRESH_SECONDS
    except (ValueError, TypeError, OverflowError, AttributeError):
        return False


def _validated_profile(hass: Any, runtime: dict[str, Any]) -> Any | None:
    """Resolve exactly one RCL sensor; never attach to an arbitrary device."""
    try:
        candidates = [
            state for state in hass.states.async_all()
            if state.entity_id.startswith("binary_sensor.")
            and state.attributes.get("ba_source") == RCL_MARKER
        ]
    except AttributeError:
        return None
    expected_entity = runtime.get("source_entity")
    if len(candidates) != 1 or _bad(expected_entity):
        return None
    state = candidates[0]
    return state if state.entity_id == expected_entity else None


def preflight_snapshot(hass: Any) -> dict[str, Any]:
    """Read-only evaluation; it makes NO HA service or physical calls."""
    from .brewday_runtime import build_brewday_runtime_snapshot
    from .brewday_operator_abort import brewday_operator_abort_active
    from ..brewzilla import brewzilla_orchestration as bz
    from ..brewzilla import brewzilla_observe_only as observe

    runtime = build_brewday_runtime_snapshot(hass)
    store = _store(hass)
    reasons: list[str] = []
    abort = brewday_operator_abort_active(hass)
    if abort:
        reasons.append("ABORT är aktiv – kräver separat fysisk kontroll och återaktivering")
    if runtime.get("fallback_active") or runtime.get("resync_required"):
        reasons.append("Fallback eller återanslutningsspärr är aktiv")
    mode = str(runtime.get("brewday_mode") or "")
    source = str(runtime.get("source") or "")
    if mode != RCL_MODE or source != RCL_SOURCE:
        reasons.append(
            "START-preflight stöder ännu endast verifierad, redan aktiv RCL-profil; "
            "Manual/Brewfather och start av laddad RAPT-profil behöver separat källflöde"
        )
    profile = _validated_profile(hass, runtime) if source == RCL_SOURCE else None
    pa = profile.attributes if profile is not None else {}
    profile_id = str(pa.get("profile_id") or "")
    session_id = str(pa.get("profile_session_id") or "")
    step_id = str(pa.get("step_id") or "")
    step_name = str(pa.get("step_name") or "")
    device_id = str(pa.get("raw_device_id") or "")
    if (
        profile is None or profile.state != "on" or
        pa.get("profile_contract_complete") is not True or
        not all((profile_id, session_id, step_id, step_name, device_id))
    ):
        reasons.append("Ingen unik aktiv RAPT-profil med verifierat recept, session, steg och BZ-id")
    if profile is not None and not _fresh(profile):
        reasons.append("RAPT-profilens status är för gammal eller otillgänglig")
    target = runtime.get("target_temperature")
    p_target = pa.get("step_target_temperature")
    if (
        not _finite(target, 1, 105)
        or not _finite(p_target, 1, 105)
        or abs(float(target) - float(p_target)) > 0.3
    ):
        reasons.append("RAPT-mål och Brewday-mål är inte verifierat synkroniserade")
    if str(runtime.get("step") or "") != step_name:
        reasons.append("Brewday-steg stämmer inte med verifierat RAPT-steg")

    ids = (
        bz.BREWZILLA_TEMP_SENSOR,
        bz.BREWZILLA_TARGET_NUMBER,
        bz.BREWZILLA_HEATER_SWITCH,
        bz.BREWZILLA_PUMP_SWITCH,
        bz.BREWZILLA_HEAT_UTILIZATION,
        bz.BREWZILLA_PUMP_UTILIZATION,
        bz.BREWZILLA_MAIN_SWITCH,
    )
    states = {entity: hass.states.get(entity) for entity in ids}
    for entity in ids:
        if not _fresh(states[entity]):
            reasons.append(f"BrewZilla-telemetri saknas/är äldre än {FRESH_SECONDS}s: {entity}")
    if not _finite(states[bz.BREWZILLA_TEMP_SENSOR].state if states[bz.BREWZILLA_TEMP_SENSOR] else None, 0, 105):
        reasons.append("BrewZilla-temperaturen kan inte verifieras")
    for entity in (bz.BREWZILLA_HEAT_UTILIZATION, bz.BREWZILLA_PUMP_UTILIZATION):
        state = states[entity]
        if not _finite(state.state if state else None, 0, 100):
            reasons.append(f"Utilization okänd/ogiltig: {entity}")
    for entity in (bz.BREWZILLA_HEATER_SWITCH, bz.BREWZILLA_PUMP_SWITCH):
        state = states[entity]
        if state is None or state.state not in {"on", "off"}:
            reasons.append(f"Utgångsstatus okänd: {entity}")
    main = states[bz.BREWZILLA_MAIN_SWITCH]
    if main is None or main.state != "on":
        reasons.append("BrewZilla huvudström är inte verifierat PÅ")

    identity = {
        "mode": RCL_MODE,
        "source": RCL_SOURCE,
        "profile_id": profile_id,
        "session_id": session_id,
        "step_id": step_id,
        "step_name": step_name,
        "device_id": device_id,
    }
    current = store.get("started_identity")
    same = current is not None and current == identity
    readonly = observe.observation_required(hass)
    if store["starting"]:
        status = "starting"
    elif abort:
        status = "aborted"
    elif same and not readonly and not reasons:
        status = "running"
    elif not readonly:
        reasons.append("BA styr redan utan verifierad START för denna session – aktivera READ-ONLY")
        status = "blocked"
    elif reasons:
        status = "waiting"
    else:
        status = "ready"

    return {
        "status": status,
        "ready": status == "ready",
        "reasons": reasons,
        "mode": mode,
        "source": source,
        "identity": identity if profile is not None else None,
        "read_only": readonly,
        "target_temperature": target,
        "operator_confirmation_required": True,
        "can_start_rapt_profile": False,  # no attested loaded-profile ID available before session
        "start_scope": "attach_ba_rcl_assist_to_existing_verified_rapt_session",
        "hardware_start_confirmed": False,
        "physical_outputs_off_verified": False,
    }


async def async_start_verified(
    hass: Any,
    *,
    confirmed: bool,
    expected_session_id: str,
    expected_step_id: str,
    expected_profile_id: str,
) -> dict[str, Any]:
    """Explicit START only for an already active attested RAPT session.

    This arms BA RCL Assist via the existing guarded read-only switch.
    It does not start or switch RAPT profiles, and it never guesses IDs.
    """
    store = _store(hass)
    if confirmed is not True:
        raise HomeAssistantError("START kräver uttrycklig operatörsbekräftelse.")
    async with store["lock"]:
        before = preflight_snapshot(hass)
        if not before["ready"]:
            raise HomeAssistantError("START nekad: " + "; ".join(before["reasons"]))
        identity = before["identity"]
        if not identity or (
            str(expected_session_id) != identity["session_id"]
            or str(expected_step_id) != identity["step_id"]
            or str(expected_profile_id) != identity["profile_id"]
        ):
            raise HomeAssistantError("START nekad: profil/session/steg ändrades efter preflight.")
        store["starting"] = True
        try:
            # Recheck every condition just before requesting BA writes.
            still = preflight_snapshot(hass)
            if still["reasons"] or still["identity"] != identity:
                raise HomeAssistantError("START nekad: källans identitet eller telemetri ändrades.")
            await hass.services.async_call(
                "switch", "turn_off",
                {"entity_id": "switch.brewassistant_brewzilla_observe_only"},
                blocking=True,
            )
            from ..brewzilla.brewzilla_observe_only import observation_required
            if observation_required(hass):
                raise HomeAssistantError("START misslyckades: BA är fortfarande i read-only.")
            # Attest the *same* source after enabling. Never mark running on an
            # unverified session. On mismatch return to observe-only.
            after = preflight_snapshot(hass)
            if after["identity"] != identity or after["reasons"]:
                await hass.services.async_call(
                    "switch", "turn_on",
                    {"entity_id": "switch.brewassistant_brewzilla_observe_only"},
                    blocking=True,
                )
                raise HomeAssistantError("Källan ändrades under START; BA återställd till read-only.")
            store["started_identity"] = identity
            return preflight_snapshot(hass)
        finally:
            store["starting"] = False
