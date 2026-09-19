# BrewZilla backend

Status: active supervised hot-side development  
Code snapshot documented: 2026-09-06

`brewzilla` is BrewAssistant's BrewZilla/RAPT hot-side hardware adapter. It consumes normalized Brewday intent, resolves physical temperature roles, computes target/heat/pump behavior, applies ownership and safety guards, and performs permitted writes to BrewZilla/RAPT entities.

The package is intentionally implemented as an ordered wrapper/guard chain. Installation order in `__init__.py` is part of the control architecture.

## Responsibilities

- read BrewZilla/RAPT target, temperature, connection, heater, pump and utilization state;
- resolve process/mash and kettle/wort temperature roles;
- convert trusted Brewday Runtime intent into physical hot-side plans;
- regulate Heatstrike and Mash-In using the dedicated physical controller;
- handle READY -> STARTED -> COMPLETE as an explicit physical handoff;
- preserve valid local BrewZilla regulation when cloud/process telemetry is genuinely degraded;
- distinguish RCL report freshness from unchanged-value age;
- request active RCL coordinator refreshes during owned hot-side phases;
- enforce Manual Brew channel ownership;
- use generic Supervised Apply where positive authority is not covered by a dedicated phase;
- execute authoritative ABORT/safe-down and lockout behavior;
- expose learning/energy/orchestration diagnostics to sensors and Flight Recorder.

## Physical entity surface

Core orchestration uses the BrewZilla/RAPT control surface:

```text
number.brewzilla_target_temperature
sensor.brewzilla_temperature
sensor.brewzilla_connection
switch.brewzilla
switch.brewzilla_heater
switch.brewzilla_pump
number.brewzilla_heat_utilization
number.brewzilla_pump_utilization
```

BrewAssistant's canonical power sensor is used only when a verified source is configured. Unverified `sensor.brewzilla_power` must not gain control-freshness authority.

## Temperature roles

```text
process_temperature / mash_temperature
  canonical external mash/process probe when owned
  target/reach/readiness authority during Heatstrike/Mash

safety_temperature / wort_temperature
  BrewZilla internal/kettle view
  limiter/overshoot/safety context
```

The internal sensor must not silently take over target-reached authority while an owned external process probe is degraded.

### External process-sensor ownership

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  hot-side owns the external process sensor

Boil starts
  hot-side releases ownership

Chill -> Transfer
  Cooling owns/interprets the same sensor as CFC wort-out when applicable
```

## Heatstrike and Mash-In authority

`Brewfather Play` is treated as operator authorization for the dedicated Heatstrike/Mash-In physical controller. While that controller owns the phase it may modulate target, heat and pump without generating a new generic confirmation for every internal adjustment. Safety and ABORT remain authoritative.

Outside that dedicated authority, positive automatic control continues through generic Supervised Apply where applicable.

## Consolidated Heatstrike -> Mash-In contract

`brewzilla_hot_side_contract.py` is the boundary between temperature roles, Clean Heatstrike and the Mash-In state machine.

```text
READY
  operator gate only
  does not release strike target or stop Heatstrike regulation

Mash-In Started
  releases strike target toward effective mash target
  pump OFF / utilization 0 %
  grain-addition window begins

Mash-In Complete
  valid only after Started
  one-way transition
  normal mash circulation may resume
```

Automatic completion requires:

```text
BA observes Brewfather PAUSED after Mash-In Started
THEN later Brewfather RUNNING / Continue
```

These are not enough by themselves:

```text
BF already running at Mash-In Started
active Brewfather target movement
normalized runtime staying live/running
```

## Heatstrike gradient relief

Current narrow gradient rule:

```text
MASH/BLE still below strike
AND mash/wort gradient >= 1.5 °C
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +2.0 °C

=> heat cap 5 %
=> heater master remains available
=> pump 100 %
```

Above +2.0 °C hottest-view overshoot, heat 0 / heater OFF remains authoritative. This is not a generic READY or overshoot tolerance.

## RAPT freshness and recovery

Freshness semantics are split deliberately:

```text
report/control freshness
  = last_reported, fallback last_updated
  = used by orchestration/fail-passive trust

value age / stagnation
  = last_updated + explicit change tracking
  = diagnostics only
  = must not replace canonical process-temperature freshness
```

During an active owned hot-side phase, `brewzilla_active_rcl_recovery_guard.py` requests a real coordinator refresh every 30 seconds:

```text
one BrewZilla CoordinatorEntity
  -> homeassistant.update_entity
  -> CoordinatorEntity
  -> DataUpdateCoordinator.async_request_refresh()
```

Using one trigger entity avoids duplicate cloud-fetch fan-out across several entities backed by the same coordinator.

Hard `reload_config_entry` recovery is separate and may only be used for hard connection loss/extreme report staleness, with a 15-minute minimum interval.

Important distinction:

```text
telemetry recovery request != permission to change target/heat/pump
```

## Fail-passive telemetry loss

The outer `brewzilla_fail_passive_guard.py` converts genuine active hot-side report loss into:

```text
no new BrewAssistant writes
preserve last observed/applied target and output state
allow BrewZilla local regulator to continue
request/indicate telemetry recovery
```

A stable physical temperature is not stale merely because the numeric state has not changed.

This fail-passive behavior does **not** override ABORT or explicit hard-safety paths.

## ABORT

Expected physical safe-down:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
positive-action lockout
```

Brewday operator ABORT adds a separate persistent source/ownership latch around the physical mechanism.

## Manual Brew ownership

Manual Brew can split ownership by channel:

```text
target: operator or BA
heater + heat utilization: operator or BA
pump + pump utilization: operator or BA
```

Mixed ownership is intentional. Manual ownership cannot undo an active safety block or ABORT.

## Ordered package installation

`__init__.py` installation order is functional architecture. Important active concepts include:

1. temperature-role and mash-ramp patches;
2. Heatstrike target/transition context;
3. RCL/value-stagnation diagnostics;
4. equipment-learning/advice layers;
5. mash thermal/pump guards and Clean Heatstrike;
6. Mash-In gate/readiness contract;
7. paused/execution/target-trust/local-control safety layers;
8. consolidated hot-side contract;
9. active RCL polling/recovery and final ABORT boundary;
10. Manual ownership + generic Supervised Apply/readback grace;
11. Play-granted phase authority;
12. outermost fail-passive guard.

Older guard modules may remain in the directory for history/compatibility but are not necessarily installed.

## Important files

| File | Purpose |
| --- | --- |
| `brewzilla_orchestration.py` | Core snapshot, desired physical state and executor |
| `brewzilla_temperature.py` / `brewzilla_temperature_roles.py` | Process/wort temperature resolution and ownership roles |
| `brewzilla_clean_heat_strike_guard.py` | Current pre-mash physical Heatstrike regulator |
| `brewzilla_hot_side_contract.py` | Canonical Heatstrike/Mash-In handoff contract |
| `brewzilla_mash_in_gate.py` | Mash-In state storage and operator transition surface |
| `brewzilla_mash_in_readiness_contract.py` | Fresh READY + bounded operator acceptance contract |
| `brewzilla_phase_authority.py` | Brewfather Play authorization for dedicated physical phase |
| `brewzilla_supervised_runtime_guard.py` | Generic positive-plan confirmation outside dedicated authority |
| `brewzilla_supervised_readback_grace.py` | Bounded stale readback grace after confirmed writes |
| `brewzilla_manual_brew_control.py` | Channel-scoped Manual ownership |
| `brewzilla_fail_passive_guard.py` | Outermost no-new-writes behavior on real report loss |
| `brewzilla_abort_lockout_final_guard.py` | Final ABORT/lockout protection |
| `brewzilla_active_rcl_recovery_guard.py` | Active 30 s coordinator polling + hard recovery policy |
| `brewzilla_rcl_value_recovery_guard.py` | Heatstrike value-stagnation diagnostics only |
| `brewzilla_learning.py` / `brewzilla_equipment_learning.py` | Advisory/passive learning evidence |
| `brewzilla_energy.py` | BrewZilla energy context |

## Public action surface

Examples:

```text
brewassistant.apply_brewzilla_target
brewassistant.abort_brewzilla
brewassistant.mash_in_started
brewassistant.mash_in_complete
brewassistant.start_mash_circulation
```

The service name is not the safety boundary. Every physical path must pass applicable ownership/phase/safety guards.

## Debugging

Use Flight Recorder plus orchestration attributes. Useful evidence includes:

- runtime source/state/stage/step;
- effective vs device target;
- process and safety temperatures + source/report age;
- value-stagnation diagnostics separately from report freshness;
- desired/current heat and pump utilization;
- Mash-In gate state and BF post-start pause marker;
- phase authority state;
- active RCL polling last-request timestamp/entity;
- pending confirmation state;
- fail-passive reason;
- `apply_result` and actions;
- ABORT/lockout state.

## Do not change casually

1. Wrapper installation order is functional architecture.
2. Process and safety temperature roles are not interchangeable.
3. READY is not Mash-In Started.
4. Mash-In Started owns the pump-off grain-addition window.
5. Automatic completion requires post-start BF PAUSED followed by later RUNNING.
6. Report freshness and value age are different clocks.
7. Brewfather Play authorizes the dedicated pre-mash controller; do not reintroduce per-modulation confirmation casually.
8. Ordinary real data loss is fail-passive, not automatic heater/pump shutdown.
9. ABORT and hard safety always outrank normal ownership/advice/fail-passive behavior.
10. Cooling owns the external process sensor after BOIL handoff; hot-side code must release it.
