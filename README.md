# BrewAssistant v0.2.0-beta.7

**BrewAssistant v0.2.0-beta.7** is a modular Home Assistant brewing assistant for supervised Brewday runtime intelligence, BrewZilla/RAPT hardware control and visualization, carbonation guidance, dynamic serving/climate supervision, kegerator fan circulation, fermentation tracking, dashboard cards and notifications.

> [!WARNING]
> BrewAssistant Beta is under active development. It is intended for supervised hobby brewing and testing, not unattended automation. Always verify hot-side actions, electrical safety, pump/heater state, pressure equipment, sanitation and fermentation decisions manually.

The project has moved away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations, safety guards, notifications and hardware orchestration live in `custom_components/brewassistant/`.

```text
Python custom integration = logic, normalization, stage engine, calculations, control decisions, safety guards, notifications
Dashboard YAML             = presentation and explicit operator actions
Legacy local packages      = local compatibility/cleanup only, not mainline repo setup
```

---

## Documentation map

Start here when trying to understand how the current backend behaves:

| Area | Document |
| --- | --- |
| Backend documentation index | [`docs/backends/README.md`](docs/backends/README.md) |
| BrewZilla backend responsibilities | [`docs/backends/brewzilla-backend.md`](docs/backends/brewzilla-backend.md) |
| BrewZilla Advice control profile | [`docs/brewzilla-control-profile.md`](docs/brewzilla-control-profile.md) |

Backend documentation should explain intent, safety boundaries, event-log markers and dashboard dependencies, not just restate code structure.

---

## AI-assisted development

BrewAssistant is a hobby/beta project developed in close collaboration between Joachim Eriksson and ChatGPT.

Large parts of the Python integration, dashboard YAML, documentation, refactoring and troubleshooting have been generated, rewritten or iterated with ChatGPT based on Joachim's Home Assistant setup, brewing workflow, real hardware tests and feedback.

Joachim provides the brewing domain context, hardware environment, requirements, testing, validation and operational decisions. The generated code should therefore be treated as experimental and reviewed carefully before use, especially anywhere it can affect heat, pumps, cooling, pressure equipment or other physical brewing hardware.

This repository is shared openly for transparency, learning and experimentation — not as a claim that all code was hand-written by the repository owner.

---

## Current status

```text
v0.2.0-beta.7
Safe Advice Beta
```

Validated in the active beta baseline:

```text
✅ Brewfather RAW Brew Tracker runtime resolver
✅ Python Manual Brewday runtime and services
✅ Normalized Brewday Runtime selects Brewfather or Manual Brewday source
✅ Human-friendly Brew Tracker step labels
✅ Paused Brewfather freeze-state handling
✅ BrewTracker entity resolver supports brew_tracker and brewtracker naming variants
✅ Brewfather Feed dashboard card
✅ Source Health dashboard card
✅ BrewZilla runtime sensors
✅ BrewZilla target sync from normalized Brewday Runtime
✅ BrewZilla Orchestration bridge for Manual Brewday target
✅ BrewZilla heater/pump direct actions
✅ BrewZilla mash-in heat strategy: ramp far, approach, mash-in ready and overshoot phases
✅ BrewZilla mash-in confirmation gate pending binary sensor
✅ BrewZilla Mash-In Complete operator button
✅ BrewZilla Start Mash Circulation operator button
✅ BrewZilla mash-in confirmation starts circulation using pump utilization plus pump switch
✅ ABORT service for heater + pump
✅ ABORT lockout blocks automatic BrewZilla re-apply after operator stop
✅ ABORT safe-state enforcement: heater off, pump off, heat utilization 0 and pump utilization 0
✅ Brewday Event Log backend, services, sensors and dashboard card
✅ Brewday Event Log uses normalized runtime for Brewfather and Manual Brewday
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
✅ Brewday Advice uses the shared mash/wort resolver
✅ Brewday Advice uses normalized runtime for Brewfather and Manual Brewday
✅ Brewday Advice persistent notification for new pending recommendations
✅ BrewZilla operator card and Brewday Advice card baseline
✅ Brewday Runtime operator card
✅ Manual Brewday operator card
✅ Kegerator fan/guard card baseline
✅ Fermentation cockpit card baseline
✅ Carbonation runtime card baseline
✅ BrewAssistant Hub card baseline
✅ Sanity dashboard baseline
```

Active BrewZilla/Brewday Advice test focus:

```text
🧪 Built-in BrewZilla 35L small-batch advice profile
🧪 Thermal mix modifier: cap heat and raise pump when wort is above target while mash lags
🧪 Paused mash-hold maintenance: limited heat/pump corrections while Brewfather reports paused hold
🧪 Mash circulation floor after mash-in: keep pump at or above 50 % unless a safety/gate/abort guard blocks it
🧪 Local-control lease break reasons: retake control when Advice sees thermal mix, near-target taper or profile changes
🧪 Recommended supervised test recipe: 5 min ramps, unchanged hold times
```

---

## Documentation TODO

The backend documentation index lists planned per-backend documents for Brewday Runtime, Event Log, Fermentation, Kegerator, Carbonation and Notifications.

The preferred documentation pattern is one focused `.md` per backend area, with:

```text
purpose
read/write entities
safety boundaries
event-log proof markers
dashboard dependencies
known test focus
```
