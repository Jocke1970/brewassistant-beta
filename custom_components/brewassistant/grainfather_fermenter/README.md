# Grainfather Fermenter backend

Status: phase 1 scaffold / read-only discovery / parked until live hardware  
Initial hardware target: Grainfather GF30 Conical Fermenter  
Upstream Home Assistant integration: `fidley/grainfather_integration`

This package is a fermentation-control provider scaffold. It is intentionally separate from BrewAssistant's reserved `grainfather` hot-side adapter, which remains reserved for Grainfather brewing systems such as G30/G40-class hardware.

The common fermentation provider contract is documented in [`../../../docs/backends/fermentation-control.md`](../../../docs/backends/fermentation-control.md).

## Phase 1 goal

Prepare the BrewAssistant side before a physical GF30 is available, without inventing entity ids, model identity or control behavior.

The backend currently:

- discovers Grainfather fermentation-device states by the upstream public `grainfather_entity_type` attribute;
- groups temperature and gravity telemetry by Grainfather `device_id`;
- reads controller linkage, linked brew session and `last_heard` metadata;
- matches the selected device to the Grainfather brew-session anchor;
- detects whether `grainfather.adjust_current_step_temperature` exists;
- reports whether the future supervised target bridge has enough visible prerequisites;
- performs **no service calls** and remains fail-passive/read-only.

It is not yet registered as a writable provider and does not compete with `fermentation_chamber`.

## Why no hard-coded entity ids

The upstream integration creates fermentation devices dynamically and their names depend on the user's Grainfather account and configured devices. BrewAssistant therefore discovers them from stable upstream attributes instead of assuming an entity such as:

```text
sensor.grainfather_gf30_temperature
```

Current upstream fermentation-device attributes observed during integration research include:

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

## Device-selection boundary

Current upstream Home Assistant attributes identify fermentation devices and whether a controller is linked, but do not expose a field that proves the selected device is specifically a GF30.

Until real hardware is available BrewAssistant therefore uses this conservative discovery rule:

```text
exactly one controller-linked device -> safe discovery candidate
multiple controller-linked devices    -> ambiguous; select nothing
single unverified device              -> telemetry-only candidate
multiple unverified devices           -> select nothing
```

The snapshot explicitly reports:

```text
model_verified: false
```

A friendly name containing `GF30` is not considered sufficient proof.

## Fermentation-provider role

This package follows the same control boundary as the current chamber provider:

```text
fermentation_tracking
  recommended beer/liquid target
        |
        v
grainfather_fermenter
  provider translation / validation
        |
        v
Supervised Apply (future)
        |
        v
Grainfather fermentation target/profile step
        |
        v
Grainfather controller
  owns actual heat/cool cycling
```

BrewAssistant should own fermentation intent and target selection. The Grainfather controller should own heater/cooling demand, hysteresis and local actuator switching when live validation confirms that behavior.

The adapter must not add direct Cooling Pump Kit, heater, compressor, glycol-pump or cooling-valve control merely because those actuators exist.

## Relationship to fermentation chamber

`fermentation_chamber/` is the currently implemented physical fermentation provider and translates the beer target into a chamber-air target for `climate.fermentation_chamber`.

A future Grainfather provider becomes an **alternative** physical provider, not a second controller operating in parallel.

Before Grainfather target writes can be enabled, executable provider selection/authority must ensure that only one provider can create a target-write action for a fermentation session.

## Future target bridge

Integration research found this upstream service:

```text
grainfather.adjust_current_step_temperature
```

It is a promising future bridge because it can allow BrewAssistant to set the approved fermentation target while leaving physical regulation to Grainfather.

Phase 1 merely detects whether the service exists. It never calls it.

The future write path must begin behind BrewAssistant's generic **Supervised Apply** boundary. A registered executor should perform the external service call only after explicit confirmation and only after live hardware readback has been verified.

## Snapshot status values

The read-only snapshot may report:

```text
integration_missing
awaiting_fermentation_device
ambiguous_device
awaiting_device_selection
ready_read_only
controller_unlinked
ready_supervised_candidate
```

`ready_supervised_candidate` does **not** mean writes are enabled. It only means the currently visible upstream state contains the prerequisites we expect to need later.

## First live-GF30 validation

When physical hardware is available, verify before enabling control:

1. actual device/entities/attributes exposed by `fidley/grainfather_integration`;
2. whether the GF30 appears as `is_controller_linked: true`;
3. linkage behavior when a brew session enters/leaves fermentation;
4. temperature polling/update cadence and `last_heard` behavior;
5. whether `adjust_current_step_temperature` changes the GF30 controller target reliably;
6. target write-to-readback latency and cloud failure behavior;
7. whether the GF30 controller itself owns heating and Cooling Pump Kit demand;
8. behavior during ramps, diacetyl rest and cold crash;
9. behavior with Cooling Pump Kit versus any later glycol setup.

After that validation:

```text
read-only provider
  -> explicit provider selection
  -> registered Supervised Apply executor
  -> controlled field tests
  -> only then consider any automatic target transitions
```

## Do not change casually

1. Keep this package separate from the reserved Grainfather hot-side adapter.
2. Do not infer GF30 model identity from a friendly name.
3. Phase 1 remains read-only and must not call Grainfather services.
4. `fermentation_tracking` remains hardware-agnostic and owns observations/readiness.
5. Only one physical fermentation provider may have target-write authority at a time.
6. Prefer downstream setpoint control over raw actuator control when the Grainfather controller already owns local regulation.
