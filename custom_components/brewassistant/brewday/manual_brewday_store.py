"""Manual Brewday session helper with external-runtime ownership guards."""

from __future__ import annotations

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event

from ..const import DOMAIN
from .brewday_runtime_core import BF_STATUS, brewfather_session_active, entity_candidates
from .manual_brewday_runtime import ManualRuntimeSession, ManualRuntimeState

KEY = "manual_brewday_session"
HANDOFF_LISTENER_KEY = "manual_brewfather_handoff_listener"
LAST_HANDOFF_SAFE_DOWN_KEY = "last_brewfather_handoff_safe_down"

_ACTIVE_MANUAL_STATES = {
    ManualRuntimeState.PREPARED,
    ManualRuntimeState.RUNNING,
    ManualRuntimeState.AWAITING_CONFIRM,
}


def brewfather_brew_tracker_active(hass: HomeAssistant) -> bool:
    """Return the same Brewfather ownership decision used by runtime source selection."""
    return brewfather_session_active(hass)


def _ownership_error() -> HomeAssistantError:
    return HomeAssistantError(
        "Manual Brewday is blocked while Brewfather Brew Tracker is active. "
        "Stop or finish the active Brewfather Brew Tracker session before taking "
        "manual control."
    )


def _rapt_ownership_error() -> HomeAssistantError:
    return HomeAssistantError(
        "Manual Brewday is blocked while a RAPT BrewZilla profile owns or retains "
        "the hot-side runtime handoff. Stop the profile and wait for a confirmed "
        "RAPT STOP before taking manual control."
    )


def _release_stopped_rapt_for_manual(hass: HomeAssistant) -> bool:
    """Release only a confirmed RAPT STOP guard for explicit Manual takeover."""
    # Import lazily so Brewday can finish initializing before importing the
    # BrewZilla package through rapt_profile_runtime.
    from .rapt_profile_runtime import clear_rapt_profile_stop_guard

    return clear_rapt_profile_stop_guard(hass, reason="manual_operator_takeover")


def _rapt_blocks_manual(hass: HomeAssistant, *, allow_stopped_takeover: bool) -> bool:
    # Keep this import out of module initialization. rapt_profile_runtime uses
    # BrewZilla owned-control helpers, whose package imports orchestration and
    # audit helpers back from Brewday.
    from .rapt_profile_runtime import rapt_profile_runtime_claims_source

    if not rapt_profile_runtime_claims_source(hass):
        return False
    if allow_stopped_takeover and _release_stopped_rapt_for_manual(hass):
        return rapt_profile_runtime_claims_source(hass)
    return True


class GuardedManualRuntimeSession(ManualRuntimeSession):
    """Manual session that refuses positive control while an external source owns it."""

    def __init__(self, hass: HomeAssistant) -> None:
        object.__setattr__(self, "_hass", hass)
        object.__setattr__(self, "_guard_enabled", False)
        super().__init__()
        object.__setattr__(self, "_guard_enabled", True)

    def bind_hass(self, hass: HomeAssistant) -> None:
        """Refresh the Home Assistant reference after integration reload."""
        object.__setattr__(self, "_hass", hass)

    def _assert_brewfather_inactive(self) -> None:
        """Preserve legacy method name while guarding every external runtime owner."""
        if _rapt_blocks_manual(self._hass, allow_stopped_takeover=True):
            raise _rapt_ownership_error()
        if brewfather_brew_tracker_active(self._hass):
            raise _ownership_error()

    def __setattr__(self, name: str, value) -> None:
        """Catch direct stage jumps that bypass the normal session methods."""
        guard_enabled = bool(getattr(self, "_guard_enabled", False))
        positive_mutation = bool(
            (name == "state" and value in _ACTIVE_MANUAL_STATES)
            or name in {"active_stage_index", "active_step_index"}
            or (name == "step_started_at" and value is not None)
        )

        if guard_enabled and positive_mutation:
            if _rapt_blocks_manual(self._hass, allow_stopped_takeover=True):
                raise _rapt_ownership_error()

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


def _ensure_brewfather_handoff_listener(hass: HomeAssistant) -> None:
    """React immediately when Brewfather gains or releases hot-side ownership."""
    data = hass.data.setdefault(DOMAIN, {})
    if HANDOFF_LISTENER_KEY in data:
        return

    async def _handle_handoff() -> None:
        # Entering Brewing: pause Manual immediately, but do not safe-down here;
        # Brewfather is now authoritative and may legitimately keep outputs on.
        if brewfather_brew_tracker_active(hass):
            pause_manual_brewday_for_brewfather(hass)
            return

        # Leaving Brewing: Manual must remain paused and physical outputs must
        # be driven safe immediately rather than waiting for the periodic
        # coordinator/orchestration tick.
        session = data.get(KEY)
        if not isinstance(session, ManualRuntimeSession):
            return
        if session.state != ManualRuntimeState.PAUSED:
            return

        from ..brewzilla.brewzilla_orchestration import async_apply_brewzilla_target_if_allowed

        result = await async_apply_brewzilla_target_if_allowed(hass)
        data[LAST_HANDOFF_SAFE_DOWN_KEY] = result

    @callback
    def _state_changed(_event: Event) -> None:
        hass.async_create_task(_handle_handoff())

    data[HANDOFF_LISTENER_KEY] = async_track_state_change_event(
        hass,
        list(entity_candidates(BF_STATUS)),
        _state_changed,
    )


def get_manual_brewday_session(hass: HomeAssistant) -> ManualRuntimeSession:
    """Return the persistent guarded Manual Brewday session."""
    data = hass.data.setdefault(DOMAIN, {})
    _ensure_brewfather_handoff_listener(hass)
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
    _ensure_brewfather_handoff_listener(hass)
    session = GuardedManualRuntimeSession(hass)
    hass.data.setdefault(DOMAIN, {})[KEY] = session
    return session
