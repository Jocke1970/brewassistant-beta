# Fermentation Control Provider Contract

Status: architecture contract / current chamber provider + planned provider model  
Last synced: 2026-09-11

This document defines the common BrewAssistant control boundary for fermentation temperature control.

It is intentionally hardware-neutral. The current fermentation chamber and a future Grainfather fermenter such as GF30 should follow the same ownership model even though their physical interfaces are different.

## Core principle

BrewAssistant should decide **what fermentation temperature is desired**. The selected physical provider should translate that process target into the target understood by its local controller. The local controller should then decide **how to heat or cool**.

Conceptually:

```text
fermentation_tracking
  observations / readiness / recommended beer target
                |
                v
      fermentation control contract
                |
        selected provider only
        +-------+------------------+
        |                          |
        v                          v
fermentation_chamber      future grainfather_fermenter
translate beer target     translate beer target
into chamber-air target   into Grainfather target
        |                          |
        v                          v
HA climate controller      Grainfather/GF controller
owns heat/cool cycling     owns heat/cool cycling
```

The provider boundary prevents BrewAssistant from becoming a second thermostat that fights the controller already attached to the hardware.

## Ownership contract

### Fermentation strategy / tracking

`fermentation_tracking` owns process observations and fermentation-derived state:

- normalized gravity and liquid-temperature observations;
- source selection and observation quality;
- progress, stability and readiness;
- recommended beer/liquid temperature when enough process context exists.

It does **not** own a heater, compressor, fan, pump, cooling valve or climate entity.

It should not care whether the physical fermentation vessel is in a refrigerator, a Grainfather fermenter or another future controller.

### Physical provider

A fermentation control provider owns translation from BrewAssistant's desired beer/liquid target into the target native to one physical control system.

A provider may therefore need device-specific translation. For example:

- a chamber provider may calculate a chamber-air target from beer temperature and air/liquid delta;
- a Grainfather provider may be able to pass the approved beer target directly to the Grainfather fermentation controller.

The provider may propose/write a **setpoint**, but it should not recreate local thermostat logic when the downstream controller already owns that responsibility.

### Local regulator

The downstream local controller owns actuator-level regulation:

- heating/cooling demand;
- hysteresis/deadband;
- compressor or pump cycling;
- local safety behavior;
- hardware-specific timing and switching.

For the current chamber this is the Home Assistant `climate` controller. For a future GF30 path this should be the Grainfather controller itself if live validation confirms the expected behavior.

## Single-provider authority

Only one physical fermentation provider may have write authority for a fermentation target at a time.

Conceptually the future selection could be:

```text
monitor_only
fermentation_chamber
grainfather_fermenter
<future provider>
```

Provider selection is an architecture requirement before a second writable provider is enabled. It is **not yet implemented as a generic selector**.

This prevents scenarios such as:

```text
fermentation_chamber -> writes one target
GF30 provider        -> writes another target
```

for the same fermentation session.

## Current implementation: fermentation chamber

`custom_components/brewassistant/fermentation_chamber/` is the currently implemented physical provider.

Its path is:

```text
fermentation_tracking recommended liquid target
        |
        v
fermentation_chamber air-target model
        |
        v
Supervised Apply pending action
        |
        v
climate.fermentation_chamber target
        |
        v
local climate controller decides heat/cool
```

The chamber backend therefore owns **setpoint translation**, not raw heater/compressor switching.

Its effective chamber-air calculation remains device/environment specific and belongs inside the chamber provider.

## Planned provider: Grainfather fermenter / GF30

A future Grainfather fermentation provider should follow the same contract:

```text
fermentation_tracking recommended liquid target
        |
        v
Grainfather fermentation provider
        |
        v
Supervised Apply
        |
        v
Grainfather controller target/profile step
        |
        v
Grainfather controller decides heat/cool
```

Earlier integration research identified `grainfather.adjust_current_step_temperature` as a promising cloud-service bridge. That remains a **planned candidate**, not a validated production contract.

Before enabling writes with real hardware, verify:

1. the actual HA entities/attributes exposed for the physical fermenter;
2. controller/session linkage;
3. target write and readback behavior;
4. cloud latency and failure behavior;
5. whether the local controller independently manages heating and cooling;
6. behavior with the Cooling Pump Kit and any later glycol setup;
7. ramps, diacetyl rest and cold-crash transitions.

No direct Cooling Pump Kit, heater, compressor or valve control should be invented unless future hardware evidence proves that BrewAssistant must own it.

## Supervised Apply rule

A newly added physical provider starts behind BrewAssistant's generic Supervised Apply boundary.

The intended flow is:

```text
BA recommends target
  -> provider prepares target action
  -> user confirms APPLY
  -> provider writes the downstream controller target
  -> provider reads back/observes the resulting state
```

Direct automatic target changes are a later decision and require field evidence. They are not an assumed end state.

## Readback and diagnostics

A provider should expose enough diagnostics to distinguish:

```text
recommended beer target
translated provider target
current downstream target
current measured beer temperature
provider status/readiness
pending confirmation
last confirmed write/readback
```

If downstream heat/cool demand is observable without taking control, it is useful diagnostic telemetry but does not change ownership.

## Failure behavior

Providers must fail passive when required context is unavailable or ambiguous.

Examples:

- no trusted liquid temperature;
- no fermentation target;
- multiple possible physical controllers without explicit selection;
- stale/unavailable downstream controller;
- provider not linked to the active fermentation session;
- target write without trustworthy readback.

The correct outcome is monitor-only / not-ready, not an invented fallback target or raw actuator takeover.

## Relationship to `fermentation/`

`custom_components/brewassistant/fermentation/` is a legacy compatibility package only.

The word "fermentation" may be used conceptually for the overall strategy/control flow, but new ownership must not be placed in that compatibility package.

Current canonical ownership remains:

```text
fermentation_tracking/
  observations, calculations, readiness, recommended beer target

fermentation_chamber/
  implemented chamber provider / target translation

fermentation/
  compatibility aliases only
```

A future Grainfather fermenter backend should be a separate provider package rather than being added to `fermentation/`.

## Roadmap

### Current

- fermentation tracking is hardware-independent;
- chamber target translation exists;
- chamber target writes are behind Supervised Apply;
- the HA climate controller owns actual heat/cool regulation.

### Before a second writable provider

- formalize provider selection/authority in executable code;
- expose enough provider diagnostics to make ownership obvious;
- ensure only the selected provider can create a pending target action.

### When GF30 hardware becomes available

- validate the live Grainfather integration surface;
- implement a read-only Grainfather provider first;
- verify target service/readback behavior;
- add a registered Supervised Apply executor only after live validation;
- field-test normal fermentation, temperature rise and cold crash.

### Later, only if justified

Consider automatic target transitions after sufficient field evidence. Do not bypass the downstream controller's local thermostat logic merely to make BrewAssistant appear more "direct".

## Do not change casually

1. BrewAssistant owns fermentation intent; local controllers own actuator cycling when they already provide that function.
2. Only one physical fermentation provider may write targets for a session.
3. `fermentation_tracking` stays hardware-agnostic.
4. `fermentation/` stays compatibility-only.
5. New providers start fail-passive/read-only and move through Supervised Apply after live validation.
6. Do not add raw heater/cooler/pump control unless hardware evidence and architecture explicitly require it.
