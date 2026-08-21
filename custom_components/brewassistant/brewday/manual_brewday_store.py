"""Manual Brewday session helper with Brewfather ownership guard."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..const import DOMAIN
from .brewday_runtime_core import BF_STATUS, BREWDAY_ACTIVE_STATUS, state as runtime_state
from .manual_brewday_runtime import ManualRuntimeSession, ManualRuntimeState

KEY = "manual_brewday_session"

_ACTIVE_MANUAL_STATES = {
    ManualRuntimeState.PREPARED,
    ManualRuntimeState.RUNNING,
    ManualRuntimeState.AWAITING_CONFIRM,
}


def brewfather_brew_tracker_active(hass: HomeAssistant) -> bool:
    """Return true only while Brewfather Brew Tracker is explicitly active."""
    return runtime_state(hass, BF_STATUS, "").strip().lower() == BREWDAY_ACTIVE_STATUS


def _ownership_error() -> HomeAssistantError:
    return HomeAssistantError(
        "Manual Brewday is blocked while Brewfather Brew Tracker is active. "
        "Stop/finish the active Brewfather Brew Tracker session before taking "
        "manual control."
    )


class GuardedManualRuntimeSession(ManualRuntimeSession):
    """Manual session that refuses positive control while Brewfather is active."""

    def __init__(self, hass: HomeAssistant) -> None:
        object.__setattr__(self, "_hass", hass)
        object.__setattr__(self, "_guard_enabled", False)
        super().__init__()
        object.__setattr__(self, "_guard_enabled", True)

    def bind_hass(self, hass: HomeAssistant) -> None:
        """Refresh the Home Assistant reference after integration reload."""
        object.__setattr__(self, "_hass", hass)

    def _assert_brewfather_inactive(self) -> None:
        if brewfather_brew_tracker_active(self._hass):
            raise _ownership_error()

    def __setattr__(self, name: str, value) -> None:
        """Catch direct stage jumps that bypass the normal session methods."""
        guard_enabled = bool(getattr(self, "_guard_enabled", False))
        if guard_enabled and brewfather_brew_tracker_active(self._hass):
            if name == "state" and value in _ACTIVE_MANUAL_STATES:
                raise _ownership_error()
            if name in {"active_stage_index", "active_step_index"}:
                current_state = getattr(self, "state", ManualRuntimeState.IDLE)
                if not (current_state == ManualRuntimeState.IDLE and value == 0):
                    raise _ownership_error()
            if name == "step_started_at" and value is not None:
                raise _ownership_error()
        super().__setattr__(name, value)

    def prepare(self) -> None:
        self._assert_brewfather_inactive()
        super().prepare()

    def start(self, now=None) -> None:
        self._assert_brewfather_inactive()
        super().start(now)

    def next(self, now=None) -> None:
        self._assert_brewfather_inactive()
        super().next(now)


def _upgrade_session(
    hass: HomeAssistant,
    session: ManualRuntimeSession | None,
) -> GuardedManualRuntimeSession:
    """Upgrade an existing in-memory session without losing its current state."""
    if isinstance(session, GuardedManualRuntimeSession):
        session.bind_hass(hass)
        return session

    guarded = GuardedManualRuntimeSession(hass)
    if isinstance(session, ManualRuntimeSession):
        object.__setattr__(guarded, "_guard_enabled", False)
        guarded.__dict__.update(session.__dict__)
        object.__setattr__(guarded, "_hass", hass)
        object.__setattr__(guarded, "_guard_enabled", True)
    return guarded


def get_manual_brewday_session(hass: HomeAssistant) -> ManualRuntimeSession:
    """Return the persistent guarded Manual Brewday session."""
    data = hass.data.setdefault(DOMAIN, {})
    session = _upgrade_session(hass, data.get(KEY))
    data[KEY] = session
    return session


def pause_manual_brewday_for_brewfather(hass: HomeAssistant) -> bool:
    """Pause a running Manual Brewday when Brewfather takes runtime ownership."""
    if not brewfather_brew_tracker_active(hass):
        return False

    session = get_manual_brewday_session(hass)
    if session.state not in {
        ManualRuntimeState.RUNNING,
        ManualRuntimeState.AWAITING_CONFIRM,
    }:
        return False

    session.pause()
    return True


def new_manual_brewday_session(hass: HomeAssistant) -> ManualRuntimeSession:
    """Replace and return the guarded Manual Brewday session."""
    session = GuardedManualRuntimeSession(hass)
    hass.data.setdefault(DOMAIN, {})[KEY] = session
    return session
