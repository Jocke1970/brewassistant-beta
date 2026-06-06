# BrewAssistant v0.2.0-beta.1

**BrewAssistant v0.2.0-beta.1** is a modular Home Assistant brewing assistant for supervised Brewday runtime intelligence, BrewZilla/RAPT hardware control/visualization, counterflow wort cooling, carbonation guidance, dynamic serving/climate supervision, fermentation tracking, dashboards and notifications.

The project is moving away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations and hardware orchestration live in `custom_components/brewassistant/`.

```text
Python custom integration = logic, normalization, stage engine, calculations, control decisions
YAML/dashboard             = presentation and explicit operator actions
Legacy packages            = temporary compatibility only
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
✅ Carbonation Runtime backend, persistence and UI
✅ Counterflow Wort Cooling backend and UI
✅ Counter Flow Chiller sanitation backend and CFC Ready button
✅ Fermentation Cockpit scope guard and compact idle UI
✅ Backend domain layout refactor
```

Beta limitations / still pending validation:

```text
[ ] first full serious all-grain batch from start to transfer
[ ] hop addition/event notifications
[ ] real counterflow chilling data
[ ] active fermentation and cold-crash validation
[ ] full carbonation/serving cooling-cycle validation
[ ] package cleanup validation in a real HA install
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

## Documentation index

```text
docs/manual-brewday.md                 Python Manual Brewday runtime, services and safety model
docs/backend-domain-layout.md          Backend package layout after domain refactor
docs/brewzilla-temperature-sources.md  Mash/Wort temperature resolver and dashboard policy
docs/counterflow-chiller.md            Python CFC sanitation backend and CFC Ready flow
docs/legacy-package-cleanup.md         Checklist for deleting old package YAML safely
docs/legacy-migration.md               Namespace and legacy migration notes
docs/structure.md                      Project structure and module responsibilities
```
