"""Final RAPT process identity and supervised execution checks for BA writes.

A profile-active flag and session ID alone cannot authorize a BrewZilla write:
the *current* RCL step must agree with the Brewday runtime. An independent
execution guard additionally requires a live supervised-confirmation task for
positive preboil commands.
"""

from __future__ import annotations

from . import brewzilla_source_authority_runtime as authority_runtime
from .brewzilla_source_authority_contract import HotSideAuthority

_INSTALLED = False
_PREVIOUS_AUTHORITY = None
_PREVIOUS_SAFE_OFF = None


def _identity_error(runtime, profile):
    """Return a diagnostic, never authorize missing or contradictory step data."""
    if runtime.get("source") != "RAPT BrewZilla Profile":
        return None
    if profile is None or not hasattr(getattr(profile, "attributes", None), "get"):
        return "rapt_profile_step_unavailable"
    attrs = profile.attributes
    session = str(attrs.get("profile_session_id") or "").strip()
    runtime_session = str(runtime.get("profile_session_id") or "").strip()
    if not session or not runtime_session or session != runtime_session:
        return "rapt_session_identity_mismatch"
    profile_name = str(attrs.get("step_name") or "").strip().casefold()
    runtime_name = str(runtime.get("raw_step_name") or "").strip().casefold()
    if not profile_name or not runtime_name or profile_name != runtime_name:
        return "rapt_step_name_missing_or_mismatched"
    profile_id = str(attrs.get("step_id") or "").strip()
    runtime_id = str(runtime.get("profile_step_id") or "").strip()
    profile_number = attrs.get("step_number")
    runtime_number = runtime.get("profile_step_number")
    if not profile_id and profile_number is None:
        return "rapt_step_identity_missing"
    if bool(profile_id) != bool(runtime_id) or (profile_id and profile_id != runtime_id):
        return "rapt_step_id_missing_or_mismatched"
    if (profile_number is None) != (runtime_number is None):
        return "rapt_step_number_missing_or_mismatched"
    if profile_number is not None:
        try:
            if int(profile_number) < 1 or int(profile_number) != int(runtime_number):
                return "rapt_step_number_missing_or_mismatched"
        except (TypeError, ValueError):
            return "rapt_step_number_missing_or_mismatched"
    return None


def _live_authority(hass):
    """Revoke authority if the current RAPT step is not independently verified."""
    assert _PREVIOUS_AUTHORITY is not None
    decision, context = _PREVIOUS_AUTHORITY(hass)
    if decision.may_write_brewzilla is not True or decision.mode != "rapt_controller":
        return decision, context
    from ..brewday import rapt_profile_runtime

    reason = _identity_error(context["runtime"], rapt_profile_runtime._profile_state(hass))
    if reason is None:
        return decision, context
    return HotSideAuthority("blocked", False, reason), context


def _safe_off_allowed(decision, context):
    """Brewfather observer must not inherit an older RAPT ABORT exception."""
    assert _PREVIOUS_SAFE_OFF is not None
    if context["runtime"].get("source") == "Brewfather Brew Tracker":
        return False
    return _PREVIOUS_SAFE_OFF(decision, context)


def install_rapt_identity_guard():
    """Install after source authority; close write and read bypasses separately."""
    global _INSTALLED, _PREVIOUS_AUTHORITY, _PREVIOUS_SAFE_OFF
    if _INSTALLED:
        return
    _PREVIOUS_AUTHORITY = authority_runtime._live_authority
    _PREVIOUS_SAFE_OFF = authority_runtime._safe_off_allowed
    authority_runtime._live_authority = _live_authority
    authority_runtime._safe_off_allowed = _safe_off_allowed
    from . import brewzilla_sparge_execution_guard
    from . import brewzilla_rapt_brewing_read_isolation
    from . import brewzilla_sparge_local_target_guard
    from . import brewzilla_supervised_fallback_guard
    from . import brewzilla_policy_payload_guard
    from . import brewzilla_direct_entity_guard
    from ..brewday import brewday_rapt_audit_context

    brewzilla_sparge_execution_guard.install_sparge_execution_guard()
    brewzilla_rapt_brewing_read_isolation.install_rapt_brewing_read_isolation()
    # Additive last boundary: conflicting RAPT local targets cannot heat against
    # BA's proposed preboil target; all existing readers and OFF paths remain.
    brewzilla_sparge_local_target_guard.install_sparge_local_target_guard()
    # Logging metadata uses the already normalized snapshot; never selects a source.
    brewday_rapt_audit_context.install_rapt_audit_context()
    # Generic Supervised Apply calls HA directly: gate the synchronous grant
    # immediately before that service call, including captured confirmation imports.
    brewzilla_supervised_fallback_guard.install_supervised_fallback_guard()
    # A forged/mismatched policy action must not hide BZ in service_data.
    brewzilla_policy_payload_guard.install_policy_payload_guard()
    # Direct writer functions must not let prefixed HA entity IDs bypass the
    # canonical source guard; Manual and unrelated devices remain unchanged.
    brewzilla_direct_entity_guard.install_direct_entity_guard()
    _INSTALLED = True
