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
    """Read-only, itemized safety preflight. Green chips NEVER authorize writes."""
    from .brewday_runtime import build_brewday_runtime_snapshot
    from .brewday_operator_abort import brewday_operator_abort_active
    from ..brewzilla import brewzilla_orchestration as bz
    from ..brewzilla import brewzilla_observe_only as observe

    runtime = build_brewday_runtime_snapshot(hass)
    store = _store(hass)
    reasons: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(
        key: str, label: str, status: str, detail: str,
        *, blocking: bool = True,
    ) -> None:
        """Emit one UI diagnostic AND its matching backend-blocking reason."""
        checks.append({
            "id": key, "label": label, "status": status,
            "detail": detail, "blocking": blocking,
        })
        if blocking and status != "passed":
            reasons.append(detail)

    abort = brewday_operator_abort_active(hass)
    check(
        "abort", "ABORT", "failed" if abort else "passed",
        "ABORT är aktiv – fysisk kontroll och separat återaktivering krävs"
        if abort else "Ingen aktiv ABORT-spärr",
    )

    fallback = bool(runtime.get("fallback_active"))
    resync = bool(runtime.get("resync_required"))
    check(
        "fallback", "Återanslutning", "failed" if fallback or resync else "passed",
        "Fallback eller återanslutningsspärr är aktiv – kontrollera källans session/steg"
        if fallback or resync else "Ingen aktiv fallback/resync-spärr",
    )

    mode = str(runtime.get("brewday_mode") or "")
    source = str(runtime.get("source") or "")
    source_ok = mode == RCL_MODE and source == RCL_SOURCE
    check(
        "source", "RCL-källa", "passed" if source_ok else "pending",
        f"Källa: {source or 'saknas'} / läge: {mode or 'saknas'}"
        if source_ok else
        "START stöder endast en redan aktiv RCL-profil – "
        f"nuvarande källa: {source or 'saknas'}, läge: {mode or 'saknas'}",
    )

    profile = _validated_profile(hass, runtime) if source_ok else None
    pa = profile.attributes if profile is not None else {}
    profile_id = str(pa.get("profile_id") or "").strip()
    session_id = str(pa.get("profile_session_id") or "").strip()
    step_id = str(pa.get("step_id") or "").strip()
    step_name = str(pa.get("step_name") or "").strip()
    device_id = str(pa.get("raw_device_id") or "").strip()
    active = (
        profile is not None and profile.state == "on"
        and pa.get("profile_contract_complete") is True
    )
    check(
        "profile", "RAPT-profil", "passed" if active else "pending",
        f"Aktiv profil: {pa.get('profile_name') or profile_id}"
        if active else "Ingen unik aktiv RAPT-profil med komplett verifierat profilkontrakt",
    )
    check(
        "profile_fresh", "RAPT-status", "passed" if _fresh(profile) else "pending",
        f"RAPT-data uppdaterad inom {FRESH_SECONDS} s"
        if _fresh(profile) else f"RAPT-profilens status saknas eller är äldre än {FRESH_SECONDS} s",
    )

    identity_complete = bool(active and all((profile_id, session_id, step_id, step_name, device_id)))
    runtime_session = str(runtime.get("profile_session_id") or "").strip()
    runtime_profile = str(runtime.get("profile_id") or "").strip()
    ids_match = (
        identity_complete
        and runtime_session == session_id
        and runtime_profile == profile_id
    )
    check(
        "session", "Session", (
            "passed" if ids_match else "failed" if identity_complete else "pending"
        ),
        f"Profil och session matchar RCL ({session_id[:8]}…)"
        if ids_match else
        "Profil-/sessions-ID i Brewday matchar inte aktiv RAPT-session"
        if identity_complete else
        "Väntar på verifierat profil-ID, session-ID och BrewZilla-enhet",
    )

    # The RCL adapter exports an immutable profile_step_id. A pretty display
    # label may legitimately differ (e.g. Heat Strike vs Heatstrike). Never
    # let a label alone authorize actuation or hide a real step-ID mismatch.
    runtime_step_id = str(runtime.get("profile_step_id") or "").strip()
    runtime_step_name = str(runtime.get("step") or "").strip()
    step_match = bool(ids_match and step_id and runtime_step_id == step_id)
    if step_match:
        name_differs = runtime_step_name != step_name
        check(
            "step", "Bryggsteg", "passed",
            f"Steg-ID verifierat ({step_id[:8]}…); "
            f"visningsnamn: {runtime_step_name!r} / RAPT: {step_name!r}"
            if name_differs else f"Steg-ID och RAPT-steg matchar: {step_name}",
        )
        if name_differs:
            check(
                "step_label", "Stegnamn", "warning",
                f"Olika visningsnamn ({runtime_step_name!r} / {step_name!r}); "
                "samma verifierade steg-ID – ingen styrspärr",
                blocking=False,
            )
    else:
        check(
            "step", "Bryggsteg", "failed" if identity_complete else "pending",
            f"Steg-ID skiljer: Brewday {runtime_step_id or 'saknas'} / "
            f"RAPT {step_id or 'saknas'} – STOPPA BA START"
            if identity_complete else "Steg-ID kan inte verifieras mot RAPT",
        )

    target = runtime.get("target_temperature")
    p_target = pa.get("step_target_temperature")
    target_valid = _finite(target, 1, 105) and _finite(p_target, 1, 105)
    target_ok = target_valid and abs(float(target) - float(p_target)) <= 0.3
    check(
        "target", "Temperaturmål",
        "passed" if target_ok else "failed" if target_valid else "pending",
        f"RAPT och Brewday: {float(target):.1f} °C"
        if target_ok else
        f"Temperaturmål skiljer: BA {target} °C / RAPT {p_target} °C"
        if target_valid else "RAPT-/Brewday-mål saknas eller är ogiltigt",
    )

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
    stale = [entity for entity in ids if not _fresh(states[entity])]
    check(
        "telemetry", "BZ-telemetri", "pending" if stale else "passed",
        "Saknas/är för gammal (>90 s): " + ", ".join(stale)
        if stale else "Alla sju BZ-värden är färska",
    )
    main = states[bz.BREWZILLA_MAIN_SWITCH]
    check(
        "bz_power", "BZ-ström",
        "passed" if main is not None and main.state == "on" and _fresh(main)
        else "failed" if main is not None and main.state == "off" else "pending",
        "BZ huvudström rapporteras PÅ med färsk status"
        if main is not None and main.state == "on" and _fresh(main)
        else "BrewZilla huvudström är AV – START spärrad"
        if main is not None and main.state == "off"
        else "BrewZilla huvudström saknar färsk PÅ-kvittens",
    )

    temp = states[bz.BREWZILLA_TEMP_SENSOR]
    number_target = states[bz.BREWZILLA_TARGET_NUMBER]
    bzm_ok = (
        _finite(temp.state if temp else None, 0, 105)
        and _finite(number_target.state if number_target else None, 0, 105)
        and _fresh(temp) and _fresh(number_target)
    )
    check(
        "sensors", "BZ-temperatur", "passed" if bzm_ok else "pending",
        "BZ temperatur och device-target kan läsas och är färska"
        if bzm_ok else "BZ temperatur/device-target saknas, är ogiltiga eller för gamla",
    )

    for key, label, switch_id, util_id in (
        ("heater", "Värmare", bz.BREWZILLA_HEATER_SWITCH, bz.BREWZILLA_HEAT_UTILIZATION),
        ("pump", "Pump", bz.BREWZILLA_PUMP_SWITCH, bz.BREWZILLA_PUMP_UTILIZATION),
    ):
        sw = states[switch_id]
        utilization = states[util_id]
        output_ok = (
            sw is not None and sw.state in {"on", "off"} and _fresh(sw)
            and _finite(utilization.state if utilization else None, 0, 100)
            and _fresh(utilization)
        )
        check(
            key, label, "passed" if output_ok else "pending",
            f"{label}: status {sw.state}, utilization {utilization.state} %; färsk återläsning"
            if output_ok else
            f"{label}: status/utilization kan inte verifieras – "
            f"{switch_id}, {util_id}",
        )

    identity = {
        "mode": RCL_MODE, "source": RCL_SOURCE,
        "profile_id": profile_id, "session_id": session_id,
        "step_id": step_id, "step_name": step_name, "device_id": device_id,
    }
    current = store.get("started_identity")
    stable_keys = ("mode", "source", "profile_id", "session_id", "device_id")
    same = isinstance(current, dict) and all(
        current.get(key) == identity.get(key) for key in stable_keys
    )
    readonly = observe.observation_required(hass)
    start_in_flight = bool(store["starting"])
    # During a verified START the switch is intentionally released after
    # preflight and before returning GO. An ordinary manual release is blocked.
    readonly_ok = readonly or start_in_flight or same
    check(
        "read_only", "BA READ-ONLY",
        "passed" if readonly_ok else "failed",
        "READ-ONLY PÅ – BA skriver inte till BrewZilla"
        if readonly else
        "READ-ONLY släppt under verifierad START eller samma session"
        if readonly_ok else
        "BA READ-ONLY är AV utan verifierad START – återställ READ-ONLY",
    )

    if start_in_flight:
        status = "starting"
    elif abort:
        status = "aborted"
    elif same and not readonly and not reasons:
        status = "running"
    elif not readonly and not same:
        status = "blocked"
    elif reasons:
        status = "waiting"
    else:
        status = "ready"

    check(
        "operator", "Startkvittens", "passed" if status == "running" else "pending",
        "START är operatörsbekräftad för denna session"
        if status == "running" else
        "Fysisk kontroll och uttrycklig START-kvittens återstår; "
        "ingen mjukvarukvittens bevisar fysisk säkerhet",
        blocking=False,
    )

    return {
        "status": status,
        "ready": status == "ready",
        "reasons": reasons,
        "checks": checks,
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
        except Exception:
            # A partial HA switch turn_off must never leave BA armed after
            # START validation failed. Reassert observation, fail visibly.
            store["started_identity"] = None
            from ..brewzilla.brewzilla_observe_only import observation_required
            if not observation_required(hass):
                try:
                    await hass.services.async_call(
                        "switch", "turn_on",
                        {"entity_id": "switch.brewassistant_brewzilla_observe_only"},
                        blocking=True,
                    )
                except Exception as rollback_error:
                    raise HomeAssistantError(
                        "START misslyckades OCH återgång till BA READ-ONLY misslyckades. "
                        "Stoppa styrningen fysiskt och kontrollera BrewZilla."
                    ) from rollback_error
            raise
        finally:
            store["starting"] = False
