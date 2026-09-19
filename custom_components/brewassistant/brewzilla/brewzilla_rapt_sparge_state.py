"""Pure, fail-closed Sparge operator interlock.

This module does not control hardware. The orchestration adapter must enforce
its desired outputs AND validate live source/readback before any BA command.
Never infer a lifted malt pipe from time, temperature, or a RAPT step change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Phase = Literal["inactive", "awaiting_lift", "heat_to_boil"]
SPARGE_NAMES = frozenset({"sparge", "lakning"})


@dataclass(frozen=True)
class SpargeState:
    phase: Phase = "inactive"
    session_id: str | None = None
    step_id: str | None = None
    step_number: int | None = None
    lift_confirmed: bool = False
    reason: str = "inactive"


def _id(value: object) -> str | None:
    raw = str(value or "").strip()
    return raw or None


def _step_number(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def is_sparge_step(name: object) -> bool:
    """Match the exact physical stage, never a next-step preview or substring."""
    return str(name or "").strip().casefold() in SPARGE_NAMES


def observe(
    previous: SpargeState,
    *,
    source: str | None,
    profile_active: bool,
    contract_valid: bool,
    telemetry_fresh: bool,
    session_id: object,
    step_id: object,
    step_number: object,
    raw_step_name: object,
    operator_abort: bool = False,
) -> SpargeState:
    """Invalidate authorization on *any* source/session/step/health change.

    An uncertain observation is never a valid entry into Sparge. After losing
    telemetry, a new observation returns to awaiting_lift, not heat_to_boil.
    """
    if operator_abort:
        return SpargeState(reason="operator_abort")
    if source != "RAPT BrewZilla Profile":
        return SpargeState(reason="not_rapt_brewing_source")
    if not profile_active or not contract_valid or not telemetry_fresh:
        return SpargeState(reason="unverified_rapt_profile")
    if not is_sparge_step(raw_step_name):
        return SpargeState(reason="not_sparge_step")
    session = _id(session_id)
    step = _id(step_id)
    number = _step_number(step_number)
    if session is None or (step is None and number is None):
        return SpargeState(reason="missing_session_or_step_identity")
    if (
        previous.phase in {"awaiting_lift", "heat_to_boil"}
        and previous.session_id == session
        and previous.step_id == step
        and previous.step_number == number
    ):
        return previous
    return SpargeState(
        phase="awaiting_lift", session_id=session,
        step_id=step, step_number=number,
        reason="new_sparge_step_requires_lift_confirmation",
    )


def confirm_lift(
    current: SpargeState,
    *,
    heater_off: bool | None,
    pump_off: bool | None,
    heat_utilization: float | None,
    pump_utilization: float | None,
    output_telemetry_fresh: bool,
    kettle_has_sufficient_wort: bool,
    malt_pipe_safely_lifted: bool,
) -> SpargeState:
    """Consume one explicit operator confirmation on this exact observation.

    Unknown switch/number states are not OFF. Operator acknowledgement is
    required independently of safe-down readback; neither implies the other.
    """
    if current.phase != "awaiting_lift":
        return current
    if not (kettle_has_sufficient_wort and malt_pipe_safely_lifted):
        return current
    if not output_telemetry_fresh or heater_off is not True or pump_off is not True:
        return current
    if heat_utilization is None or pump_utilization is None:
        return current
    if not (0 <= heat_utilization <= 0.1 and 0 <= pump_utilization <= 0.1):
        return current
    return SpargeState(
        phase="heat_to_boil",
        session_id=current.session_id,
        step_id=current.step_id,
        step_number=current.step_number,
        lift_confirmed=True,
        reason="operator_confirmed_lift_and_wort_coverage",
    )
