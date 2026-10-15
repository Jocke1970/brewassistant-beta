"""Operator-armed BOIL recirculation for CFC / immersion chiller sanitation.

Only a fresh RCL-reported, current, duration-from-start BOIL may qualify.
This module NEVER sends a hardware command: it supplies a DENY-only predicate
and orchestration intent. RAPT/RCL owns the step and normal heater control.

Arming is in-memory and bound to the exact RAPT profile/session/step/observed
transition. Restart, profile change, stale RCL or unknown timer all fail closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from ..brewday import rapt_profile_runtime
from ..brewday.brewday_runtime import build_brewday_runtime_snapshot
from . import brewzilla_temperature as temperature
from ..const import DOMAIN

DATA_KEY = "brewzilla_boil_cooling_choice"
READY = "cfc_ready"
NO_COOLING = "no_cooling"
PENDING = "pending"
CHILL_WINDOW_SECONDS = 15 * 60
MAX_OBSERVATION_AGE_SECONDS = 90


def _timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _identities(attrs: dict[str, Any]) -> tuple[str, str, str, str] | None:
    fields = ("profile_session_id", "profile_id", "step_id",
              "profile_step_transition_observed_at")
    parts = tuple(str(attrs.get(k) or "").strip() for k in fields)
    return parts if all(parts) else None


def observe(hass, *, active_boil: bool, now: datetime | None = None) -> dict[str, Any]:
    """Read-only decision for currently verified BOIL; no inferred STOP.

    An observed RCL transition may lag the real timer by the polling interval;
    this is an *approximate* last-15-min trigger, not a live RAPT countdown.
    """
    result: dict[str, Any] = {
        "boil_cooling_choice": PENDING,
        "boil_cooling_prompt": active_boil,
        "boil_cooling_can_ack": False,
        "boil_cooling_timer_verified": False,
        "boil_cooling_remaining_seconds_estimate": None,
        "boil_cooling_recirc_allowed": False,
        "boil_cooling_reason": "not_current_boil" if not active_boil else "waiting_for_operator",
        "boil_cooling_session_id": None,
        "boil_cooling_profile_id": None,
        "boil_cooling_step_id": None,
        "boil_cooling_transition_at": None,
    }
    def disarm_for_uncertain_source() -> None:
        # Stale/lost RCL authority must invalidate even an armed choice.
        # Returning to the same session ID on reconnect is NOT consent to
        # automatically restart physical CFC circulation.
        hass.data.setdefault(DOMAIN, {}).pop(DATA_KEY, None)

    if not active_boil:
        disarm_for_uncertain_source()
        return result

    profile = rapt_profile_runtime._profile_state(hass)
    if (profile is None or not rapt_profile_runtime._active_contract(profile)
            or profile.attributes.get("profile_contract_complete") is not True
            or profile.attributes.get("profile_active") is not True):
        result["boil_cooling_reason"] = "rcl_profile_unverified"
        disarm_for_uncertain_source()
        return result

    attrs = profile.attributes
    runtime = build_brewday_runtime_snapshot(hass)
    if (str(runtime.get("source") or "") != rapt_profile_runtime.RAPT_PROFILE_SOURCE
            or not temperature._is_current_boil_label(attrs.get("step_name"))):
        result["boil_cooling_reason"] = "rcl_not_current_boil_owner"
        disarm_for_uncertain_source()
        return result
    key = _identities(attrs)
    if key is None:
        result["boil_cooling_reason"] = "rcl_session_or_step_unknown"
        disarm_for_uncertain_source()
        return result
    session, profile_id, step_id, stamp = key
    result.update(
        boil_cooling_session_id=session,
        boil_cooling_profile_id=profile_id,
        boil_cooling_step_id=step_id,
        boil_cooling_transition_at=stamp,
    )

    now = now or datetime.now(timezone.utc)
    observed_at = _timestamp(attrs.get("profile_observed_at"))
    age = (now - observed_at).total_seconds() if observed_at else None
    if age is None or not (0 <= age <= MAX_OBSERVATION_AGE_SECONDS):
        result["boil_cooling_reason"] = "rcl_profile_stale"
        disarm_for_uncertain_source()
        return result

    result["boil_cooling_can_ack"] = True
    selected = hass.data.setdefault(DOMAIN, {}).get(DATA_KEY)
    if isinstance(selected, dict) and selected.get("identity") == key:
        choice = selected.get("choice")
        if choice in {READY, NO_COOLING}:
            result["boil_cooling_choice"] = choice

    if result["boil_cooling_choice"] == NO_COOLING:
        result["boil_cooling_reason"] = "operator_no_cooling"
        return result
    if result["boil_cooling_choice"] == PENDING:
        result["boil_cooling_reason"] = "waiting_for_operator"
        return result

    # Duration from target temperature, manual end types and absent step
    # transition are NOT sufficient to automate pump ON.
    if (str(attrs.get("step_end_type") or "").lower() != "duration"
            or str(attrs.get("step_duration_type") or "").lower() != "start"):
        result["boil_cooling_reason"] = "timer_not_start_based"
        disarm_for_uncertain_source()
        return result

    try:
        length = float(attrs.get("step_length"))
    except (TypeError, ValueError):
        length = math.nan
    transitioned_at = _timestamp(stamp)
    elapsed = (now - transitioned_at).total_seconds() if transitioned_at else -1
    if not (math.isfinite(length) and length > 0 and 0 <= elapsed):
        result["boil_cooling_reason"] = "timer_unavailable"
        disarm_for_uncertain_source()
        return result

    remaining = max(0, length - elapsed)
    result["boil_cooling_timer_verified"] = True
    result["boil_cooling_remaining_seconds_estimate"] = round(remaining)
    if remaining > CHILL_WINDOW_SECONDS:
        result["boil_cooling_reason"] = "waiting_for_last_15_minutes"
        return result

    # Once inside the window, keep intent while the SAME verified current BOIL
    # continues. The actual RAPT step change (not our estimated zero) ends it.
    result["boil_cooling_recirc_allowed"] = True
    result["boil_cooling_reason"] = "operator_ready_last_15_minutes"
    return result


def select(hass, *, choice: str, confirmed: bool,
           expected_session_id: str, expected_profile_id: str,
           expected_step_id: str, expected_transition_at: str,
           active_boil: bool) -> dict[str, Any]:
    """Explicit operator acknowledgement; does not touch BrewZilla hardware."""
    if choice not in {READY, NO_COOLING} or confirmed is not True:
        raise ValueError("Explicit BOIL cooling choice and confirmation required")

    current = observe(hass, active_boil=active_boil)
    if not current["boil_cooling_can_ack"]:
        raise ValueError("Cannot acknowledge without verified current RCL BOIL")

    expected = (expected_session_id, expected_profile_id,
                expected_step_id, expected_transition_at)
    actual = (current["boil_cooling_session_id"],
              current["boil_cooling_profile_id"],
              current["boil_cooling_step_id"],
              current["boil_cooling_transition_at"])
    if not all(expected) or expected != actual:
        raise ValueError("BOIL identity changed; acknowledge the current step again")

    hass.data.setdefault(DOMAIN, {})[DATA_KEY] = {
        "identity": actual, "choice": choice,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    return observe(hass, active_boil=active_boil)
