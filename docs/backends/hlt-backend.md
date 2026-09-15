# HLT backend — planning specification

Status: planned / architecture only  
Planning baseline: 2026-09-15

`hlt` is the planned BrewAssistant backend for a Hot Liquor Tank / sparge-water heater. Its primary job is to prepare and hold sparge water at the required temperature without competing unsafely with BrewZilla for electrical capacity.

This document is intentionally a design/roadmap document. No `custom_components/brewassistant/hlt/` implementation should be considered current until code exists and a code-local README documents the actual contract.

## Goals

The HLT backend should:

- heat sparge water to the recipe/manual target temperature;
- derive the required volume and temperature from normalized Brewday context when available;
- automatically remain inactive for no-sparge brews;
- use spare electrical capacity opportunistically while BrewZilla is in a low-power phase, especially mash;
- cooperate with a shared Power Budget Arbiter rather than independently guessing whether enough power is available;
- yield safely and predictably when BrewZilla needs more power again;
- expose clear state, target, temperature, power-grant and readiness diagnostics;
- integrate with Brewday Flight Recorder so electrical arbitration can be reconstructed after a field test;
- support the same policy philosophy as other BrewAssistant hardware modules: monitor/read-only, supervised apply and direct control as explicit capabilities rather than hidden behavior.

## Non-goals

The HLT backend should not:

- own BrewZilla heat, target or pump decisions;
- read BrewZilla power and directly manipulate BrewZilla entities as a shortcut;
- override ABORT, hard-safety or Manual Brew ownership;
- infer that a momentarily low measured wattage means it is safe to start an HLT;
- assume a fixed 230 V supply, breaker size or heater wattage in code;
- require Brewfather specifically; Manual Brewday and other recipe adapters should be able to provide the same normalized sparge-water intent.

## Ownership boundary

Conceptually:

```text
Brewday Runtime
  owns process intent:
    sparge required?
    sparge water volume
    sparge water target temperature
    process stage / timing context

HLT backend
  owns HLT process state:
    idle / waiting / heating / holding / ready / fault
    HLT target interpretation
    HLT heater request
    HLT temperature safety

Power Budget Arbiter
  owns shared electrical permission:
    whether HLT may consume power now
    how much power is granted
    coordinated handoff when BrewZilla reclaims capacity

BrewZilla backend
  owns BrewZilla process control:
    desired BrewZilla heat utilization
    physical BrewZilla writes after power-budget permission
```

The HLT backend must request electrical capacity. It must not create its own parallel power-sharing logic inside the HLT state machine.

## Expected hardware abstraction

The first implementation should be generic enough to support a simple electrically heated sparge-water vessel rather than one specific brand.

Minimum logical inputs/outputs:

```text
required
  HLT temperature sensor
  HLT heater switch or controllable heater output
  configured HLT heater rated power (W)

recommended
  HLT power sensor
  independent/local over-temperature protection

optional future
  variable heater utilization / SSR output
  water-level or dry-fire protection sensor
  lid/flow/auxiliary diagnostics
```

A binary heater must be treated as an all-or-nothing electrical consumer. Before switching it on, the arbiter must reserve its full configured rated wattage plus any applicable margin.

## Brewday input contract

The backend should consume normalized intent rather than parse Brewfather entities directly.

Proposed logical fields:

```text
sparge_required: bool | unknown
sparge_water_volume_l: float | unknown
sparge_water_target_c: float | unknown
brewday_stage: enum
brewday_active: bool
source: brewfather | manual | other adapter | none
```

Suggested source precedence:

```text
active normalized Brewday Runtime intent
  -> explicit HLT manual override
  -> configured fallback target only when the operator has explicitly enabled fallback mode
  -> otherwise no automatic heating
```

A missing sparge target/volume must not silently become a guessed recipe.

## No-sparge behavior

When normalized Brewday intent says `sparge_required == false`:

```text
HLT automatic request = OFF
power lease request = none
state = NOT_REQUIRED (or IDLE with explicit reason)
```

No-sparge detection should be visible in diagnostics so an unexpectedly idle HLT is explainable.

## Proposed state machine

```text
DISABLED
  module/control policy disabled

IDLE
  backend available, no active brewday need

WAITING_FOR_CONTEXT
  active brewday but sparge target/volume is incomplete

WAITING_FOR_WINDOW
  sparge is required but process/timing policy says heating should not start yet

WAITING_FOR_POWER
  HLT wants heat but no safe electrical lease is currently available

HEATING
  heater is permitted and energized

YIELDING
  BrewZilla has requested capacity back; HLT heater is being turned off and electrical release is being verified

HOLDING
  at/near target; heater may cycle only when a valid power lease is available

READY
  sparge water is within readiness band and available for use

COMPLETE
  sparge-water duty for the current brewday is finished

FAULT
  temperature/power/readback/safety fault; heater request forced off
```

`YIELDING` is deliberately explicit. A shared-load design needs to distinguish "HLT was told to turn off" from "electrical capacity is actually free again".

## Phase policy

Initial policy should be conservative.

| Brewday phase | HLT automatic heating policy |
| --- | --- |
| Setup | normally wait for valid recipe/runtime context |
| Heat strike | normally no HLT lease; BrewZilla has high-priority heating demand |
| Mash-In | normally no new HLT start during physical handoff |
| Mash | primary opportunistic HLT heating window |
| Mash out | HLT yields whenever BrewZilla needs the capacity |
| Sparge | HLT may hold target if required and power is available |
| Pre-boil | HLT usually complete/off; BrewZilla priority |
| Boil+ | no normal HLT heating for the completed sparge duty |

The table is a policy baseline, not a hard-coded assumption that BrewZilla always uses a particular utilization in a phase. Actual electrical permission comes from the arbiter.

## Target and readiness behavior

Proposed configurable values:

```text
target_c                    normalized sparge target
readiness_band_c            e.g. narrow +/- band around target
hold_deadband_c             avoids rapid heater cycling
max_hlt_temperature_c       hard backend ceiling below hardware high-limit
minimum_on_time_s           anti-chatter
minimum_off_time_s          anti-chatter
sensor_stale_timeout_s      freshness requirement
```

Exact defaults should be chosen only when implementation begins and hardware is known.

A target reached event should be based on fresh HLT water temperature, not heater state or elapsed time.

## Electrical cooperation with BrewZilla

The HLT backend should expose a demand to the Power Budget Arbiter, for example:

```text
consumer = hlt
demand_w = configured_hlt_heater_w
mode = binary
priority = secondary_hot_side
reason = sparge_water_heating
```

The arbiter returns something equivalent to:

```text
granted: bool
granted_w: float
lease_id: str
lease_expires_at: timestamp
reason: str
```

The HLT may energize only while a valid grant exists.

### Critical handoff rule

If BrewZilla needs more power while HLT is heating:

```text
1. Power Arbiter revokes the HLT grant.
2. HLT enters YIELDING and commands heater OFF.
3. Heater-off/readback or configured release delay is verified.
4. Arbiter marks the HLT watts free.
5. BrewZilla may then receive/apply the higher power allocation.
```

This prevents the unsafe race where HLT sees "spare" power, starts, and BrewZilla independently jumps back to a high utilization before HLT is off.

## Safety and fail behavior

### HLT telemetry loss

Because HLT heating is secondary and not required to preserve BrewZilla process safety, the default HLT response to stale/invalid temperature telemetry should be fail-safe OFF:

```text
no fresh HLT water temperature
  -> no new heater-on command
  -> existing heater request removed
  -> electrical lease released after off confirmation
```

This differs intentionally from BrewZilla's ordinary fail-passive cloud-telemetry behavior.

### Power telemetry loss

A power sensor is useful for verification but cannot be the sole safety mechanism. Electrical grants must remain conservative when a configured readback becomes unavailable.

For a binary HLT, configured rated wattage remains the reservation baseline even if a power sensor reports less.

### Restart behavior

After Home Assistant/BrewAssistant restart:

```text
HLT physical command authority starts ungranted
persisted brewday context may be restored
power lease must be reacquired
heater must not be assumed safe-on merely because a prior state said HEATING
```

Whether the physical plug itself restores ON/OFF after power loss is a hardware setup concern and should be documented during commissioning.

### Hardware safety

Software control is not a substitute for:

- vessel/heater dry-fire protection where applicable;
- an independent over-temperature mechanism where practical;
- electrical installation sized for the configured circuit load;
- a known HLT heater rating.

## Manual ownership and control modes

The planned backend should align with BrewAssistant capability policy:

```text
monitor_only
  calculate need/readiness/power opportunity; never write HLT heater

supervised
  operator authorizes positive HLT control; backend may then regulate within that authorized duty

direct
  backend may control HLT automatically within all guards

off
  module inactive
```

A future implementation decision is whether supervised authorization is per heater transition or per HLT duty/session. For usability and consistency with phase authority elsewhere, a session-level authorization is likely preferable, but this is not locked by this planning document.

Manual ownership must remain able to suppress normal HLT writes without bypassing hard safety or electrical-budget rules.

## Proposed entities

Names are provisional.

```text
sensor.brewassistant_hlt_state
sensor.brewassistant_hlt_temperature
sensor.brewassistant_hlt_target
sensor.brewassistant_hlt_readiness
sensor.brewassistant_hlt_power_request_w
sensor.brewassistant_hlt_power_grant_w
sensor.brewassistant_hlt_power_reason
sensor.brewassistant_hlt_time_to_target
binary_sensor.brewassistant_hlt_power_granted
binary_sensor.brewassistant_hlt_ready
binary_sensor.brewassistant_hlt_fault
switch.brewassistant_hlt_enabled
select.brewassistant_hlt_control_mode
```

If the source entities already exist in HA, BrewAssistant should reference them rather than clone their raw sensor semantics unnecessarily.

## Configuration candidates

```text
HLT heater entity
HLT temperature entity
HLT power entity (optional)
HLT rated heater power W
maximum HLT temperature
hold/readiness deadbands
minimum on/off time
control mode
shared circuit / power-budget profile
```

Electrical circuit settings should live in the shared power-budget configuration rather than be duplicated in both HLT and BrewZilla.

## Flight Recorder / audit evidence

Important events/fields:

```text
hlt_state_changed
hlt_target_resolved
hlt_power_requested
hlt_power_granted
hlt_power_denied
hlt_yield_requested
hlt_heater_off_confirmed
hlt_ready
hlt_fault

context fields:
  brewday stage
  sparge target / volume / source
  HLT temp + freshness
  HLT demand W
  current lease/grant
  BrewZilla requested/granted W
  circuit usable budget W
  arbiter reason
  heater command/readback
```

A field test should be diagnosable from recorder data without relying on dashboard screenshots.

## Dashboard concept

A compact HLT card can eventually show:

```text
Sparge water: 78.0 C
Current: 63.4 C
State: Heating
Power: 2000 W granted
BZ: 32% / priority
ETA: 18 min
```

When waiting:

```text
State: Waiting for power
Reason: BrewZilla reclaim / Mash-out ramp
```

The UI must distinguish target-ready from merely heater-off.

## MVP implementation slices

### HLT-0 — planning/calibration

- document actual HLT hardware;
- confirm heater rated power;
- confirm temperature source;
- confirm whether HLT and BrewZilla share the same protected circuit;
- define usable circuit budget and safety margin.

### HLT-1 — monitor only

- normalized sparge intent;
- HLT temperature/readiness sensor;
- proposed heater demand;
- no physical writes;
- Flight Recorder visibility.

### HLT-2 — Power Budget Arbiter integration

- BrewZilla publishes desired electrical demand;
- HLT publishes binary demand;
- arbiter grants/denies safely;
- no automatic heater write until arbitration is field-tested.

### HLT-3 — supervised heater control

- operator-authorized HLT duty;
- power lease required for ON;
- YIELDING handshake with BrewZilla reclaim;
- stale-temperature OFF behavior;
- anti-chatter.

### HLT-4 — direct/predictive heating

- optional direct mode;
- estimate heating lead time from volume, delta-T and observed heater performance;
- start late enough to reduce unnecessary holding losses while still reaching sparge readiness.

## Acceptance criteria before direct control

1. HLT never energizes without a valid power grant.
2. Binary HLT reserves its full configured heater wattage.
3. BrewZilla and HLT cannot independently create a combined grant above the configured usable circuit budget.
4. A BrewZilla power increase revokes HLT first and verifies electrical release before the extra BrewZilla allocation is applied.
5. Stale/invalid HLT temperature removes HLT heating authority.
6. No-sparge brews do not request HLT power.
7. HLT target and volume come from normalized Brewday intent or explicit manual input, not hidden guesses.
8. Restart does not resurrect an old HLT power lease.
9. Manual ownership and ABORT/hard-safety remain higher authority than normal HLT automation.
10. Flight Recorder shows enough evidence to reconstruct every grant, denial and reclaim.

## Field-test matrix

At minimum test:

```text
Mash stable, BZ low demand -> HLT receives grant and heats
BZ demand rises -> HLT yields, off confirmed, BZ receives capacity
HLT temp reaches target -> heater cycles/holds without chatter
HLT sensor stale -> heater off + lease release
HLT power readback missing -> conservative behavior
Brewday switches to no-sparge / completed -> HLT request removed
HA restart during HLT heating -> no stale lease reuse
Manual HLT ownership -> BA does not issue normal heater commands
BrewZilla ABORT / hard-safety -> no HLT behavior can interfere with it
```

## Open commissioning inputs

These are intentionally left unresolved until the actual HLT hardware is selected/connected:

- heater entity;
- temperature entity;
- optional power entity;
- heater rated watts;
- actual protected-circuit limit shared with BrewZilla;
- desired safety margin;
- whether HLT heat is binary or modulated;
- desired sparge readiness temperature band.

They should become configuration/calibration data, not magic constants in the backend.
