"""Keep Heatstrike physically authoritative while Mash-In is merely ready.

Reaching strike temperature is an operator notification, not a physical phase
transition.  Until the brewer explicitly presses Mash-In Started, BrewAssistant
must keep the strike target and Heatstrike circulation/regulation active.  The
existing Mash-In Started state remains the boundary that pauses the pump and
releases strike temperature to the effective mash target.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from . import brewzilla_clean_heat_strike_guard as clean_heatstrike
from . import brewzilla_mash_in_gate as mash_in_gate
from . import brewzilla_orchestration as orchestration

_ORIGINAL_BUILD: Callable[[HomeAssistant], dict[str, Any]] | None = None
_INSTALLED = False


def _ready_hold_active(snapshot: dict[str, Any]) -> bool:
    return bool(
        str(snapshot.get("mash_in_gate_state") or "").lower() == mash_in_gate.READY_STATE
        and snapshot.get("clean_heat_strike_active")
        and not snapshot.get("abort_lockout_active")
        and not snapshot.get("completed_runtime")
    )


def _hold_heatstrike_until_mash_in_started(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Restore Heatstrike outputs that the ready gate must not pause."""
    if not _ready_hold_active(snapshot):
        snapshot.setdefault("mash_in_ready_heatstrike_hold_active", False)
        return snapshot

    # Mash-In gate runs after Clean Heatstrike and historically forced the pump
    # OFF as soon as READY was reached. Re-running the pure Heatstrike snapshot
    # regulator here restores target/heat/pump ownership without bypassing any
    # later hard safety/ABORT guards in the orchestration chain.
    out = clean_heatstrike._apply_clean_heatstrike(snapshot)
    reason = str(out.get("control_reason") or "")
    out.update(
        {
            "mash_in_gate_state": mash_in_gate.READY_STATE,
            "mash_in_gate_pending": True,
            "mash_in_gate_latched": True,
            "mash_in_started_visible": True,
            "mash_in_complete_visible": False,
            "mash_in_ready_heatstrike_hold_active": True,
            "mash_in_ready_heatstrike_release_event": "mash_in_started",
            "control_reason": (
                f"{reason} Strike temperature is ready, but Heatstrike remains physically authoritative "
                "and keeps target/circulation until the operator presses Mash-In Started."
            ).strip(),
        }
    )
    return out


async def _create_ready_notification(hass: HomeAssistant, snapshot: dict[str, Any]) -> None:
    """Notify that Mash-In may start without implying Heatstrike has stopped."""
    temperature = mash_in_gate._temperature_for_gate(snapshot)
    target = mash_in_gate._target_for_gate(snapshot)
    effective, effective_source, next_target, next_source = mash_in_gate._effective_mash_in_target(
        hass, snapshot
    )
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "notification_id": mash_in_gate.NOTIFICATION_ID,
            "title": "🍺 BrewAssistant: dags för mash-in",
            "message": (
                "Strike target är nådd. Heatstrike fortsätter hålla temperaturen och cirkulationen "
                "tills du bekräftar att inmäskningen börjar.\n\n"
                f"Mäsktemperatur: {temperature} °C  \n"
                f"Strike/current target: {target} °C  \n"
                f"Nästa/effective target: {effective} °C ({effective_source}, next={next_target}, source={next_source})\n\n"
                "Tryck **BrewAssistant Mash-In Started** när du faktiskt börjar hälla i malten. "
                "Då pausas pumpen och Mash-In-logiken tar över. När malten är inrörd och bädden är redo: "
                "tryck **BrewAssistant Mash-In Complete**."
            ),
        },
        blocking=False,
    )


def install_mash_in_ready_hold_guard() -> None:
    """Install READY-state Heatstrike hold after the Mash-In gate wrapper."""
    global _ORIGINAL_BUILD, _INSTALLED
    if _INSTALLED:
        return

    _ORIGINAL_BUILD = orchestration.build_orchestration_snapshot

    def build_orchestration_snapshot(hass: HomeAssistant) -> dict[str, Any]:
        assert _ORIGINAL_BUILD is not None
        snapshot = _ORIGINAL_BUILD(hass)
        return _hold_heatstrike_until_mash_in_started(snapshot)

    orchestration.build_orchestration_snapshot = build_orchestration_snapshot
    mash_in_gate._create_ready_notification = _create_ready_notification
    _INSTALLED = True
