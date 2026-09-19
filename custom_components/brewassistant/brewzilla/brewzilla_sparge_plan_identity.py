"""Bind every RAPT Sparge supervised plan to the verified profile occurrence.

A different RAPT session can have the same stage, target and action list. The
standard plan digest does not include the RAPT session/step identity, so a
previously confirmed plan must never match a new occurrence by coincidence.
"""

from __future__ import annotations

import hashlib

from . import brewzilla_supervised_runtime_guard as supervised

_INSTALLED = False
_PREVIOUS_PLAN_ID = None


def _plan_id(snapshot, actions):
    assert _PREVIOUS_PLAN_ID is not None
    plan_id = _PREVIOUS_PLAN_ID(snapshot, actions)
    if not snapshot.get("rapt_sparge_active"):
        return plan_id
    session = str(snapshot.get("rapt_sparge_session_id") or "").strip()
    step_id = str(snapshot.get("rapt_sparge_step_id") or "").strip()
    step_number = snapshot.get("rapt_sparge_step_number")
    if not session or (not step_id and step_number is None):
        # Missing identity must not accidentally match an earlier authorized plan.
        return f"{plan_id}:invalid-sparge-identity"
    fingerprint = hashlib.sha256(
        f"{session}\x00{step_id}\x00{step_number}".encode("utf-8")
    ).hexdigest()[:20]
    return f"{plan_id}:rapt-{fingerprint}"


def install_sparge_plan_identity():
    global _INSTALLED, _PREVIOUS_PLAN_ID
    if _INSTALLED:
        return
    _PREVIOUS_PLAN_ID = supervised._plan_id
    supervised._plan_id = _plan_id
    _INSTALLED = True
