# Grainfather Fermenter backend

Status: phase 1 scaffold / read-only discovery / parked until live hardware  
Initial hardware target: Grainfather GF30 Conical Fermenter  
Upstream Home Assistant integration: `fidley/grainfather_integration`

This package is intentionally separate from BrewAssistant's reserved `grainfather` hot-side adapter. The existing `grainfather` module remains available for Grainfather brewing systems such as G30/G40-class hardware. This package is for fermentation hardware.

Longer architecture/roadmap: [`../../../docs/backends/grainfather-fermenter.md`](../../../docs/backends/grainfather-fermenter.md)

## Phase 1 goal

Prepare the BrewAssistant side before a physical GF30 is available, without inventing entities or control behavior.

The backend currently:

- discovers Grainfather fermentation-device states by the upstream public `grainfather_entity_type` attribute;
- groups temperature and gravity telemetry by Grainfather `device_id`;
- reads controller linkage, linked brew session and `last_heard` metadata;
- matches the device to the Grainfather brew-session anchor;
- detects whether `grainfather.adjust_current_step_temperature` exists;
- reports whether the future supervised target bridge has enough prerequisites;
- performs **no service calls** and remains fail-passive/read-only.

## Why no hard-coded entity IDs

The upstream integration creates fermentation devices dynamically and their friendly/entity names depend on the user's Grainfather account and device names. BrewAssistant therefore discovers them from stable attributes instead of assuming an entity such as `sensor.grainfather_gf30_temperature`.

Current upstream fermentation-device attributes include:

```text
grainfather_entity_type: fermentation_device
device_id
last_heard
linked_brew_session_id
linked_brew_session_name
is_controller_linked
```

The brew-session anchor exposes data including:

```text
grainfather_entity_type: brew_session
brew_session_id
recipe_id
status
fermentation_device_ids
fermentation_steps
```

## GF30 identification boundary

The current upstream Home Assistant state surface identifies fermentation devices and whether a controller is linked, but does not expose a field that proves a selected device is specifically a GF30.

Until real hardware is available BrewAssistant therefore uses this conservative rule:

```text
exactly one controller-linked device -> safe discovery candidate
multiple controller-linked devices    -> ambiguous; select nothing
single unverified device              -> telemetry-only candidate
```

The backend explicitly reports:

```text
model_verified: false
```

A friendly name containing `GF30` is not considered sufficient proof.

## Control boundary

Phase 1 never sends a Grainfather command.

The upstream integration currently exposes a service that can set the temperature of the active Grainfather fermentation step:

```text
grainfather.adjust_current_step_temperature
```

That is a promising future bridge because it can let Grainfather remain the physical temperature controller while BrewAssistant supplies the recommended fermentation target.

The intended later ownership is:

```text
fermentation_tracking
  owns process observations, target recommendation and readiness

Grainfather Fermenter adapter
  translates an approved BrewAssistant target into Grainfather profile control

GF30 / Grainfather controller
  owns physical heating/cooling regulation
```

The GF30 adapter must use BrewAssistant's generic **Supervised Apply** boundary initially. No direct automatic target writes should be enabled until live readback behavior has been verified.

Direct heater, glycol-pump, compressor or cooling-valve control is **not** inferred from the current cloud integration.

## Relationship to existing chamber backend

`fermentation_chamber/` remains the adapter for the current Home Assistant climate-controlled fermentation chamber.

The GF30 must become an alternative/selectable physical fermentation target provider, not a second controller fighting the chamber backend.

Conceptually:

```text
                    fermentation_tracking
                           |
                    target/recommendation
                           |
              +------------+------------+
              |                         |
 fermentation_chamber            grainfather_fermenter
 climate target bridge           GF30 profile target bridge
```

Only the selected physical target provider may propose a temperature change.

## First live-GF30 validation

When a GF30 is available, verify before enabling control:

1. actual device/entity attributes exposed by `fidley/grainfather_integration`;
2. whether the GF30 appears as `is_controller_linked: true`;
3. linkage behavior when a brew session starts/stops fermentation;
4. temperature polling/update cadence and `last_heard` behavior;
5. whether `adjust_current_step_temperature` changes the GF30 controller target reliably;
6. cloud write-to-readback latency;
7. behavior during ramps, diacetyl rest and cold crash;
8. behavior with Grainfather cooling accessories versus heating-only operation.

After that validation the next implementation step is a registered Supervised Apply executor plus explicit provider selection between the existing chamber and the GF30.

## Current parking point

Phase 1 is intentionally the stopping point until physical hardware is available.

Keep the discovery/normalization scaffold, documentation and regression guards. Do **not** add guessed GF30 entity IDs, model-name heuristics, direct actuator assumptions or automatic target writes while those behaviors cannot be verified against a real controller.

When hardware arrives, resume with live characterization/readback validation first. The detailed milestone sequence is maintained in the roadmap document linked above.
