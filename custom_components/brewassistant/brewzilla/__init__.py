"""BrewAssistant BrewZilla package."""

from typing import Any

from homeassistant.core import State
from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as _orchestration
from . import brewzilla_learning as _learning
from . import brewzilla_temperature_roles as _temp_roles
from . import brewzilla_mash_ramp_strategy as _mash_ramp
from . import brewzilla_advice_control as _advice_control
from . import brewzilla_heat_strike_profile as _heat_strike_profile
from . import brewzilla_pre_mash_in_strike_sensor_guard as _pre_mash_in_strike_sensor
from . import brewzilla_strike_ready_hold_guard as _strike_ready_hold_guard
from . import brewzilla_advice_notification_gate as _advice_notification_gate
from . import brewzilla_mash_in_gate as _mash_in_gate
from . import brewzilla_freshness_guard as _freshness_guard
from . import brewzilla_stale_safe_guard as _runtime_safety
from . import brewzilla_paused_guard as _paused_guard
from . import brewzilla_paused_heatstrike_guard as _paused_heatstrike_guard
from . import brewzilla_execution_guard as _gate
from . import brewzilla_target_trust_guard as _target_trust_guard
from . import brewzilla_local_control_lease_v2 as _local_control_lease
from . import brewzilla_stale_heat_guard as _stale_heat_guard
from . import brewzilla_no_positive_gate as _no_positive_gate
from . import brewzilla_mash_in_started_guard as _mash_in_started_guard
from . import brewzilla_mash_in_complete_safe_down_guard as _mash_in_complete_safe_down_guard
from .brewzilla_temp_filter import install_temp_filter as _install_temp


def _fresh_entity_age_seconds(entity_state: State | None) -> int | None:
    if entity_state is None:
        return None
    timestamp: Any = getattr(entity_state, "last_reported", None) or entity_state.last_updated
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(timestamp)).total_seconds()))


_orchestration._entity_age_seconds = _fresh_entity_age_seconds
_learning._age_seconds = _fresh_entity_age_seconds
_temp_roles.install_temperature_roles_patch()
_mash_ramp.install_mash_ramp_strategy()
_install_temp()
_heat_strike_profile.install_heat_strike_profile()
_pre_mash_in_strike_sensor.install_pre_mash_in_strike_sensor_guard()
_strike_ready_hold_guard.install_strike_ready_hold_guard()
_advice_control.install_advice_control()
_advice_notification_gate.install_advice_notification_gate()
_mash_in_gate.install_mash_in_gate()
_freshness_guard.install_freshness_guard()
_runtime_safety.install_stale_safe_guard()
_paused_guard.install_paused_guard()
_paused_heatstrike_guard.install_paused_heatstrike_guard()
_gate.install_execution_guard()
_target_trust_guard.install_target_trust_guard()
_local_control_lease.install_local_control_lease()
_stale_heat_guard.install_stale_heat_guard()
_no_positive_gate.install_no_positive_gate()
_mash_in_started_guard.install_mash_in_started_guard()
_mash_in_complete_safe_down_guard.install_mash_in_complete_safe_down_guard()
