"""Add source-specific diagnostics to the existing Brewday flight recorder.

Logging only. This module does not inspect BT/BF to choose a brewing source,
create a session, or issue hardware commands. Existing event keys are retained.
"""

from __future__ import annotations

import json

from . import brewday_audit as audit

_INSTALLED = False
_PREVIOUS_SIGNATURE = None

# These values come from the SAME normalized runtime snapshot already used by
# audit._runtime_context; they are not a second source arbitration or sensor poll.
EXTRA_RUNTIME_FIELDS = (
    "source_status",
    "target_temperature_source",
    "snapshot_updated_at",
    "profile_source_available",
    "profile_contract_complete",
    "profile_session_id",
    "profile_step_id",
    "profile_step_number",
    "profile_step_pid_enabled",
    "rapt_directive_target_temperature",
    "rapt_effective_ba_target_temperature",
    "profile_stop_guard_active",
    "profile_stop_confirmed",
    "operator_control_state",
    "operator_abort_active",
    "operator_abort_source",
    "direct_brewzilla_control_allowed",
)

EXTRA_RESULT_FIELDS = (
    "requested_target_source",
    "rapt_sparge_active",
    "rapt_sparge_phase",
    "rapt_sparge_local_target_c",
    "rapt_sparge_local_target_agrees",
    "abort_lockout_active",
    "fail_passive_active",
)

IDENTITY_FIELDS = (
    "profile_session_id",
    "profile_step_id",
    "profile_step_number",
    "profile_stop_guard_active",
    "operator_abort_active",
    "rapt_sparge_phase",
    "rapt_sparge_local_target_agrees",
)


def _source_aware_signature(event):
    """Never merge distinct RAPT runs, steps or safety states into one row."""
    assert _PREVIOUS_SIGNATURE is not None
    previous = _PREVIOUS_SIGNATURE(event)
    identity = {name: event.get(name) for name in IDENTITY_FIELDS}
    return previous + "|rapt_context=" + json.dumps(identity, sort_keys=True, default=str)


def install_rapt_audit_context() -> None:
    """Extend tuple contracts, leaving all legacy keys and event handlers in place."""
    global _INSTALLED, _PREVIOUS_SIGNATURE
    if _INSTALLED:
        return
    audit.RUNTIME_FIELDS += tuple(
        field for field in EXTRA_RUNTIME_FIELDS if field not in audit.RUNTIME_FIELDS
    )
    audit.BREWZILLA_RESULT_FIELDS += tuple(
        field for field in EXTRA_RESULT_FIELDS if field not in audit.BREWZILLA_RESULT_FIELDS
    )
    _PREVIOUS_SIGNATURE = audit._event_signature
    audit._event_signature = _source_aware_signature
    _INSTALLED = True
