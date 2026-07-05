# BrewZilla Backend

Status: active development / supervised hot-side testing  
Last synced: 2026-07-05

This document explains the backend responsibilities for BrewAssistant's BrewZilla/RAPT hot-side control path.

For the detailed heat/pump profile and current tuning values, see [`../brewzilla-control-profile.md`](../brewzilla-control-profile.md).

## Purpose

The BrewZilla backend connects normalized Brewday Runtime intent to BrewZilla/RAPT hardware control.

It is responsible for:

```text
- reading normalized Brewday Runtime target/stage/step state
- reading BrewZilla temperature, target, heater, pump and utilization state
- reading mash/wort temperature sources
- deciding whether BrewAssistant should observe, suggest, block or apply
- applying safe direct-control actions when allowed
- recording enough event-log data to debug the decision afterwards
```

It is not intended to be unattended autopilot. Hot-side actions must remain supervised.

## Main control path

The current high-level path is:

```text
Brewday Runtime resolver
  -> BrewZilla orchestration snapshot
  -> Brewday Advice control profile
  -> mash-in gate / safety guard layers
  -> async_apply_brewzilla_target_if_allowed
  -> Brewday Event Log
```

## Important backend files

| File | Responsibility |
| --- | --- |
| `brewzilla_orchestration.py` | Core orchestration snapshot and direct apply path for target, heat utilization, pump utilization, heater and pump. |
| `brewzilla_advice_control.py` | Brewday Advice profile bridge. Converts stage/delta/rate/mash-wort state into desired heat and pump utilization. |
| `brewzilla_temperature.py` | Mash/wort/control temperature resolver and source selection. |
| `brewzilla_mash_in_gate.py` | Two-step operator gate: Mash-In Started releases strike target; Mash-In Complete starts circulation. |
| `brewzilla_mash_in_started_guard.py` | Narrow apply bridge for Mash-In Started anti-drop heat and target release while pump remains OFF. |
| `brewzilla_paused_guard.py` | Safe-down and limited paused mash-hold maintenance while Brewfather reports paused. |
| `brewzilla_local_control_lease_v2.py` | Short passive observation lease after target changes, with early break on Advice risk. |
| `brewzilla_freshness_guard.py` | RAPT/BrewZilla telemetry freshness diagnostics and guard state. |
| `brewzilla_no_positive_gate.py` | Blocks positive control when runtime is not in a trusted active state. |
| `brewzilla_execution_guard.py` | Detects execution desync or unsafe execution state. |
| `brewzilla_target_trust_guard.py` | Prevents unsafe or stale target rewinds. |
| `brewzilla_learning.py` | Brewday Advice learning snapshot and recommendation context. |

## Read-only vs direct action

BrewZilla control is intentionally guarded.

Direct actions are only expected when runtime and safety context are trusted. Otherwise BrewAssistant should observe or safe-down.

Typical modes seen in event logs:

```text
monitor        -> BA is observing; no action required
local-control  -> short passive lease after target application
direct-control -> BA has an allowed action to apply
blocked        -> higher guard blocks positive control
```

## Positive-control gate

Brewday Advice must not apply stale target, heat or pump commands when Brewday Runtime is idle, inactive, completed, unknown or otherwise outside an active trusted control state.

Expected stale/idle behavior:

```yaml
advice_positive_control_blocked: true
advice_positive_control_blocked_reason: brewday_runtime_not_active
target_sync_needed: false
```

Only safe-down actions may be allowed in this state.

## Brewday Advice profile bridge

`brewzilla_advice_control.py` owns the current built-in profile:

```text
brewzilla_35l_small_batch_default
```

It computes:

```text
desired_heat_utilization
desired_heater_on
desired_pump_utilization
desired_pump_on
heat_utilization_action_needed
pump_utilization_action_needed
```

The profile is conservative by design. It should prefer smaller heat corrections and controlled circulation rather than chasing target aggressively.

Learning context affects pump behavior:

```text
Water only -> stronger test circulation
Real mash  -> conservative malt-pipe circulation
Unknown    -> conservative malt-pipe circulation
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
- scans Brew Tracker timeline for the next temperature-bearing mash/ramp step
- releases the strike target if that next mash target is lower
- keeps pump OFF / pump utilization 0
- allows only low anti-drop heat up to 15 %
```

For a realistic 69/66 mash-in:

```yaml
mash_in_gate_state: mash_in_started
mash_in_started_hold_active: true
mash_in_effective_target: 66.0
mash_in_complete_visible: true
actions:
  - mash_in_started_set_target:66.0
  - mash_in_started_set_heat_utilization:10.0
  - mash_in_started_set_pump_utilization:0.0
```

### 2. Mash-In Complete

Visible only after Mash-In Started:

```yaml
mash_in_gate_state: mash_in_started
mash_in_started_visible: false
mash_in_complete_visible: true
```

When pressed, BA starts circulation:

```yaml
apply_result: mash_circulation_started
actions:
  - mash_in_complete
  - set_pump_utilization:50.0
  - pump_on
mash_in_gate_state: mash_in_complete
mash_in_started_visible: false
mash_in_complete_visible: false
```

After confirmation, normal mash circulation should continue unless a higher safety guard stops it.

## Mash circulation floor

After mash-in is complete, BrewAssistant applies an explicit circulation floor during ramp and mash-hold stages:

```text
pump_on = true
pump_utilization >= 40 %
```

Normal real-mash ramp/hold profile asks for 50 %. The 40 % floor only prevents circulation from falling too low if another modifier would otherwise lower it.

Thermal mix may temporarily raise pump utilization to 70 % during real mash or 80 % during water-only tests. When thermal mix is no longer active, the pump should return to the normal ramp/hold profile or at least the floor.

Expected diagnostics:

```yaml
advice_mash_circulation_floor_active: true
advice_mash_circulation_floor_utilization: 40
advice_desired_pump_on: true
desired_pump_utilization: 50
```

## Thermal mix

Thermal mix is the stratification guard.

It is active when BrewAssistant sees separate mash and wort/internal values and either:

```text
- wort/internal is above target while mash still lags behind, or
- wort/internal is within 1.0°C below target while mash is at least 1.5°C behind
```

Expected real-mash behavior:

```text
heat utilization -> 0 % or 5 %
pump utilization -> 70 %
```

Water-only tests may still use 80 % pump utilization for thermal mix.

Expected diagnostics:

```yaml
advice_thermal_mix_active: true
advice_heat_profile_phase: thermal_mix_heat_cap
advice_thermal_mix_reason: wort_near_target_mash_lagging
advice_pump_phase: thermal_mix
```

or:

```yaml
advice_thermal_mix_reason: wort_above_target_mash_lagging
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

Example actions:

```yaml
actions:
  - paused_hold_set_heat_utilization:10.0
  - paused_hold_set_pump_utilization:50.0
```

or during real-mash thermal mix:

```yaml
actions:
  - paused_hold_set_heat_utilization:0.0
  - paused_hold_set_pump_utilization:70.0
```

## Local-control lease

The local-control lease is a short observe window after BrewAssistant changes the BrewZilla target.

Current intent:

```text
After set_target:
  observe briefly while BrewZilla reacts locally

But break early if Advice sees risk or a meaningful heat/pump profile change.
```

Expected break diagnostics:

```yaml
local_control_lease_break_reason: thermal_mix_active
```

or:

```yaml
local_control_lease_break_reason: near_target_taper_zone
```

Long stretches of local-control should be treated as suspicious during testing if heat/pump corrections are needed.

## Freshness and RAPT/Shelly telemetry

The backend tracks telemetry ages separately for RAPT/BrewZilla entities and local Shelly power data.

Important event-log fields:

```yaml
rapt_brewzilla_poll_age_seconds: ...
rapt_brewzilla_dynamic_age_seconds: ...
rapt_brewzilla_temperature_age_seconds: ...
rapt_brewzilla_power_age_seconds: ...
rapt_critical_refresh_recommended: true
rapt_brewzilla_poll_warning: false
```

A critical refresh recommendation is a diagnostic warning. It should not automatically mean a safety block unless the freshness guard says it is blocking.

## Safe-down behavior

The ABORT path and higher guards must always win over Advice.

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
Strike / mash-in target: 69°C
Mash target after grain: 66°C
```

Two-minute ramps are useful stress tests, but they can cause Brewfather target transitions before the mash/wort temperatures and cloud telemetry have stabilized.

## What to verify in next event log

```yaml
mash_in_gate_state: ready_for_mash_in
mash_in_started_visible: true
event_type: mash_in_started
mash_in_started_hold_active: true
mash_in_effective_target: 66.0
apply_result: mash_in_started_hold_applied
event_type: mash_in_confirmed
apply_result: mash_circulation_started
advice_mash_circulation_floor_active: true
advice_thermal_mix_active: true
advice_thermal_mix_reason: wort_near_target_mash_lagging
advice_positive_control_blocked: true
local_control_lease_break_reason: thermal_mix_active
local_control_lease_break_reason: near_target_taper_zone
```

Also verify that pump remains on after mash-in and does not fall below the mash circulation floor unless a safety/gate/abort guard is active.
