"""Pure source-authority decision for BrewZilla hot-side writes.

Legacy internal mode names are retained for guard compatibility. write_scope is
the authoritative description of what BA may do in each Brewday mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RAPT_SOURCE = "RAPT BrewZilla Profile"
BREWFATHER_SOURCE = "Brewfather Brew Tracker"
MANUAL_SOURCE = "Manual Brewday"

AuthorityMode = Literal["rapt_controller", "brewfather_observer", "manual_legacy_unresolved", "blocked"]
WriteScope = Literal["rcl_assist", "full", "manual_legacy", "none"]


@dataclass(frozen=True)
class HotSideAuthority:
    mode: AuthorityMode
    may_write_brewzilla: bool | None
    reason: str
    write_scope: WriteScope = "none"


def resolve_hot_side_authority(
    source: str | None, *,
    rapt_contract_valid: bool = False,
    rapt_profile_active: bool = False,
    rapt_session_id: str | None = None,
    telemetry_fresh: bool = False,
    operator_abort: bool = False,
) -> HotSideAuthority:
    if operator_abort:
        return HotSideAuthority("blocked", False, "operator_abort", "none")
    normalized = (source or "").strip().lower()
    if normalized == BREWFATHER_SOURCE.lower():
        return HotSideAuthority("brewfather_observer", True, "brewfather_brewing_authority_verified", "full")
    if normalized == RAPT_SOURCE.lower():
        if not rapt_contract_valid:
            return HotSideAuthority("blocked", False, "rapt_contract_not_verified", "none")
        if not rapt_profile_active:
            return HotSideAuthority("blocked", False, "rapt_profile_not_active", "none")
        if not (rapt_session_id or "").strip():
            return HotSideAuthority("blocked", False, "rapt_session_missing", "none")
        if not telemetry_fresh:
            return HotSideAuthority("blocked", False, "rapt_telemetry_not_fresh", "none")
        return HotSideAuthority("rapt_controller", True, "rcl_brewing_assist_authority_verified", "rcl_assist")
    if normalized == MANUAL_SOURCE.lower():
        return HotSideAuthority("manual_legacy_unresolved", None, "manual_existing_policy", "manual_legacy")
    return HotSideAuthority("blocked", False, "unknown_or_unselected_brewing_source", "none")
