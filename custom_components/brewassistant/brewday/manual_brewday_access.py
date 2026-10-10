"""Fail-closed guard for direct Manual Brewday process service calls.

Lovelace visibility is not a security boundary. This check runs synchronously
immediately before modifying a ManualRuntimeSession, including direct HA
service calls that bypass the dashboard. It never sends BrewZilla commands.
"""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError

from . import brewday_execution_mode as execution_mode
from .brewday_operator_abort import brewday_operator_abort_active
from .brewday_runtime_core import brewfather_session_active
from .rapt_profile_runtime import build_rapt_profile_runtime_snapshot


def assert_manual_brewday_mutation_allowed(hass: Any, *, action: str) -> None:
    """Reject manual mutations until *all* external ownership is resolved."""
    if brewday_operator_abort_active(hass):
        raise HomeAssistantError(f"Manual {action} nekad: ABORT-spärren är aktiv.")

    if execution_mode.resync_required(hass) or execution_mode.fallback_active(hass):
        raise HomeAssistantError(
            f"Manual {action} nekad: extern session väntar på återanslutning/kvittens."
        )

    # A previously recorded external owner is retained until an explicit
    # verified end/ACK. Unavailable is NOT a verified STOP.
    previous = execution_mode.last_external_mode(hass)
    if previous is not None and execution_mode.has_external_snapshot(hass, previous):
        raise HomeAssistantError(
            f"Manual {action} nekad: tidigare extern ägare har inte frigjorts."
        )

    # Covers active RCL, source loss after active, and verified STOP handoff
    # guard (until it has been explicitly released).
    if build_rapt_profile_runtime_snapshot(hass) is not None:
        raise HomeAssistantError(
            f"Manual {action} nekad: RAPT/RCL äger fortfarande överlämningen."
        )

    if brewfather_session_active(hass):
        raise HomeAssistantError(
            f"Manual {action} nekad: Brewfather-sessionen är fortfarande aktiv."
        )
