"""Pure source authority decision for the planned BrewZilla writer boundary.

IMPORTANT: This module is a *contract*, not an installed actuator interlock.
The existing BrewZilla write paths are NOT routed through it yet. Do not use
this file or its tests as evidence that BF is passive in an installed release.
Fermentation authorization belongs to the separate cold-side controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RAPT_SOURCE = "RAPT BrewZilla Profile"
BREWFATHER_SOURCE = "Brewfather Brew Tracker"
MANUAL_SOURCE = "Manual Brewday"

AuthorityMode = Literal[
    "rapt_controller",
    "brewfather_observer",
    "manual_legacy_unresolved",
    "blocked",
]


@dataclass(frozen=True)
class HotSideAuthority:
    """Desired authority only; physical outputs may retain old values."""

    mode: AuthorityMode
    # None means existing Manual behavior remains undecided by this contract.
    may_write_brewzilla: bool | None
    reason: str


def resolve_hot_side_authority(
    source: str | None,
    *,
    rapt_contract_valid: bool = False,
    rapt_profile_active: bool = False,
    rapt_session_id: str | None = None,
    telemetry_fresh: bool = False,
    operator_abort: bool = False,
) -> HotSideAuthority:
    """Classify *brewing* source, with an explicit fail-closed RAPT contract.

    This intentionally ignores recipe metadata and fermentation status.
    It does not issue OFF commands; ``may_write_brewzilla=False`` means do not
    authorize new BA writes, NOT that the hardware has been turned off.
    """
    if operator_abort:
        return HotSideAuthority("blocked", False, "operator_abort")

    normalized = (source or "").strip().lower()
    if normalized == BREWFATHER_SOURCE.lower():
        return HotSideAuthority("brewfather_observer", False, "brewfather_hot_side_passive")

    if normalized == RAPT_SOURCE.lower():
        if not rapt_contract_valid:
            return HotSideAuthority("blocked", False, "rapt_contract_not_verified")
        if not rapt_profile_active:
            return HotSideAuthority("blocked", False, "rapt_profile_not_active")
        if not (rapt_session_id or "").strip():
            return HotSideAuthority("blocked", False, "rapt_session_missing")
        if not telemetry_fresh:
            return HotSideAuthority("blocked", False, "rapt_telemetry_not_fresh")
        return HotSideAuthority("rapt_controller", True, "rapt_brewing_authority_verified")

    if normalized == MANUAL_SOURCE.lower():
        # A separate design/review is required; don't silently change Manual.
        return HotSideAuthority("manual_legacy_unresolved", None, "manual_requires_separate_policy")

    return HotSideAuthority("blocked", False, "unknown_or_unselected_brewing_source")
