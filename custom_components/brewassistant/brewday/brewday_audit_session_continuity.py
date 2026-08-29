"""Keep same-brewday pre-start -> Play transitions in one flight-recorder log.

The legacy audit autostart predates the deterministic session-boundary latch. It
used the latest audit row (`idle`/no source) as a completed-session signal. With
Brewfather's ready-only Brewing pre-start state, that row is expected inside the
current brewday; when Play then makes the runtime live, the legacy heuristic can
incorrectly rotate the recorder.

Idle/no-owner rows are therefore considered terminal only when the dedicated
session-boundary guard has actually armed a durable boundary. Explicit
completed/finished rows remain terminal on their own.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import brewday_audit_autostart as autostart
from .brewday_audit import get_brewday_audit_log

DATA_KEY_BOUNDARY = "brewday_audit_session_boundary"
_INSTALLED = False


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _boundary_armed(hass: HomeAssistant) -> bool:
    boundary = hass.data.setdefault("brewassistant", {}).get(DATA_KEY_BOUNDARY)
    return bool(isinstance(boundary, dict) and boundary.get("armed"))


def _boundary_aware_last_audit_session_finished(hass: HomeAssistant) -> bool:
    """Return terminal status without treating BF pre-start idle as old brewday."""
    log = get_brewday_audit_log(hass)
    if not log.events:
        return False

    last_event = log.events[-1]
    last_state = _norm(last_event.get("runtime_state") or last_event.get("status"))
    last_source = _norm(last_event.get("source"))

    if last_state in {"completed", "finished"}:
        return True
    if last_state in {"idle", "inactive"} and last_source in {"", "none"}:
        return _boundary_armed(hass)
    return False


def install_audit_session_continuity_guard() -> None:
    """Make the legacy autostart consume the deterministic boundary latch."""
    global _INSTALLED
    if _INSTALLED:
        return
    autostart._last_audit_session_finished = _boundary_aware_last_audit_session_finished
    _INSTALLED = True
