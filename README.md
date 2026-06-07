# BrewAssistant v0.2.0-beta.1

**BrewAssistant v0.2.0-beta.1** is a modular Home Assistant brewing assistant for supervised Brewday runtime intelligence, BrewZilla/RAPT hardware control/visualization, counterflow wort cooling, carbonation guidance, dynamic serving/climate supervision, kegerator fan circulation, fermentation tracking, dashboards and notifications.

The project has moved away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations and hardware orchestration live in `custom_components/brewassistant/`.

```text
Python custom integration = logic, normalization, stage engine, calculations, control decisions
YAML/dashboard             = presentation and explicit operator actions
Legacy local packages      = local compatibility/cleanup only, not mainline repo setup
```

---

## Current status

```text
v0.2.0-beta.1
Supervised BrewZilla Brewday Beta
```

Validated in the active beta branch:

```text
✅ Brewfather RAW Brew Tracker runtime resolver
✅ Python Manual Brewday runtime and services
✅ Normalized Brewday Runtime selects Brewfather or Manual Brewday source
✅ Human-friendly Brew Tracker step labels
✅ Paused Brewfather freeze-state handling
✅ BrewZilla runtime sensors
✅ BrewZilla target sync from normalized Brewday Runtime
✅ BrewZilla Orchestration bridge for Manual Brewday target
✅ BrewZilla heater/pump direct actions
✅ ABORT service for heater + pump
✅ Brewday audit backend, services, sensors and dashboard
✅ Smart Brewfather refresh policy
✅ Low-temperature BrewZilla water test: 30 → 35 → 40 → 45 → 50 → 55°C
✅ Dry-run mash profile target validation: 45 → 55 → 65 → 72 → 78°C
✅ Reality-style BrewZilla/Brewfather test with malt/water flow
✅ Boil target fallback to 100°C when Brew Tracker omits a target
✅ Pump OFF orchestration during boil
✅ Runtime terminal completion inference after final Brew Tracker step
✅ Heater/pump stop handling when runtime completes
✅ BrewZilla local Shelly power vs RAPT Cloud telemetry age separation
✅ BrewZilla energy and SEK cost estimate sensors
✅ BrewZilla selectable mash temperature source resolver
✅ BrewZilla mash/wort/delta dashboard-safe sensors
✅ BrewZilla Learning uses the shared mash/wort resolver
✅ BrewZilla Cockpit operator hardware card with mash/wort source display
✅ Brewday Card operator cockpit
✅ Manual Brewday operator card
✅ Brewday Audit Card dashboard example
✅ Brewfather RAW Timeline debug card
✅ Climate Supervisor backend and UI
✅ Kegerator Fan Backend initial compressor/afterrun/fan-auto validation
✅ Carbonation Runtime backend, persistence and UI
✅ Carbonation control entity naming aligned with existing HA entity IDs
✅ Counterflow Wort Cooling backend and UI
✅ Counter Flow Chiller sanitation backend and CFC Ready button
✅ Fermentation Cockpit scope guard and compact idle UI
✅ Backend domain layout refactor
✅ Main repo pruned of legacy packages, patch notes and obsolete migration docs
```

Beta limitations / still pending validation:

```text
[ ] first full serious all-grain batch from start to transfer
[ ] hop addition/event notifications
[ ] real counterflow chilling data
[ ] active fermentation and cold-crash validation
[ ] full carbonation/serving cooling-cycle validation
[ ] full kegerator fan-auto turn-off validation after afterrun expiry
[ ] legacy package cleanup validation in existing local HA installs
[ ] RAPT Cloud Link latency remains a known limitation
[ ] no known local BrewZilla/RAPT API integration
[ ] external RAPT BLE Thermometer depends on RAPT Cloud Link control-device telemetry
```

---

## Beta safety scope

```text
Status: beta
Scope: supervised BrewZilla/Brewfather/manual brewday runtime
Control policy: operator-supervised direct actions with abort available
Not stable
Not unattended autopilot
Not recommended without active operator supervision
```

BrewAssistant may apply BrewZilla target/heater/pump actions during a brewday, but the intended operating model is still supervised. The operator should remain present, verify BrewZilla behavior, and keep abort/manual controls available.

Kegerator Fan Backend is narrower: it may only manage kegerator circulation fan actions through its fan-auto switch. Compressor/cooling target behavior remains owned by `climate.kegerator_kylskap` and its Home Assistant climate/thermostat layer.

---

## Architecture layers

| Layer | Purpose |
| --- | --- |
| Python Core | Normalize source entities and expose dashboard-safe state. |
| Brewday Runtime | Resolve Brewfather RAW Brew Tracker and Manual Brewday sessions. |
| Stage Engine | Interpret runtime state plus BrewZilla telemetry into current brewday stage. |
| BrewZilla Orchestration | Apply target/heater/pump actions when allowed by runtime state. |
| BrewZilla Temperature Resolver | Separate mash, wort/kettle and mash-wort delta temperature roles. |
| BrewZilla Learning | Advisory recommendations using the shared temperature resolver. |
| Brewday Audit | Persist event snapshots for post-run analysis of runtime and BrewZilla actions. |
| CFC Sanitation | Optional Counter Flow Chiller boil-sanitation reminder and CFC Ready pump action. |
| Climate Supervisor | Calculate and apply dynamic kegerator/serving air targets through climate control. |
| Kegerator Fan Backend | Infer compressor/fan state and optionally manage fan circulation/afterrun. |
| Cooling Runtime | Track counterflow wort cooling status, pump requirement, heater guard, ETA and pitch readiness. |
| Carbonation Runtime | Track carbonation session state, inputs, calculations and serving guidance. |
| Fermentation Scope Guard | Keep fermentation warnings scoped to active fermentation/cold-crash context. |
| Dashboard | Visualize state and trigger explicit operator actions. |

---

## Brewday / BrewZilla direct flow

Current verified beta flow:

```text
Brewfather RAW Brew Tracker or Manual Brewday
→ Normalized BrewAssistant Brewday Runtime
→ BrewAssistant Stage Engine
→ BrewAssistant BrewZilla Orchestration
→ BrewZilla target/heater/pump actions when allowed
→ Brewday Audit log
→ Dashboard verification
```

Key beta behavior:

```text
- Brewfather paused state freezes current step/target.
- Manual Brewday can own prepare/start/pause/next/reset/finish runtime.
- Manual Brewday can jump directly to Mash, Boil, Whirlpool/Hopstand and Cooling.
- Mash steps can sync BrewZilla target from normalized runtime.
- Boil stages fall back to 100°C when Brew Tracker omits a temperature target.
- Pump is stopped during boil unless an explicit operator action, such as CFC Ready, starts it.
- Runtime completion can be inferred when the final Brew Tracker step reaches zero.
- Heater and pump are stopped when the runtime is completed.
- Shelly power is treated as local live telemetry.
- RAPT temperature/target are treated as cloud/control telemetry.
- RAPT heat/pump utilization are treated as slower config telemetry.
- Mash temperature is operator-selectable, defaulting to Auto.
- Wort/kettle temperature is BrewZilla internal thermometer.
- Mash/Wort delta is exposed as dashboard-safe context.
- RAPT Pill is not used as a hot-side brew temperature source.
```

---

## Kegerator fan-auto flow

Current kegerator fan backend flow:

```text
climate.kegerator_kylskap
+ sensor.kyl_temperatur_4
+ sensor.brewassistant_kegerator_air_temperature_average
+ sensor.kegerator_power
+ switch.kegerator_fan
+ sensor.kegerator_fan_power
→ Kegerator Fan Backend
→ switch.brewassistant_kegerator_fan_auto_enabled attributes
→ optional switch.kegerator_fan on/off actions when fan-auto is enabled
```

Key beta behavior:

```text
- Compressor activity is inferred from sensor.kegerator_power > 20 W.
- Fan running state is inferred from switch.kegerator_fan or fan power > 2 W.
- Fan-auto is off by default.
- Fan runs while compressor is active.
- Fan afterrun continues after compressor stop.
- Restart/statistics trend spikes are ignored above +5.00 °C/h.
- Fan service calls are blocking.
- Compressor/cooling target control remains in climate.kegerator_kylskap.
```

---

## Credits / Acknowledgements

BrewAssistant is an independent Home Assistant custom integration and is not affiliated with Brewfather, KegLand/RAPT or RAPT Cloud.

Thanks to:

- **Brewfather Home Assistant integration** by `MvdDonk`  
  Community integration used as one possible source for Brewfather recipe, batch and brewing data in Home Assistant.  
  https://github.com/MvdDonk/brewfather

- **RAPT Cloud Link for Home Assistant** by `berra200`  
  Community integration used to expose RAPT/BrewZilla telemetry to Home Assistant.  
  https://github.com/berra200/home-assistant-rapt-cloud-link

- **Home Assistant and the brewing automation community**  
  For the ecosystem, frontend cards, integrations and testing inspiration.

---

## Documentation index

```text
docs/INSTALLATION.md                  Current Home Assistant custom integration install guide
docs/setup.md                         Current setup, update and verification guide
docs/dashboard-baselines.md           Current dashboard/card baseline policy
docs/architecture-target.md            Long-term process-first architecture target
docs/module-capability-model.md        Module defaults, capabilities and policy model
docs/manual-brewday.md                Python Manual Brewday runtime, services and safety model
docs/backend-domain-layout.md          Backend package layout after domain refactor
docs/kegerator-fan-backend.md          Kegerator fan/compressor inference and fan-auto policy
docs/brewzilla-temperature-sources.md  Mash/Wort temperature resolver and dashboard policy
docs/counterflow-chiller.md            Python CFC sanitation backend and CFC Ready flow
docs/legacy-package-cleanup.md        Local HA legacy package cleanup checklist
docs/structure.md                      Project structure and module responsibilities
```
