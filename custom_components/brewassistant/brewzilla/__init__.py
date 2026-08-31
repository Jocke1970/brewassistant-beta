"""BrewAssistant BrewZilla package."""

from typing import Any

from homeassistant.core import State
from homeassistant.util import dt as dt_util

from . import brewzilla_orchestration as _orchestration
from . import brewzilla_learning as _learning
from . import brewzilla_temperature_roles as _temp_roles
from . import brewzilla_mash_ramp_strategy as _mash_ramp
from . import brewzilla_advice_control as _advice_control
from . import brewzilla_mash_priority_thermal_mix_guard as _mash_priority_thermal_mix_guard
from . import brewzilla_mash_wort_delta_pump_guard as _mash_wort_delta_pump_guard
from . import brewzilla_clean_heat_strike_guard as _clean_heat_strike_guard
from . import brewzilla_equipment_learning_patch as _equipment_learning_patch
from . import brewzilla_heat_strike_profile as _heat_strike_profile
from . import brewzilla_heat_strike_transition_guard as _heat_strike_transition_guard
from . import brewzilla_rcl_value_recovery_guard as _rcl_value_recovery_guard
from . import brewzilla_active_rcl_recovery_guard as _active_rcl_recovery_guard
from . import brewzilla_pre_mash_in_strike_sensor_guard as _pre_mash_in_strike_sensor
from . import brewzilla_advice_notification_gate as _advice_notification_gate
from . import brewzilla_mash_in_gate as _mash_in_gate
from . import brewzilla_hot_side_contract as _hot_side_contract
from . import brewzilla_manual_brew_control as _manual_brew_control
from . import brewzilla_supervised_runtime_guard as _supervised_runtime_guard
from . import brewzilla_supervised_readback_grace as _supervised_readback_grace
from . import brewzilla_phase_authority as _phase_authority
from . import brewzilla_paused_guard as _paused_guard
from . import brewzilla_paused_heatstrike_guard as _paused_heatstrike_guard
from . import brewzilla_execution_guard as _gate
from . import brewzilla_target_trust_guard as _target_trust_guard
from . import brewzilla_local_control_lease_v2 as _local_control_lease
from . import brewzilla_stale_heat_guard as _stale_heat_guard
from . import brewzilla_no_positive_gate as _no_positive_gate
from . import brewzilla_local_regulation_heat_guard as _local_regulation_heat_guard
from . import brewzilla_mash_in_complete_safe_down_guard as _mash_in_complete_safe_down_guard
from . import brewzilla_abort_lockout_final_guard as _abort_lockout_final_guard
from . import brewzilla_fail_passive_guard as _fail_passive_guard
from .brewzilla_temp_filter import install_temp_filter as _install_temp


def _fresh_entity_age_seconds(entity_state: State | None) -> int | None:
    if entity_state is None:
        return None
    # Use last_updated rather than last_reported. RCL may report/refresh an old
    # value without changing the actual temperature, target or utilization. For
    # BrewZilla control freshness we need value freshness, not only report traffic.
    timestamp: Any = entity_state.last_updated
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(timestamp)).total_seconds()))


_orchestration._entity_age_seconds = _fresh_entity_age_seconds
_learning._age_seconds = _fresh_entity_age_seconds

# sensor.brewzilla_power is not a verified BrewZilla entity in this installation
# and must never participate in control freshness/RCL recovery. The canonical BA
# power entity now intentionally resolves unavailable until a real BrewZilla
# power source is configured.
_orchestration.BREWZILLA_POWER_SENSOR = "sensor.brewassistant_brewzilla_power"
_orchestration.LOCAL_LIVE_ENTITY_IDS = ()
_orchestration.RAPT_BREWZILLA_DYNAMIC_ENTITY_IDS = (
    _orchestration.RAPT_CONTROL_ENTITY_IDS + _orchestration.RAPT_CONFIG_ENTITY_IDS
)
_orchestration.RAPT_BREWZILLA_ENTITY_IDS = (
    _orchestration.RAPT_BREWZILLA_DYNAMIC_ENTITY_IDS
    + _orchestration.RAPT_BREWZILLA_STATIC_ENTITY_IDS
)

_temp_roles.install_temperature_roles_patch()
_mash_ramp.install_mash_ramp_strategy()
_install_temp()

# Legacy Heatstrike profile is retained only for phase/strike-target latching
# and RCL transition context. Physical target/heat/pump regulation is owned by
# Clean Heatstrike below. The older target-clamp, ready-hold, pump-mix and
# near-target-safety wrappers are intentionally no longer installed.
_heat_strike_profile.install_heat_strike_profile()
_heat_strike_transition_guard.install_heat_strike_transition_guard()
_rcl_value_recovery_guard.install_rcl_value_recovery_guard()
_pre_mash_in_strike_sensor.install_pre_mash_in_strike_sensor_guard()
_equipment_learning_patch.install_equipment_learning_patch()
_advice_control.install_advice_control()
_mash_wort_delta_pump_guard.install_mash_wort_delta_pump_guard()
_mash_priority_thermal_mix_guard.install_mash_priority_thermal_mix_guard()
_clean_heat_strike_guard.install_clean_heat_strike_guard()
_advice_notification_gate.install_advice_notification_gate()
_mash_in_gate.install_mash_in_gate()

# The older freshness/stale-safe pair deliberately is not installed. Those
# layers translated ordinary stale cloud data into heater/pump OFF. BrewZilla
# already regulates locally against its last applied target, so normal data loss
# must be fail-passive instead of an automatic safe-down.
_paused_guard.install_paused_guard()
_paused_heatstrike_guard.install_paused_heatstrike_guard()
_gate.install_execution_guard()
_target_trust_guard.install_target_trust_guard()
_local_control_lease.install_local_control_lease()
_stale_heat_guard.install_stale_heat_guard()
_no_positive_gate.install_no_positive_gate()
_local_regulation_heat_guard.install_local_regulation_heat_guard()

# Keep the narrow Brewfather paused->running auto-complete bridge. Its older
# target-safe-down helpers are harmless once Mash-In Started has already made
# the authoritative 71.8 -> mash-target downshift.
_mash_in_complete_safe_down_guard.install_mash_in_complete_safe_down_guard()

# Consolidated boundary installed after the lower safety/apply chain: canonical
# process/safety roles, pure READY gate, atomic Mash-In Started transition and
# one-way STARTED -> COMPLETE semantics.
_hot_side_contract.install_hot_side_contract()

_active_rcl_recovery_guard.install_active_rcl_recovery_guard()
_abort_lockout_final_guard.install_abort_lockout_final_guard()
_manual_brew_control.install_manual_brew_control_guard()
# Generic Supervised Apply remains authoritative for new positive control
# authority outside the dedicated pre-mash-in physical controller.
_supervised_runtime_guard.install_supervised_runtime_guard()
# Stale confirmed readback grace belongs to generic supervised plans.
_supervised_readback_grace.install_supervised_readback_grace()
# Brewfather Play authorizes the physical Heatstrike/Mash-In phase, so that
# controller may modulate heat/pump without per-write confirmations while all
# lower ABORT/safety guards remain intact.
_phase_authority.install_phase_authority()

# Install absolutely last: ordinary RCL/process telemetry loss stops BA writes
# and leaves BrewZilla's last local target/output state untouched. ABORT and
# explicit hard-safety paths are exempt and remain authoritative.
_fail_passive_guard.install_fail_passive_guard()
