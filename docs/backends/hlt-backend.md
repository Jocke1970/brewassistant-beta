# HLT backend — planning specification

Status: planned / simulation-first architecture  
Planning baseline: 2026-09-15

`hlt` is the planned BrewAssistant backend for a Hot Liquor Tank / sparge-water heater. The first implementation target is **not monitor-only** and does not require real HLT hardware. It should run the complete HLT process logic against a virtual HLT model while suppressing only the final physical heater write.

The goal is to prove that BrewAssistant can schedule sparge-water heating around BrewZilla's electrical demand before any HLT is connected.

## Core goals

The HLT backend should:

- consume normalized sparge-water intent from Brewday Runtime;
- remain inactive automatically for no-sparge brews;
- run a real HLT state machine in simulation;
- model virtual water temperature from granted electrical energy;
- request power through the shared Power Budget Arbiter;
- yield when BrewZilla needs the shared capacity back;
- calculate whether sparge water would actually be ready in time;
- record all virtual heater, grant, deny and reclaim decisions in Flight Recorder;
- later allow the same logic to be bound to physical HLT entities without redesigning the state machine.

## Non-goals

The HLT backend must not:

- own BrewZilla process heat, target or pump decisions;
- start merely because instantaneous BrewZilla wattage happens to look low;
- physically constrain BrewZilla while simulation mode is active;
- parse Brewfather directly when normalized Brewday intent is available;
- hard-code voltage, breaker size, HLT brand or heater wattage;
- require a physical HLT to validate scheduling/arbitration logic.

## Ownership boundary

```text
Brewday Runtime
  sparge required?
  sparge volume
  sparge target
  stage / timing context

HLT backend
  HLT state machine
  virtual/real HLT temperature model
  heater demand
  readiness
  local HLT safety

Power Budget Arbiter
  shared-circuit reservation
  grants / denials / revocations
  BrewZilla reclaim ordering

BrewZilla backend
  BrewZilla process demand
  BrewZilla physical control chain
```

The HLT requests watts. It does not implement its own parallel sharing algorithm.

## Simulation mode

Simulation is the first executable mode.

It should use real Brewday/BrewZilla signals where available and configurable virtual HLT parameters:

```text
water_volume_l
start_temperature_c
target_temperature_c
heater_rated_w
heater_efficiency
ambient_temperature_c       optional
heat_loss_coefficient       optional
virtual_release_delay_s
```

No physical HLT heater entity is required.

### Virtual thermal model

For each simulation step, granted heater energy should update virtual water temperature approximately as:

```text
useful_energy_j = granted_power_w * efficiency * dt_s
mass_kg         ~= water_volume_l
delta_t_c       = useful_energy_j / (mass_kg * 4186)
```

An optional heat-loss term may later subtract energy as the water rises above ambient temperature.

The model is intentionally practical rather than laboratory-grade. Its purpose is to determine whether the scheduling and arbitration logic gets the water ready in time and to compare later against real hardware.

## Brewday input contract

Proposed normalized fields:

```text
sparge_required: bool | unknown
sparge_water_volume_l: float | unknown
sparge_water_target_c: float | unknown
brewday_stage: enum
brewday_active: bool
source: brewfather | manual | other adapter | none
```

Source precedence:

```text
active normalized Brewday Runtime
  -> explicit HLT manual/simulation inputs
  -> explicitly enabled configured fallback
  -> otherwise no HLT heating request
```

Missing volume or target must not silently become a guessed recipe.

## No-sparge behavior

```text
sparge_required == false
  -> HLT demand = 0
  -> no power lease
  -> state = NOT_REQUIRED
```

This must remain visible in diagnostics.

## State machine

```text
DISABLED
IDLE
NOT_REQUIRED
WAITING_FOR_CONTEXT
WAITING_FOR_WINDOW
WAITING_FOR_POWER
HEATING
YIELDING
HOLDING
READY
COMPLETE
FAULT
```

`YIELDING` is explicit because "HLT told to stop" and "electrical capacity released" are different events.

## Phase policy

Initial scheduling baseline:

| Brewday phase | HLT policy |
| --- | --- |
| Setup | wait for valid context unless manual simulation explicitly starts |
| Heat strike | normally BZ priority; no new HLT start |
| Mash-In | avoid starting during physical handoff |
| Mash | primary HLT heating window |
| Mash out | HLT yields whenever BZ requires capacity |
| Sparge | hold/finish if required and capacity exists |
| Pre-boil | normally HLT complete/off |
| Boil+ | no normal HLT duty for completed sparge water |

Actual electrical permission is always decided by the arbiter, not by stage name alone.

## Power request

For the initial binary-heater model:

```text
consumer = hlt
mode = binary
demand_w = heater_rated_w
priority = secondary_hot_side
reason = sparge_water_heating
```

A binary heater receives either its full demand or zero.

## BrewZilla reclaim contract

If BrewZilla needs more capacity while HLT is heating:

```text
1. arbiter revokes HLT grant
2. HLT -> YIELDING
3. virtual/physical heater -> OFF
4. release delay/readback completes
5. HLT reservation is released
6. higher BrewZilla allocation becomes available
```

In simulation this sequence must be executed and logged even though no physical HLT exists.

Simulation must calculate what BrewZilla **would** be permitted to use, but must not physically cap or rewrite BrewZilla.

## Simulation outputs

Provisional diagnostics:

```text
sensor.brewassistant_hlt_state
sensor.brewassistant_hlt_virtual_temperature
sensor.brewassistant_hlt_target
sensor.brewassistant_hlt_readiness
sensor.brewassistant_hlt_power_request_w
sensor.brewassistant_hlt_power_grant_w
sensor.brewassistant_hlt_time_to_target
sensor.brewassistant_hlt_energy_added_wh
binary_sensor.brewassistant_hlt_virtual_heater
binary_sensor.brewassistant_hlt_ready
```

Useful attributes:

```text
water_volume_l
heater_rated_w
heater_efficiency
current lease
current BrewZilla request/grant
waiting/yield reason
estimated ready time
```

## Flight Recorder evidence

At minimum:

```text
hlt_simulation_started
hlt_state_changed
hlt_target_resolved
hlt_power_requested
hlt_power_granted
hlt_power_denied
hlt_virtual_heater_on
hlt_yield_requested
hlt_virtual_heater_off
hlt_release_confirmed
hlt_ready
hlt_complete
hlt_fault
```

Each event should include stage, virtual temperature, target, volume, HLT request/grant, BrewZilla request/grant and circuit budget.

## Simulation scenarios

The first implementation should support live simulation and deterministic/replay-style scenarios.

Required scenarios:

```text
stable mash + low BZ demand -> HLT heats
BZ demand rises -> HLT yields -> release -> BZ reclaim
HLT reaches target -> holding/readiness
no-sparge -> no HLT request
unknown/stale BZ demand -> no unsafe new HLT grant
virtual release delay -> reclaim waits correctly
lease expiry/restart -> grants invalidated
Manual Brew ownership -> residual budget conservative
```

## Development order

### SIM-0 — model/config

- virtual HLT volume/start/target;
- rated heater W;
- efficiency/loss model;
- release delay;
- shared usable circuit budget;
- BrewZilla demand-to-watts mapping.

### SIM-1 — executable simulation

- full HLT state machine;
- real arbiter grant/deny/revoke/reclaim logic;
- virtual heater actions;
- virtual thermal integration;
- BrewZilla `would_grant` / `would_cap` calculations;
- Flight Recorder integration.

### SIM-2 — scenario/fault analysis

- automated scenario tests;
- restart/lease tests;
- stale/unknown input tests;
- manual-ownership tests;
- no-sparge tests;
- anti-chatter/reclaim timing tests.

### SIM-3 — real brew trace tuning

- run simulation during or replay real brewdays;
- measure usable HLT heating windows;
- compare predicted readiness against sparge timing;
- tune scheduling, margins and model parameters.

### HW-1 — physical HLT binding

Only after simulation is convincing:

- configure real heater/temp/power entities;
- verify rated load and circuit;
- bind virtual actuator boundary to real HLT output;
- supervised field test;
- direct operation after successful validation.

## Acceptance criteria before hardware binding

1. Full HLT state machine runs with no physical HLT.
2. Virtual water temperature responds to granted heater energy.
3. Binary HLT reserves full configured heater wattage.
4. Low instantaneous BrewZilla wattage alone never creates permission.
5. Combined simulated reservations never exceed usable budget.
6. BrewZilla reclaim waits until HLT release completes.
7. Simulation never physically changes BrewZilla.
8. No-sparge creates no HLT demand.
9. Restart/lease expiry cannot preserve stale grants.
10. Flight Recorder can reconstruct every simulated power transition.
11. A completed run can answer: **Would the sparge water have reached target in time?**

## Open hardware inputs

Physical commissioning remains intentionally deferred:

```text
real HLT heater entity
real HLT temperature entity
optional power entity
verified heater watts
actual shared protected-circuit limit
hardware over-temperature/dry-fire behavior
```

Those values should become configuration, not magic constants.
