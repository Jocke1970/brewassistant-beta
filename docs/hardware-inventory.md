# BrewAssistant hardware inventory

This document describes the brewing hardware that BrewAssistant is expected to support or observe in the current beta setup. It is intended as a practical wiring/architecture reference for testing, troubleshooting, and future module boundaries.

Status labels:

- **Active**: currently used or expected in the main BrewAssistant workflow.
- **Available**: owned/available, but not always used in the main workflow.
- **Planned / optional**: discussed as future support or non-critical hardware.
- **Verify**: known from conversation/context, but exact model/entity/role should be confirmed before relying on it in code.

## System overview

```text
Brewfather Brew Tracker
        |
        v
BrewAssistant Beta in Home Assistant
        |
        +-- BrewZilla / RAPT Cloud Link backend
        |       +-- BrewZilla target temperature
        |       +-- heat utilization
        |       +-- pump utilization
        |       +-- heater / pump / power / internal temperature telemetry
        |
        +-- Brewday audit log
        +-- Equipment learning / profile suggestions
        +-- Fermentation / chamber / kegerator modules
```

The current BrewZilla control philosophy is:

- BrewAssistant may set/correct target temperature and utilization values when allowed.
- BrewZilla is trusted to regulate locally once it has a valid target.
- RCL stale/degraded telemetry should trigger diagnostics/refresh, not heater-off behavior.
- Manual/supervised confirmations remain important around mash-in and physical operations.

## Critical hardware matrix

| Area | Hardware | Status | Critical for BrewZilla test | BrewAssistant role | Notes |
|---|---:|---|---:|---|---|
| Hot side | BrewZilla Gen 4 35L | Active | Yes | Primary mash/boil vessel | Controlled/observed through RAPT/RCL-backed HA entities. |
| Hot side | BrewZilla internal controller | Active | Yes | Local regulation authority | BA should not fight local regulation after target is set. |
| Hot side | BrewZilla pump | Active | Yes | Recirculation / thermal mixing | Pump utilization is important during mash thermal-mix conditions. |
| Hot side | BrewZilla heater | Active | Yes | Heat source | Heat utilization is adjusted by BA profiles/guards when allowed. |
| Backend | RAPT Cloud Link / RAPT integration | Active | Yes | BrewZilla telemetry/control path | Stale values are a known risk area; refresh/reload diagnostics matter. |
| Backend | Brewfather Brew Tracker | Active | Yes | Recipe/runtime source | Provides stage, step, target temperature, pause/running state. |
| Platform | Home Assistant | Active | Yes | Runtime platform | Hosts BrewAssistant, RAPT/RCL, Shelly and dashboard. |
| Platform | BrewAssistant Beta | Active | Yes | Orchestration layer | Coordinates Brewfather runtime, BZ control, audit, learning and dashboards. |
| Logging | Brewday audit log | Active | Yes | Test evidence and debugging | Should auto-start from Brewfather Planning when BF+BrewZilla backends exist. |

## Hot-side brewing hardware

### BrewZilla Gen 4 35L

| Property | Value |
|---|---|
| Status | Active |
| Role | Hot-side brewing: heat strike water, mash, mash-out, boil |
| Batch context | Small batches around 8-10 L and larger batches as needed |
| Primary control path | RAPT/RCL entities in Home Assistant |
| BA criticality | High |

Expected BrewAssistant responsibilities:

- Resolve active Brewfather target.
- Apply safe target transitions around strike and mash-in.
- Maintain/adjust heat utilization when positive control is allowed.
- Maintain/adjust pump utilization for circulation/thermal mixing.
- Preserve BrewZilla local regulation when telemetry is stale or runtime is paused.
- Record enough audit context for post-run analysis.

Known or expected entity areas:

| Logical function | Example / expected HA entity |
|---|---|
| BrewZilla main power | `switch.brewzilla` |
| Internal/current temperature | `sensor.brewzilla_temperature` |
| Target temperature | `number.brewzilla_target_temperature` |
| Heat utilization | `number.brewzilla_heat_utilization` |
| Pump utilization | `number.brewzilla_pump_utilization` |
| Heater state | RAPT/RCL-backed switch/sensor, exact entity may vary |
| Pump state | RAPT/RCL-backed switch/sensor, exact entity may vary |
| Power draw | `sensor.brewzilla_power` |

### Malt pipe / mash system

| Property | Value |
|---|---|
| Status | Active / expected |
| Role | Real mash bed in BrewZilla |
| BA criticality | High for realistic learning |
| Notes | Real mash thermal behavior differs from water-only tests. |

Practical impact for BrewAssistant:

- Mash/BLE temperature should generally be preferred for mash control decisions.
- Internal/wort temperature is still important as a safety/overshoot indicator.
- Thermal-mix logic must handle stratification: hot wort/internal while mash lags behind.
- Pump strategy matters for both temperature convergence and mash-bed compaction risk.

### Counterflow chiller

| Property | Value |
|---|---|
| Hardware | Kegland Red Reaper Counter Flow Chiller |
| Status | Active / available |
| Role | Wort chilling after boil |
| BA criticality | Medium |
| Notes | Planned to be mounted on/near the brewing stand rather than placing fermenter directly under BrewZilla. |

Possible future BrewAssistant role:

- Chilling checklist stage.
- Cooling water/wort routing reminders.
- Temperature trend monitoring during transfer/chilling.
- Cleaning/sanitation reminders after use.

## Temperature and gravity sensors

### BrewZilla internal temperature

| Property | Value |
|---|---|
| Status | Active |
| Role | Internal/wort-side temperature from BrewZilla/RAPT |
| BA criticality | High |
| Risk | Can read hotter than mash bed during heating/recirculation. |

Use in BrewAssistant:

- Safety/overshoot guard.
- Thermal-mix detection.
- RCL freshness diagnostics.
- Local regulation context.

### RAPT BLE thermometer

| Property | Value |
|---|---|
| Status | Active / available |
| Role | Mash/liquid temperature reference |
| BA criticality | High for real mash tests |
| Notes | Useful as mash-bed or liquid-side temperature, depending placement. |

Use in BrewAssistant:

- Preferred mash temperature source when available and fresh.
- Used to compare mash temperature against BrewZilla internal/wort temperature.
- Helps distinguish true overshoot from internal/wort stratification.

### RAPT Pill

| Property | Value |
|---|---|
| Status | Active for fermentation |
| Role | Gravity and temperature during fermentation |
| BA criticality for BrewZilla test | Low |
| BA criticality for fermentation | High |
| Notes | Bluetooth mode has been preferred for stability after Wi-Fi dropouts. |

Known or expected entity areas:

| Logical function | Example / expected HA entity |
|---|---|
| Gravity | `sensor.yellow_pill_gravity_2` / `sensor.yellow_pill_specific_gravity` |
| Temperature | `sensor.yellow_pill_temperature` |

Use in BrewAssistant:

- Fermentation monitoring.
- Gravity stability checks.
- Cold crash / packaging readiness.
- Future batch analytics.

## Fermentation hardware

### FermZilla All Rounder 30L

| Property | Value |
|---|---|
| Status | Active / available |
| Role | Main pressure-capable fermenter |
| BA criticality | High for fermentation module |
| Notes | Used with heat mat/chamber/spunding depending process. |

Possible BrewAssistant responsibilities:

- Fermentation schedule tracking.
- Temperature target recommendations.
- Spunding/pressure checklist prompts.
- Cold crash readiness.
- Packaging checklist.

### Oxebar 8L

| Property | Value |
|---|---|
| Status | Available |
| Role | Small-batch fermentation / serving vessel |
| BA criticality | Medium |
| Notes | Useful target for 6-8 L minibatches. |

### PET carboy 11.5L

| Property | Value |
|---|---|
| Status | Available |
| Role | Small-batch fermenter |
| BA criticality | Medium |
| Notes | Useful for 8-10 L BrewZilla batches. |

### Cornelius keg, 9L

| Property | Value |
|---|---|
| Status | Active / available |
| Role | Serving keg and possible pressure fermenter |
| BA criticality | Medium |
| Notes | Useful for small batch fermentation and packaging workflows. |

### Spunding valve

| Property | Value |
|---|---|
| Status | Available |
| Role | Pressure fermentation / natural carbonation control |
| BA criticality | Medium |
| Notes | Can be included in supervised fermentation checklists. |

### Fermentation heat mat

| Property | Value |
|---|---|
| Status | Active |
| Role | Heating source for fermentation chamber/fermenter |
| BA criticality | High for fermentation module |

Known or expected entities:

| Logical function | Example / expected HA entity |
|---|---|
| Heat mat switch | `switch.fermentation_heat_mat` |
| Heat mat power | `sensor.fermentation_heat_mat_power` |

## Fermentation chamber and kegerator

### Electrolux fridge / kegerator / fermentation chamber

| Property | Value |
|---|---|
| Status | Active |
| Role | Cold chamber for serving, fermentation control and cold crash |
| BA criticality | High for chamber/kegerator/fermentation modules |

Known or expected entities:

| Logical function | Example / expected HA entity |
|---|---|
| Kegerator climate | `climate.kegerator_kylskap` |
| Fermentation chamber climate | `climate.fermentation_chamber` |
| Fridge/chamber temperature | `sensor.kyl_temperatur_4` |
| Kegerator main switch | `switch.kegerator` |
| Kegerator fan | `switch.kegerator_fan` |
| Kegerator power | `sensor.brewassistant_kegerator_power_w` |
| Compressor active | `binary_sensor.kegerator_compressor_active` |

Typical use cases:

- Fermentation temperature control.
- Diacetyl rest.
- Cold crash to approximately 1-2 C.
- Serving/kegerator monitoring.
- Compressor/power health diagnostics.

## Serving and packaging hardware

### iTapX bottle filler

| Property | Value |
|---|---|
| Status | Active / available |
| Role | Counter-pressure bottle filling from keg |
| BA criticality | Medium |
| Notes | Used after keg carbonation/conditioning. |

### CO2 system

| Property | Value |
|---|---|
| Status | Active / available |
| Role | Kegging, serving, transfers and bottle filling |
| BA criticality | Medium |

Known/mentioned components:

- CO2 regulator.
- Ball locks.
- EVABarrier tubing.
- Duotight fittings/couplers.
- Keg accessories such as dip tubes and float dip tubes.

Future BrewAssistant role:

- Packaging checklist.
- Carbonation reminders.
- Closed transfer checklist.
- Bottle filling checklist.

## Power monitoring and smart plugs

### Shelly devices

| Property | Value |
|---|---|
| Status | Active |
| Role | Power switching and power telemetry |
| BA criticality | Medium to high, depending controlled device |

Known use areas:

- Kegerator/fridge power monitoring.
- Fan switching.
- Compressor activity inference.
- Potential BrewZilla or other appliance monitoring.

Design note:

Shelly telemetry is useful for health/diagnostics, but BrewAssistant should not infer too much from a stale Shelly value without freshness checks.

## Backend and integration dependencies

| Backend / integration | Status | Used for | Criticality |
|---|---|---|---|
| Home Assistant | Active | Runtime platform | High |
| BrewAssistant Beta | Active | Orchestration/dashboard/audit/learning | High |
| Brewfather Brew Tracker | Active | Recipe runtime, target, stage, pause/running | High |
| RAPT Cloud Link / RAPT HA integration | Active | BrewZilla control and telemetry | High |
| Shelly integration | Active | Switch/power telemetry | Medium |
| HACS/custom cards | Active | Dashboard UX | Medium |

## BrewAssistant module mapping

| Module | Hardware dependencies | Optional dependencies | Notes |
|---|---|---|---|
| BrewZilla / hot-side backend | BrewZilla, RAPT/RCL, Brewfather | RAPT BLE thermometer, power sensor | Primary current beta focus. |
| Brewday audit | Brewfather, BrewZilla backend | Dashboard card | Should auto-start when BF enters Planning and both BF+BZ backends exist. |
| Equipment learning | BrewZilla telemetry, target, heat/pump utilization | Mash/BLE temp, grain/volume context | Observes first; suggestions require later operator application. |
| Fermentation | Fermenter, chamber/fridge, heat mat, Pill | Spunding valve | Separate from hot-side control. |
| Chamber/kegerator | Fridge/kegerator, fan, power sensor | Compressor binary sensor | Used for serving and cold crash. |
| Packaging | Keg, CO2, iTapX | QR/labels | Checklist-oriented. |

## Hardware criticality for first real BrewZilla batch

### Required

- BrewZilla Gen 4 35L.
- BrewZilla/RAPT telemetry and control entities.
- Brewfather Brew Tracker runtime.
- BrewAssistant hot-side backend.
- Brewday audit log.
- Reliable mash temperature source or clear understanding of which temperature source is authoritative.
- Physical abort path/operator supervision.

### Strongly recommended

- RAPT BLE thermometer for mash/liquid temperature.
- Power telemetry for BrewZilla.
- Dashboard showing current step, target, mash/internal temperatures, heat/pump utilization and audit status.
- Manual override / fallback plan for direct BrewZilla control.

### Not required for hot-side test

- RAPT Pill gravity.
- Fermentation chamber automation.
- Spunding valve.
- iTapX.
- Kegerator serving hardware.

These are important for the full brewing workflow, but not required to validate BrewZilla mash/ramp behavior.

## Current known risk areas

| Risk | Affected hardware/backend | Impact | Mitigation |
|---|---|---|---|
| RAPT/RCL telemetry stale values | RAPT/RCL, BrewZilla entities | BA may see old values while BrewZilla continues locally | Treat stale as diagnostics/refresh, not as reason to heater-off. |
| Internal/wort hotter than mash | BrewZilla internal sensor vs mash/BLE sensor | Thermal-mix false overshoot risk | Prefer mash/BLE for mash target; use internal/wort as safety limiter. |
| Short test steps exaggerate lag | Brewfather test recipe | UI may look worse than real batch behavior | Use longer 30/10/10 min mash test for realistic thermal response. |
| Pump too low during hot-wort mix | BrewZilla pump | Slower stratification recovery | Use higher pump in hot-wort thermal-mix cases, with mash-bed caution. |
| Missing manual override | BrewAssistant/BrewZilla | Harder to take temporary manual control | Add explicit manual override layer before fully unattended behavior. |

## Verification checklist after hardware or entity changes

```text
1. Confirm Brewfather runtime sensors exist and update.
2. Confirm BrewZilla target temperature entity exists and can be read.
3. Confirm BrewZilla internal/current temperature updates.
4. Confirm heat utilization entity exists and updates.
5. Confirm pump utilization entity exists and updates.
6. Confirm heater/pump/main power states are readable.
7. Confirm power telemetry updates while heating.
8. Confirm mash/BLE temperature source is selected and fresh.
9. Confirm brewday audit starts and records events.
10. Confirm abort stops heater/pump and sets utilization to safe values.
```

## Open items to verify

- Exact BrewZilla RAPT/RCL entity names for heater state and pump state.
- Exact preferred mash temperature entity when RAPT BLE thermometer is used.
- Whether BrewZilla power is always available as `sensor.brewzilla_power` in the production setup.
- Whether kegerator and fermentation chamber remain the same physical fridge or should be documented as separate current deployments.
- Exact tubing/fitting inventory for closed transfer and packaging.
- Exact Brother label printer / QR-label workflow if it becomes part of packaging docs.

## Maintenance notes

Update this document when:

- A hardware item becomes the official supported path instead of optional.
- HA entity names change.
- A backend becomes optional/required for a feature gate.
- First real BrewZilla batch confirms or invalidates test assumptions.
- Manual override or additional dashboard hardware controls are added.
