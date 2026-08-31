# BrewAssistant Cooling Backend Roadmap

Status: architecture fixed / implementation pending  
Last updated: 2026-08-31

This document defines the intended architecture, ownership boundaries and implementation roadmap for BrewAssistant wort cooling.

The backend is deliberately **Cooling-centric**, not CFC-centric. It must support counterflow chillers, immersion chillers and fully manual cooling while exposing one common cooling runtime and advice model.

## Fixed architecture decisions

The following decisions are fixed unless explicitly revisited:

- Cooling is a separate backend domain under `custom_components/brewassistant/cooling`.
- The backend supports at least:
  - `counterflow_chiller`
  - `immersion_chiller`
  - `manual`
- Cooling target is BrewAssistant-owned and independent of BrewZilla mash/boil target.
- Cooling target range is **8–30 °C**, step **1 °C**.
- Preferred entity: `number.brewassistant_cooling_target_temperature`.
- BrewZilla wort-pump control during cooling is **operator-owned/manual**.
- Cooling may read BrewZilla pump state and provide advice, but must not start, stop or regulate the BrewZilla wort pump.
- Cooling-water actuation is optional. A configured HA switch, such as a Shelly-powered pump, may be controlled by Cooling; direct/manual tap water must also be supported.
- Sanitation applies to both **counterflow chiller** and **immersion chiller** workflows.
- Default sanitation window is **15 minutes before boil completion**.
- Cooling water must remain OFF during sanitation when Cooling owns a cooling-water actuator.
- For CFC operation, the external process sensor such as the RAPT BLE Thermometer becomes the CFC wort-out temperature sensor when BOIL starts.
- `brewday_runtime` releases that extra process sensor at BOIL start; Cooling owns/interprets it from that point through Chill/Transfer.
- For immersion chilling with BrewZilla, current wort temperature comes from BrewZilla's internal temperature sensor.
- For fully manual brewing/cooling, current wort temperature may be entered manually.
- BrewZilla internal temperature must not silently substitute for CFC outlet temperature during active CFC cooling.
- Cooling target must not silently fall back to BrewZilla target temperature.
- Existing cooling rate, delta, ETA and target-ready calculations should be reused/refactored rather than discarded.

## Scope and ownership

Cooling owns:

- cooling runtime/state machine
- selected cooling method
- sanitation lifecycle
- cooling target
- cooling temperature-source resolution
- trend/rate/ETA/advice calculations
- optional cooling-water switch control
- cooling readiness and transfer-temperature readiness
- BLE/CFC outlet interpretation after BOIL handover

Cooling does not own:

- BrewZilla heater control
- BrewZilla wort-pump control
- BrewZilla pump-utilization control
- mash/boil target temperature
- brewday stage progression itself

## Cooling methods

| Method | Process temperature | Wort pump | Cooling-water control | Sanitation |
| --- | --- | --- | --- | --- |
| Counterflow chiller | External outlet sensor / BLE | Manual/operator-owned | Optional HA switch or manual tap | Required |
| Immersion chiller | BrewZilla internal temp, or manual temp in manual brewing | Not required by Cooling | Optional HA switch or manual tap | Required |
| Manual cooling | Manual temperature input | Not required by Cooling | Manual/no actuator | Method-dependent; default no automatic sanitation requirement unless an immersion/CFC device is selected |

The runtime should model hardware capabilities explicitly rather than assuming that every cooling setup has a pump or external sensor.

Suggested capabilities:

```text
cooling_method:
  counterflow_chiller
  immersion_chiller
  manual

cooling_water_control:
  none
  switch

process_temperature_source:
  cfc_outlet_sensor
  brewzilla_internal
  manual_input
```

## Runtime state machine

Core states:

```text
IDLE
PREPARE
SANITIZE
READY
CHILLING
TRANSFER
COMPLETE
```

### CFC path

```text
IDLE
  -> PREPARE          when BOIL starts
  -> SANITIZE         when boil_remaining <= sanitize_minutes
  -> READY            when sanitation is complete
  -> CHILLING         when brewday enters Chill
  -> TRANSFER         when transfer begins
  -> COMPLETE         when transfer/cooling is complete
  -> IDLE             on reset/new session
```

During CFC sanitation:

- user is instructed to circulate hot wort through the CFC
- BrewZilla wort pump remains manual
- cooling-water actuator, if configured, is forced/required OFF
- external outlet sensor may be used as evidence that hot wort is reaching the CFC

### Immersion-chiller path

```text
IDLE
  -> PREPARE          when BOIL starts
  -> SANITIZE         when boil_remaining <= sanitize_minutes
  -> READY            when sanitation is complete
  -> CHILLING         when brewday enters Chill
  -> TRANSFER         when transfer begins
  -> COMPLETE         when transfer/cooling is complete
  -> IDLE             on reset/new session
```

The immersion chiller therefore uses the same sanitation lifecycle as the CFC. The difference is temperature sensing and actuator requirements, not sanitation.

During immersion sanitation:

- the coil is expected to be immersed in hot/boiling wort for sanitation
- no wort-pump requirement is introduced by Cooling
- cooling water remains OFF until CHILLING begins

### Manual path

Manual cooling may enter CHILLING without CFC-specific equipment requirements. Temperature can be supplied by a BrewAssistant manual input when no integrated process sensor is available.

## Sanitation contract

Default:

```text
sanitize_minutes = 15
```

The existing 10–25 minute configurable range may be retained initially unless later testing shows a better contract.

Runtime fields should reserve support for:

```text
sanitize_required
sanitize_elapsed_minutes
sanitize_temperature
sanitize_temperature_ok
sanitize_complete
sanitation_incomplete
```

Sanitation completion must not be inferred merely because BOIL ended. If the configured minimum sanitation time has not been achieved, runtime must expose that explicitly.

For CFC sanitation, hot-wort circulation is a manual operator action. For immersion sanitation, physical immersion in boiling/hot wort is the sanitation mechanism.

## Cooling target

Preferred entity:

```text
number.brewassistant_cooling_target_temperature
```

Contract:

```text
min: 8 °C
max: 30 °C
step: 1 °C
unit: °C
```

No fallback to BrewZilla target temperature is allowed.

If no cooling target exists:

```text
status = no_target
```

A future Brewfather/runtime adapter may suggest or set the cooling target, but the Cooling backend remains the owner of the active cooling setpoint.

## Temperature-source resolution

### Counterflow chiller

Primary process temperature:

```text
CFC wort-out temperature = configured external sensor / RAPT BLE Thermometer
```

BrewZilla internal temperature remains informational kettle temperature only.

If the outlet sensor is unavailable during active CFC cooling:

```text
status = no_outlet_temperature
```

Automatic cooling-water control must be inhibited if the required process sensor is unavailable.

### Immersion chiller

Preferred process temperature:

```text
BrewZilla internal temperature
```

If the brew is fully manual or no integrated kettle temperature is available, use a BrewAssistant manual cooling-temperature input.

Suggested entity:

```text
number.brewassistant_cooling_manual_temperature
```

### Manual cooling

Use the manual temperature input as `current_wort_temperature`.

## Cooling Advice v2

Refactor/reuse the useful logic currently in `wort_cooling.py`:

- current/reference temperature
- target temperature
- delta
- cooling rate
- ETA
- trend samples
- target-ready calculation

Initial target-ready tolerance remains:

```text
±1.0 °C
```

Suggested advice/status vocabulary:

```text
standby
prepare
sanitize_required
sanitizing
ready
no_target
no_process_temperature
no_outlet_temperature
wort_pump_required
cooling_needed
cooling
approaching_target
on_target
below_target
cooling_ineffective
overshoot_risk
transfer_ready
```

Advice must distinguish between actions Cooling can perform and actions the operator must perform.

Examples:

```text
CFC + wort pump OFF:
"Start wort circulation through CFC."

Immersion + above target:
"Cooling active. Continue cooling water flow."

Near target:
"Approaching target. Monitor cooling to avoid overshoot."
```

## Cooling-water control

Cooling-water control is an optional capability.

Supported modes:

```text
none   = manual tap / no HA actuator
switch = configured HA switch, e.g. Shelly-powered pump
```

When `switch` is configured, Cooling may control it during CHILLING.

Minimum safety behavior:

- OFF outside CHILLING unless a later explicit transfer-cooling policy requires otherwise
- OFF during PREPARE/SANITIZE/READY
- fail-safe OFF when required process temperature is unavailable
- avoid rapid switching

Initial control strategy may be simple hysteresis around target. Later refinement may use:

- minimum ON/OFF time
- temperature trend
- predicted overshoot
- ineffective-cooling detection

## BrewZilla wort-pump boundary

Cooling may read:

```text
switch.brewzilla_pump
number.brewzilla_pump_utilization
```

Cooling must not write:

```text
switch.brewzilla_pump
number.brewzilla_pump_utilization
```

Existing CFC code that starts the BrewZilla pump or sets pump utilization must be removed/refactored.

For CFC workflows, pump state can still be used as a guard/advice input:

```text
wort_pump_required = true
wort_pump_state = off
advice = "Start BrewZilla pump to circulate wort through CFC."
```

## Proposed code structure

```text
custom_components/brewassistant/cooling/
├── __init__.py
├── cooling_runtime.py
├── cooling_advice.py
├── cooling_control.py
├── cooling_sensor.py
└── counterflow_chiller.py
```

Responsibilities:

- `cooling_runtime.py`: state machine, method/capability resolution, sanitation lifecycle, sensor ownership
- `cooling_advice.py`: delta, trend, rate, ETA, target-ready and operator advice
- `cooling_control.py`: optional cooling-water actuator only
- `cooling_sensor.py`: Home Assistant presentation/entities
- `counterflow_chiller.py`: CFC-specific adapter/configuration only, not the overall runtime engine

An immersion-specific adapter may be added later if enough method-specific behavior accumulates; do not create one merely for symmetry.

## Existing-code migration map

| Existing behavior/code | Action |
| --- | --- |
| `cooling/counterflow_chiller.py` runtime/control | Rewrite heavily |
| `cooling/wort_cooling_sensor.py` | Keep and adapt |
| root `wort_cooling.py` calculations | Refactor/move into `cooling_advice.py` |
| sanitize minutes | Keep |
| CFC pump utilization setting | Remove |
| BrewZilla pump writes | Remove |
| cooling delta | Keep |
| cooling rate | Keep |
| ETA | Keep |
| pitch-ready logic | Keep concept; generalize toward target/transfer readiness |
| ±1 °C tolerance | Keep initially |
| arbitrary output-sensor fallback chain | Replace with method-aware source resolution |
| kettle-temp fallback during CFC | Remove |
| BrewZilla-target fallback | Remove |
| optional cooling-water switch | Add |
| immersion-chiller strategy | Add |
| manual cooling temperature | Add |
| Cooling runtime state machine | Add |

## Home Assistant entity contract

Initial desired entities/capabilities include:

```text
number.brewassistant_cooling_target_temperature
number.brewassistant_cooling_manual_temperature

sensor.brewassistant_cooling_state
sensor.brewassistant_cooling_status
sensor.brewassistant_cooling_advice
sensor.brewassistant_cooling_process_temperature
sensor.brewassistant_cooling_target_temperature
sensor.brewassistant_cooling_delta
sensor.brewassistant_cooling_rate
sensor.brewassistant_cooling_eta_minutes
binary_sensor.brewassistant_cooling_target_ready
binary_sensor.brewassistant_cooling_sanitized
```

Exact entity naming should be checked against current BrewAssistant naming conventions before implementation. Avoid creating duplicate readback entities when attributes or existing sensors already serve the purpose cleanly.

Method/configuration entities for cooling method, external sensor and cooling-water switch must be designed before implementation rather than hard-coded to current hardware.

## Implementation phases

### Phase 1 — Runtime contract and method model

- add method/capability model
- implement common state machine
- implement BOIL handover
- implement CFC and immersion sanitation paths
- preserve manual brewing path

### Phase 2 — Temperature and target model

- add 8–30 °C / 1 °C cooling target
- add method-aware temperature-source resolver
- add manual temperature input
- remove BrewZilla-target fallback
- inhibit unsafe automatic control on missing required sensor

### Phase 3 — Cooling Advice v2

- migrate existing trend/delta/rate/ETA logic
- generalize `pitch_ready` toward target/transfer readiness
- add approach/overshoot/ineffective-cooling advice
- add method-aware operator prompts

### Phase 4 — Optional cooling-water control

- configurable HA switch capability
- sanitation/standby fail-safe OFF
- initial hysteresis control
- minimum switch timing
- sensor-loss fail-safe

### Phase 5 — Legacy cleanup

Only after v2 runtime is verified:

- remove CFC pump-utilization control
- remove direct BrewZilla-pump writes from Cooling
- retire obsolete cooling target helpers/fallbacks
- consolidate old `wort_cooling.py` interfaces

### Phase 6 — Dashboard and field test

- expose runtime state, advice, target and temperature-source diagnostics
- simulate all methods without hardware writes first
- test CFC with BLE outlet sensor
- test immersion chiller with BrewZilla internal temperature
- test manual temperature path
- test both HA-controlled cooling water and manual tap water

## Acceptance checklist

Before Cooling v2 is considered ready:

- [ ] CFC and immersion both enter sanitation before active chilling.
- [ ] Sanitation defaults to 15 minutes before BOIL completion.
- [ ] Cooling water cannot be automatically active during sanitation.
- [ ] CFC never starts/stops/regulates the BrewZilla wort pump.
- [ ] CFC uses the configured outlet sensor as process temperature.
- [ ] Immersion uses BrewZilla internal temperature when available.
- [ ] Manual cooling can use operator-entered temperature.
- [ ] Target is constrained to 8–30 °C in 1 °C steps.
- [ ] Cooling target never falls back to BrewZilla target.
- [ ] Missing CFC outlet sensor blocks automatic cooling-water control safely.
- [ ] Manual tap-water cooling works without a configured HA switch.
- [ ] Optional Shelly/switch cooling-water control fails safe.
- [ ] Delta, rate, ETA and target-ready calculations remain available.
- [ ] Transfer readiness is based on the correct method-specific process temperature.
- [ ] Runtime reset releases Cooling sensor ownership cleanly.

## Do not change casually

The following boundaries are intentional and should be treated as architecture, not implementation convenience:

1. BrewZilla wort pump is operator-owned during Cooling.
2. Cooling-water actuation is optional.
3. CFC outlet temperature and kettle temperature are not interchangeable.
4. Immersion chilling uses kettle temperature, not a fake CFC outlet abstraction.
5. Both CFC and immersion chillers require sanitation before active cooling.
6. Cooling target is independent of BrewZilla target.
7. Manual brewing/cooling must remain a first-class supported path.
