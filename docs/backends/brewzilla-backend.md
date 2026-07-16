# BrewZilla Backend

Status: active development / supervised hot-side testing  
Last synced: 2026-07-16

This document explains the backend responsibilities for BrewAssistant's BrewZilla/RAPT hot-side control path.

For detailed heat/pump tuning values, see [`../brewzilla-control-profile.md`](../brewzilla-control-profile.md). For persistent equipment learning, see [`../brewzilla-equipment-learning.md`](../brewzilla-equipment-learning.md).

## Purpose

The BrewZilla backend connects normalized Brewday Runtime intent to BrewZilla/RAPT hardware control.

It is responsible for:

```text
- reading normalized Brewday Runtime target/stage/step state
- reading BrewZilla temperature, target, heater, pump and utilization state
- reading mash/wort temperature sources
- deciding whether BA should observe, suggest, block, refresh or apply
- applying safe direct-control actions when allowed
- preserving BrewZilla local regulation after BA has given BZ a valid target
- recording enough event-log data to debug the decision afterwards
- collecting equipment-learning evidence for later profile suggestions
```

It is not intended to be unattended autopilot. Hot-side actions remain supervised.

## Main control path

The current high-level path is:

```text
Brewday Runtime resolver
  -> BrewZilla orchestration snapshot
  -> Brewday Advice control profile
  -> mash-in / heat-strike / thermal-mix guard layers
  -> freshness / RCL / target-trust / local-regulation guards
  -> async_apply_brewzilla_target_if_allowed
  -> Brewday Event Log
  -> Equipment Learning evidence model
```

## Important backend files

| File | Responsibility |
| --- | --- |
| `brewzilla_orchestration.py` | Core orchestration snapshot and direct apply path for target, heat utilization, pump utilization, heater and pump. |
| `brewzilla_advice_control.py` | Brewday Advice profile bridge. Converts stage/delta/rate/mash-wort state into desired heat and pump utilization. |
| `brewzilla_temperature.py` | Mash/wort/control temperature resolver and source selection. |
| `brewzilla_mash_in_gate.py` | Two-step operator gate: Mash-In Started releases strike target; Mash-In Complete starts circulation. |
| `brewzilla_mash_in_target_patch.py` | Resolves Mash-In Started target from active Brewday Runtime/Brewfather mash target instead of latched strike target. |
| `brewzilla_mash_in_started_guard.py` | Narrow apply bridge for Mash-In Started anti-drop heat and target release while pump remains OFF. |
| `brewzilla_mash_in_complete_safe_down_guard.py` | Ensures target safely drops to active mash target and starts circulation after Mash-In Complete. |
| `brewzilla_heat_strike_profile.py` | Pre-mash-in heat-strike profile and strike target latch. |
| `brewzilla_heat_strike_transition_guard.py` | Brakes heat-strike -> mash-control handoff and requests RCL refresh around transitions. |
| `brewzilla_rcl_value_recovery_guard.py` | Detects stale RCL values, requests update/reload recovery and exposes diagnostics. |
| `brewzilla_local_regulation_heat_guard.py` | Prevents stale/degraded guards from killing heat when BrewZilla has a valid active target. |
| `brewzilla_mash_priority_thermal_mix_guard.py` | Keeps mash/BLE as primary real-mash ramp/hold control signal while using wort/internal as limiter. |
| `brewzilla_paused_guard.py` | Safe-down and limited paused mash-hold maintenance while Brewfather reports paused. |
| `brewzilla_local_control_lease_v2.py` | Short passive observation lease after target changes, with early break on Advice risk. |
| `brewzilla_freshness_guard.py` | RAPT/BrewZilla telemetry freshness diagnostics and guard state. |
| `brewzilla_no_positive_gate.py` | Blocks positive control when runtime is not in a trusted active state. |
| `brewzilla_execution_guard.py` | Detects execution desync or unsafe execution state. |
| `brewzilla_target_trust_guard.py` | Prevents unsafe or stale target rewinds. |
| `brewzilla_learning.py` | Live Brewday Advice analysis snapshot and recommendation context. |
| `brewzilla_equipment_learning.py` | Persistent equipment-specific model and profile-suggestion evidence. |
| `brewzilla_equipment_learning_patch.py` | Bridges live learning snapshots into the persistent equipment-learning model. |

## Read-only vs direct action

BrewZilla control is intentionally guarded.

Typical modes seen in event logs:

```text
monitor        -> BA is observing; no action required
local-control  -> short passive lease after target application
direct-control -> BA has an allowed action to apply
blocked        -> higher guard blocks positive control
```

## Local BrewZilla regulation preservation

The backend must respect this rule:

```text
Once BA has given BrewZilla a valid active target,
BrewZilla controls the heater locally against that target.
```

Therefore RCL freshness problems should not silently produce:

```yaml
actions:
  - set_heat_utilization:0
  - heater_off
```

unless an explicit abort/completed/emergency/safe-down context exists.

Expected preservation diagnostics may include:

```yaml
local_regulation_heat_guard_active: true
local_regulation_heat_guard_reason: valid_brewzilla_target_preserves_local_regulation
```

## RCL freshness and value recovery

The backend tracks telemetry freshness and value freshness. RCL can sometimes report an entity as refreshed without the temperature value changing.

Expected recovery behavior:

```text
RCL value stale during active hot-side control
  -> request homeassistant.update_entity for RCL/BrewZilla entities
  -> optionally request guarded config-entry reload
  -> mark diagnostics in event logs
  -> do not kill local BZ heat if BZ already has a valid target
```

Useful diagnostics:

```yaml
rcl_value_stale_guard_active: true
rcl_value_stale_guard_temperature: ...
rcl_value_stale_guard_stale_seconds: ...
rcl_value_stale_guard_refresh_requested: true
rcl_value_stale_guard_reload_requested: true
```

## Two-step mash-in gate

Mash-in is split into two explicit operator actions.

### 1. Mash-In Started

Visible only while the mash-in gate is ready:

```yaml
mash_in_gate_state: ready_for_mash_in
mash_in_started_visible: true
mash_in_complete_visible: false
```

When pressed, BA:

```text
- records event_type: mash_in_started
- reads the active Brewday Runtime/Brewfather mash target
- releases the latched strike target toward that real mash target
- keeps pump OFF / pump utilization 0
- allows only low anti-drop heat while BrewZilla regulates locally
```

For a realistic 69/66 mash-in:

```yaml
mash_in_gate_state: mash_in_started
mash_in_started_hold_active: true
mash_in_effective_target: 66.0
mash_in_started_set_target: 66.0
mash_in_started_set_pump_utilization: 0.0
```

### 2. Mash-In Complete

Visible only after Mash-In Started.

When pressed, BA starts circulation and holds/drops to the active mash target:

```yaml
apply_result: mash_circulation_started_safe_down_applied
actions:
  - mash_in_complete
  - set_pump_utilization:50.0
  - pump_on
  - mash_in_complete_safe_down_set_target:66.0
mash_in_gate_state: mash_in_complete
```

## Mash circulation floor

After mash-in is complete, BA applies an explicit circulation floor during ramp and mash-hold stages:

```text
pump_on = true
pump_utilization >= 40 %
```

Normal real-mash ramp/hold profile asks for 50%. The 40% floor only prevents circulation from falling too low if another modifier would otherwise lower it.

## Thermal mix and mash-priority ramping

Thermal mix is the stratification guard.

It is active when BA sees separate mash and wort/internal values and either:

```text
- wort/internal is above target while mash still lags behind, or
- wort/internal is near target while mash is still significantly behind
```

Current real-mash rule:

```text
mash/BLE temperature is primary for ramp and mash hold
wort/internal temperature is a limiter, not the main control target
```

During real mash, when mash is still at least 2°C below target and wort/internal is not extremely hot, the mash-priority thermal-mix guard raises the cap floor:

```text
ramp:      at least 45 % heat cap
mash hold: at least 30 % heat cap
pump:      thermal-mix pump profile, usually 70 %
```

This prevents cases where mash is far below target but the profile collapses to 5% just because wort/internal is moderately above target.

Expected diagnostics:

```yaml
advice_thermal_mix_active: true
advice_heat_profile_phase: thermal_mix_heat_cap
advice_mash_priority_thermal_mix_active: true
advice_mash_priority_thermal_mix_floor: 45.0
```

## Paused mash-hold maintenance

Brewfather can report a mash hold as paused even though the brewer still expects the target to be maintained.

The paused guard allows a narrow positive-control exception for mash hold maintenance when:

```text
- runtime_state is paused
- target is already synced
- stage is mash_hold
- no abort/RCL/execution/mash-in gate block is active
- requested heat and pump values are within safe maintenance caps
```

Expected event-log marker:

```yaml
apply_result: paused_hold_maintenance_applied
```

## Equipment learning

The equipment-learning layer is not part of the immediate control decision. It observes live Brewday Advice snapshots and persists equipment-specific evidence.

It records observations during active `ramp`, `mash_hold` and `boil` stages, buckets them by equipment/context/volume/grain/stage, and creates candidate profile suggestions.

It does not auto-write profile values.

Expected sensors:

```text
sensor.brewassistant_brewzilla_equipment_learning_summary
sensor.brewassistant_brewzilla_equipment_learning_observations
sensor.brewassistant_brewzilla_equipment_learning_segments
sensor.brewassistant_brewzilla_equipment_learning_profile_key
sensor.brewassistant_brewzilla_equipment_learning_suggestion
```

See [`../brewzilla-equipment-learning.md`](../brewzilla-equipment-learning.md).

## Safe-down behavior

The ABORT path and completed runtime guards must always win over Advice and learning.

Expected abort/safe state:

```text
heater off
pump off
heat utilization 0
pump utilization 0
abort lockout active
```

No backend should re-enable heat or pump during abort lockout.

## Test recipe recommendation

For BrewAssistant/BrewZilla tests:

```text
Ramp between targets: 5 min
Hold time: unchanged
Strike / mash-in target: based on recipe and grain temperature
Mash target after grain: active first mash hold, for example 66°C
```

Two-minute ramps are useful stress tests, but they can cause Brewfather target transitions before the mash/wort temperatures and cloud telemetry have stabilized.

## What to verify in next event log

```yaml
mash_in_gate_state: ready_for_mash_in
mash_in_started_visible: true
event_type: mash_in_started
mash_in_started_hold_active: true
mash_in_started_set_target: 66.0
apply_result: mash_in_started_hold_applied
event_type: mash_in_confirmed
apply_result: mash_circulation_started_safe_down_applied
advice_mash_circulation_floor_active: true
advice_thermal_mix_active: true
advice_mash_priority_thermal_mix_active: true
rcl_value_stale_guard_refresh_requested: true   # only if RCL stalls
local_regulation_heat_guard_active: true        # only if another guard tries to kill heat despite valid target
brewzilla_equipment_learning_observations: ...
brewzilla_equipment_learning_suggestion: ...
```
