# BrewZilla backend

Status: active supervised hot-side development  
Code snapshot documented: 2026-09-05

`brewzilla` is BrewAssistant's BrewZilla/RAPT hot-side hardware adapter. It consumes normalized Brewday intent, resolves physical temperature roles, computes target/heat/pump behavior, applies ownership and safety guards, and performs permitted writes to BrewZilla/RAPT entities.

This package is intentionally implemented as an ordered wrapper/guard chain. Installation order in `__init__.py` is part of the control architecture.

## Responsibilities

- read BrewZilla/RAPT target, temperature, connection, heater, pump and utilization state;
- resolve process/mash and kettle/wort temperature roles;
- convert trusted Brewday Runtime intent into physical hot-side plans;
- regulate Heatstrike and Mash-In using the dedicated physical controller;
- handle Mash-In READY -> STARTED -> COMPLETE as an explicit operator handoff;
- regulate/advise later mash and hot-side phases through the orchestration chain;
- preserve valid local BrewZilla regulation when cloud/process telemetry is degraded;
- enforce Manual Brew channel ownership;
- use generic Supervised Apply where new positive authority is not already covered by a dedicated operator-authorized phase;
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

BrewAssistant's canonical power sensor is used only when a verified source is configured. The package currently removes the unverified `sensor.brewzilla_power` from control-freshness authority.

## Temperature roles

The hot-side contract distinguishes two physical views:

```text
process_temperature / mash_temperature
  canonical external mash/process probe when owned (for example BLE thermometer)
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

Current pre-mash architecture is deliberately different from generic per-action confirmation.

`Brewfather Play` is treated as the operator authorization for the dedicated Heatstrike/Mash-In physical controller. While that controller owns the phase it may modulate target, heat and pump without generating a new generic confirmation for every internal adjustment. Lower safety/ABORT guards remain authoritative.

`brewzilla_phase_authority.py` clears stale generic pending plans while this phase is active and keeps Brewday Advice observation/learning-only.

Outside that dedicated authority, new positive automatic control continues through the generic Supervised Apply path where applicable.

## Consolidated Heatstrike -> Mash-In contract

`brewzilla_hot_side_contract.py` is the boundary between temperature roles, Clean Heatstrike and the Mash-In state machine.

Fixed semantics:

```text
READY
  operator gate only
  does not itself release strike target or stop Heatstrike regulation

Mash-In Started
  explicit physical handoff
  releases strike target toward effective mash target
  stops circulation for grain addition

Mash-In Complete
  valid only after Started
  one-way transition; stale events must not move the state backwards
```

Automatic READY requires fresh canonical process temperature within the narrow readiness band. A separate bounded operator acceptance path can acknowledge a physically verified near-strike condition when external telemetry is stale/lagging; it must not become a silent automatic READY source.

## Fail-passive telemetry loss

Ordinary telemetry loss is not an automatic command to turn the BrewZilla off.

The outer `brewzilla_fail_passive_guard.py` converts degraded active hot-side telemetry into:

```text
no new BrewAssistant writes
preserve last observed/applied target and output state
allow BrewZilla local regulator to continue
request/indicate telemetry recovery
```

This applies to ordinary RCL/process-data loss. It does **not** override ABORT or explicit hard-safety paths.

The owned external process probe is also protected from silent fallback to the internal sensor while its ownership lock is active.

## ABORT

The physical ABORT path is authoritative and risk-reducing. The expected safe-down is:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
positive-action lockout
```

The current orchestration base carries a 600-second hardware ABORT lockout, with final ABORT guards installed late in the chain. Brewday operator ABORT adds a separate persistent source/ownership latch around this physical mechanism.

## Manual Brew ownership

Manual Brew can split ownership by channel. The final manual-control guard suppresses normal BrewAssistant writes for operator-owned channels without allowing Manual ownership to undo a safety block or ABORT.

Conceptually:

```text
target: operator or BA
heater + heat utilization: operator or BA
pump + pump utilization: operator or BA
```

Mixed ownership is intentional.

## RAPT freshness and recovery

Freshness uses entity `last_updated` (value freshness), not merely report traffic. Recovery code may request entity/config refresh, but recovery itself must not casually rewrite physical control state.

Important distinction:

```text
telemetry recovery request != permission to change target/heat/pump
```

## Ordered package installation

`__init__.py` installs current behavior in layers. Important active concepts include:

1. temperature-role and mash-ramp patches;
2. Heatstrike target/transition context;
3. RCL recovery and process-sensor guards;
4. equipment-learning/advice layers;
5. mash thermal/pump guards and Clean Heatstrike;
6. Mash-In gate/readiness contract;
7. paused/execution/target-trust/local-control safety layers;
8. consolidated hot-side contract;
9. active RCL recovery and final ABORT boundary;
10. Manual ownership + generic Supervised Apply/readback grace;
11. Play-granted phase authority;
12. outermost fail-passive guard.

Several older guard modules remain in the directory for history/compatibility but are intentionally **not installed**. In particular, the former ordinary freshness/stale-safe behavior that translated cloud staleness into output safe-down is not the current contract.

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
| `brewzilla_supervised_runtime_guard.py` | Generic positive-plan confirmation layer outside dedicated authority |
| `brewzilla_supervised_readback_grace.py` | Bounded stale readback grace after confirmed writes |
| `brewzilla_manual_brew_control.py` | Channel-scoped Manual ownership |
| `brewzilla_fail_passive_guard.py` | Outermost no-new-writes behavior on ordinary telemetry loss |
| `brewzilla_abort_lockout_final_guard.py` | Final ABORT/lockout protection |
| `brewzilla_active_rcl_recovery_guard.py` / `brewzilla_rcl_value_recovery_guard.py` | Telemetry recovery diagnostics/policy |
| `brewzilla_learning.py` / `brewzilla_equipment_learning.py` | Advisory/passive learning evidence |
| `brewzilla_energy.py` | BrewZilla energy context |

## Public action surface

The integration exposes services/buttons around actions such as:

```text
brewassistant.apply_brewzilla_target
brewassistant.abort_brewzilla
brewassistant.mash_in_started
brewassistant.mash_in_complete
brewassistant.start_mash_circulation
```

The service name is not the safety boundary. Every physical path must still pass the applicable ownership/phase/safety guards.

## Debugging

Use the Brewday Flight Recorder together with orchestration attributes. Useful evidence includes:

- runtime source/state/stage/step;
- effective vs device target;
- process and safety temperatures + source/age;
- desired/current heat and pump utilization;
- Mash-In gate state;
- phase authority state;
- pending confirmation state;
- fail-passive reason;
- RCL freshness/recovery diagnostics;
- `apply_result` and executed `actions`;
- ABORT/lockout state.

## Do not change casually

1. Wrapper installation order is functional architecture.
2. Process and safety temperature roles are not interchangeable.
3. READY is not the same physical transition as Mash-In Started.
4. Brewfather Play authorizes the dedicated pre-mash physical controller; do not reintroduce per-modulation confirmations there without revisiting the contract.
5. Generic positive authority outside dedicated phase ownership remains guarded/supervised.
6. Ordinary data loss is fail-passive, not automatic heater/pump shutdown.
7. ABORT and hard safety always outrank normal ownership/advice/fail-passive behavior.
8. Cooling owns the external process sensor after BOIL handoff; hot-side code must release it.
