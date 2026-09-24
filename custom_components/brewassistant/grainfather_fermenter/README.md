# Grainfather Fermenter backend

Status: active read-only GF30 backend foundation / no actuator control  
Initial hardware target: Grainfather GF30 Conical Fermenter  
Upstream Home Assistant integration: `fidley/grainfather_integration`

This package is intentionally separate from BrewAssistant's reserved `grainfather` hot-side adapter. The existing `grainfather` module remains available for Grainfather brewing systems such as G30/G40-class hardware. This package is for fermentation hardware.

Longer architecture/roadmap: [`../../../docs/backends/grainfather-fermenter.md`](../../../docs/backends/grainfather-fermenter.md)  
DIY cooling/learning contract: [`../../../docs/backends/gf30-thermal-control-learning.md`](../../../docs/backends/gf30-thermal-control-learning.md)

## Ownership boundary

`fermentation_tracking` owns the fermentation process: SG/day progression, readiness and the desired beer-temperature target.

`grainfather_fermenter` owns GF30-specific hardware adaptation and thermal diagnostics. It may later translate an approved BrewAssistant target to the GF30 controller, but it does not decide fermentation progression itself.

The intended split is:

```text
fermentation_tracking
  -> desired beer temperature / process state
             |
             v
grainfather_fermenter
  -> GF30 telemetry / thermal diagnostics / future supervised target bridge
             |
             v
GF30 controller
  -> local heater and automatic cooling-pump logic

separate coolant loop:
HA generic_thermostat -> freezer -> coolant reservoir
```

## Implemented now

### Grainfather cloud discovery

The backend:

- discovers Grainfather fermentation-device states by the upstream public `grainfather_entity_type` attribute;
- groups temperature and gravity telemetry by Grainfather `device_id`;
- reads controller linkage, linked brew session and `last_heard` metadata;
- matches the device to the Grainfather brew-session anchor;
- detects whether `grainfather.adjust_current_step_temperature` exists;
- reports whether a future supervised target bridge has enough prerequisites;
- performs **no service calls** and remains fail-passive/read-only.

### Thermal preflight before GF30 Wi-Fi is available

`thermal.py` contains a pure read-only comparison engine for the first physical tests where only:

- RAPT Pill temperature; and
- a manually entered reference temperature

are available.

`build_manual_preflight_snapshot()` records both values and timestamps, rejects missing/stale/implausible observations, calculates Pill-minus-manual delta and exposes whether the pair is eligible as one learning sample.

Important invariants:

- both observations participate in the comparison;
- disagreement never silently selects one sensor as the winner;
- the manual reference is not converted into an actuator source;
- the result always exposes `control_allowed: false`;
- no Home Assistant service call, pump command, freezer command or Grainfather write exists in this path.

The initial diagnostic defaults are 15 minutes maximum observation age and 0.5 °C agreement tolerance. They are explicit function parameters, not physical safety limits or calibration claims.


### Persistent preflight runtime and HA sensors

The first physical cooling test can be recorded directly in Home Assistant.

Implemented services:

```text
brewassistant.gf30_record_manual_temperature
brewassistant.gf30_clear_preflight
```

Each manual observation stores the manual temperature and timestamp plus the current configured Pill temperature and Home Assistant `last_updated` timestamp. Up to 200 observations are persisted through Home Assistant `Store`. An optional free-text phase such as `baseline`, `cooling`, `recovery` or `cold_crash` can be attached.

Implemented read-only sensors include backend/cloud status, Grainfather-controller temperature candidate, preflight status, Pill/manual temperatures, delta, sample counts, passive cooling-rate metrics, dual-sensor status and `gf30_safe_point`.

The preflight learning layer can calculate observed Pill °C/h between recorded checkpoints and basic delta statistics. It does **not** calculate a control correction or send any command.

### Dual Pill + GF30 safe-point

`build_dual_sensor_snapshot()` is ready for the moment the Grainfather integration exposes the controller temperature. It independently checks freshness for Pill and controller temperature and reports:

```text
dual_sensor_agree
dual_sensor_disagree
pill_only
internal_only
no_fresh_temperature
```

The safe-point becomes `dual_fresh_agree` only when both observations are fresh and within the current diagnostic tolerance. This is a diagnostic safe-point, not permission to actuate hardware and not an automatic source-selection rule.

### Coolant/freezer contract prepared

`coolant.py` contains a pure read-only contract for coolant temperature, freezer-air temperature and `generic_thermostat` telemetry. It explicitly keeps `generic_thermostat` as freezer owner and refuses to claim a safe coolant setpoint before medium/freeze limits are physically verified.

### Optional coolant entity mapping

BrewAssistant options now expose three deliberately blank mappings:

```text
gf30_coolant_temp_entity
gf30_freezer_air_temp_entity
gf30_coolant_thermostat_entity
```

Leaving them blank is valid. When real sensors exist, selecting those entities automatically enables the read-only coolant diagnostics; no guessed entity IDs are embedded in the backend. The coolant snapshot uses source `last_updated` for freshness and reads the thermostat's target temperature / `hvac_action` only as telemetry.

### First cooling-test workflow

Before the first water/cooling run, clear old test observations with:

```text
brewassistant.gf30_clear_preflight
```

At each manual checkpoint call:

```yaml
action: brewassistant.gf30_record_manual_temperature
data:
  temperature_c: 18.6
  phase: cooling
  note: Manual probe in representative liquid position
```

`observed_at` may be omitted when the measurement is entered immediately. The service captures the configured RAPT Pill state and its HA update time at the same checkpoint. Suggested phase labels for the first characterization are `baseline`, `cooling` and `recovery`.

The service refreshes GF30 diagnostic sensors immediately after recording. The stored series is intended for characterization, not automatic calibration or control.

## Why no hard-coded GF30 entity IDs

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

The current backend never sends a Grainfather command.

The upstream integration exposes a service that can set the temperature of the active Grainfather fermentation step:

```text
grainfather.adjust_current_step_temperature
```

That remains a promising future supervised bridge. The GF30 controller itself owns its local heater and automatic cooling-pump behavior. BrewAssistant must not create a parallel pump-control path.

The DIY coolant/freezer path is separate: Home Assistant `generic_thermostat` is intended to own freezer on/off using the coolant temperature sensor once the hardware exists and has been validated. The thermal-learning layer must not bypass that thermostat.

## Relationship to existing chamber backend

`fermentation_chamber/` remains the adapter for the existing Home Assistant climate-controlled fermentation chamber.

The GF30 is an alternative/selectable physical fermentation target provider, not a second controller fighting the chamber backend.

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

Only the selected physical provider may propose a temperature-target change.

## First physical test before Wi-Fi control

The first useful test can run without Grainfather cloud/controller access:

1. fill the GF30 with the chosen test load and allow temperatures to settle;
2. record the RAPT Pill temperature with its observation time;
3. take a manual reference measurement and record its time;
4. compare the pair through the thermal preflight engine;
5. repeat during cooling so later learning can see delta and response over time;
6. do not infer GF30 internal-sensor behavior until that sensor actually becomes available in Home Assistant.

This is measurement/characterization only. It does not validate the future GF30 controller target bridge, pump behavior, coolant thermostat or freezer fail-safe.

## Live-GF30 validation after Wi-Fi arrives

Before enabling any target write, verify:

1. actual device/entity attributes exposed by `fidley/grainfather_integration`;
2. whether the GF30 appears as `is_controller_linked: true`;
3. the real internal temperature entity and timestamp/freshness behavior;
4. linkage behavior when a brew session starts/stops fermentation;
5. whether `adjust_current_step_temperature` changes the GF30 controller target reliably;
6. cloud write-to-readback latency;
7. GF30 automatic cooling-pump behavior;
8. behavior during ramps, diacetyl rest and cold crash;
9. interaction with the separate coolant/freezer thermostat.

After that validation the next implementation step is the selected-provider/supervised target bridge plus read-only coolant learning.

## Do not change casually

1. Keep GF30 fermenter support separate from the reserved Grainfather hot-side adapter.
2. `fermentation_tracking` owns fermentation progression and desired beer temperature.
3. GF30's local controller owns its heater and automatic cooling-pump logic.
4. Freezer control belongs to the separate coolant `generic_thermostat`, not direct thermal-learning commands.
5. Pill and GF30 internal temperature are complementary observations; disagreement is surfaced, not silently resolved.
6. No physical control is considered verified until real entity/readback/failure behavior has been field-tested.
