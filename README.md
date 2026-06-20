# BrewAssistant v0.2.0-beta.6

**BrewAssistant v0.2.0-beta.6** is a modular Home Assistant brewing assistant for supervised Brewday runtime intelligence, BrewZilla/RAPT hardware control and visualization, carbonation guidance, dynamic serving/climate supervision, kegerator fan circulation, fermentation tracking, dashboard cards and notifications.

> [!WARNING]
> BrewAssistant Beta is under active development. It is intended for supervised hobby brewing and testing, not unattended automation. Always verify hot-side actions, electrical safety, pump/heater state, pressure equipment, sanitation and fermentation decisions manually.

The project has moved away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations, safety guards, notifications and hardware orchestration live in `custom_components/brewassistant/`.

```text
Python custom integration = logic, normalization, stage engine, calculations, control decisions, safety guards, notifications
Dashboard YAML             = presentation and explicit operator actions
Legacy local packages      = local compatibility/cleanup only, not mainline repo setup
```

---

## AI-assisted development

BrewAssistant is a hobby/beta project developed in close collaboration between Joachim Eriksson and ChatGPT.

Large parts of the Python integration, dashboard YAML, documentation, refactoring and troubleshooting have been generated, rewritten or iterated with ChatGPT based on Joachim's Home Assistant setup, brewing workflow, real hardware tests and feedback.

Joachim provides the brewing domain context, hardware environment, requirements, testing, validation and operational decisions. The generated code should therefore be treated as experimental and reviewed carefully before use, especially anywhere it can affect heat, pumps, cooling, pressure equipment or other physical brewing hardware.

This repository is shared openly for transparency, learning and experimentation — not as a claim that all code was hand-written by the repository owner.

---

## Current status

```text
v0.2.0-beta.6
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
✅ Climate Supervisor backend and UI
✅ Kegerator Fan Backend clean entity IDs and Always on / Afterrun validation
✅ Kegerator fan mode/afterrun/fan-auto controls
✅ Carbonation Runtime backend, persistence and UI
✅ Carbonation control entity naming aligned with existing HA entity IDs
✅ Counterflow Wort Cooling backend
✅ Counter Flow Chiller sanitation backend and CFC Ready button
✅ Counter Flow Chiller dashboard card baseline
✅ Fermentation Cockpit scope guard and compact idle UI
✅ Backend domain layout refactor
✅ Local Home Assistant baseline cleanup: no active `bryggeriet_` BrewAssistant entity prefix
✅ Legacy local cleanup validated in active HA install: old audit sensors inactive, current Event Log active
✅ Integration brand assets under `custom_components/brewassistant/brand/`
✅ Main repo pruned of legacy package/dashboard clutter
```

Beta limitations / still pending validation:

```text
[ ] first full serious all-grain batch from start to transfer
[ ] BrewTracker running → paused → next-step transitions with real Brewfather snapshots
[ ] hop addition/event notifications
[ ] real counterflow chilling data
[ ] active fermentation and cold-crash validation
[ ] full carbonation/serving cooling-cycle validation
[ ] full kegerator fan-auto turn-off validation after afterrun expiry
[ ] kegerator guard watchdog async-safety patch log validation after HA restart
[ ] RAPT Cloud Link latency remains a known limitation
[ ] no known local BrewZilla/RAPT API integration
[ ] external RAPT BLE Thermometer depends on RAPT Cloud Link control-device telemetry
```

---

## HACS custom repository install

This beta can be installed as a **HACS custom repository**.

In Home Assistant:

```text
HACS → three-dot menu → Custom repositories
```

Add repository URL:

```text
https://github.com/Jocke1970/brewassistant-beta
```

Select category/type:

```text
Integration
```

Then install **BrewAssistant Beta**, restart Home Assistant, and add/configure the integration from:

```text
Settings → Devices & services → Add integration → BrewAssistant Beta
```

Notes:

```text
- HACS installs the integration files under /config/custom_components/brewassistant/.
- Integration brand assets live under /config/custom_components/brewassistant/brand/.
- Dashboard YAML files in dashboard/ are examples and are not automatically installed as dashboards.
- This repo is intended as a custom repository, not as a default HACS repository.
- Keep operator supervision active during all BrewZilla/heater/pump tests.
```

---

## Manual install / update

Manual installation is still supported.

From a temporary clone of the repository:

```bash
rm -rf /tmp/brewassistant-beta
git clone --depth 1 --branch main https://github.com/Jocke1970/brewassistant-beta.git /tmp/brewassistant-beta

mkdir -p /config/brewassistant_backups/custom_components

if [ -d /config/custom_components/brewassistant ]; then
  cp -a /config/custom_components/brewassistant \
    /config/brewassistant_backups/custom_components/brewassistant_backup_$(date +%Y%m%d_%H%M)
fi

rsync -a --delete \
  /tmp/brewassistant-beta/custom_components/brewassistant/ \
  /config/custom_components/brewassistant/
```

Restart Home Assistant after syncing.

---

## Dashboard baseline

Current dashboard examples live under:

```text
dashboard/
```

Current baseline files:

```text
dashboard/brewassistant_sanity.yaml
dashboard/cards/brewassistant_hub.yaml
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_event_log.yaml
dashboard/cards/brewassistant_manual_brewday.yaml
dashboard/cards/brewassistant_source_health.yaml
dashboard/cards/brewfather_feed.yaml
dashboard/cards/brewzilla.yaml
dashboard/cards/brewzilla_learning.yaml
dashboard/cards/carbonation.yaml
dashboard/cards/counterflow_chiller.yaml
dashboard/cards/fermentation.yaml
dashboard/cards/kegerator.yaml
```

Dashboard docs:

```text
dashboard/README.md
docs/dashboard-baselines.md
docs/beta5-sanity-dashboard.md
docs/beta6-release-notes.md
```

Dashboard YAML is presentation-only. It may display state and call explicit operator actions, but business logic, safety guards and backend notifications should stay in the Python integration.

---

## Beta safety scope

```text
Status: beta
Scope: supervised BrewZilla/Brewfather/manual brewday runtime
Control policy: operator-supervised direct actions with ABORT lockout and safe-state enforcement
Not stable
Not unattended autopilot
Not recommended without active operator supervision
```

BrewAssistant may apply BrewZilla target/heater/pump actions during a brewday, but the intended operating model is still supervised. The operator should remain present, verify BrewZilla behavior, and keep abort/manual controls available.

ABORT has highest priority over normal orchestration. During ABORT lockout, BrewAssistant should hold BrewZilla heater off, pump off, heat utilization 0 and pump utilization 0 through the available RAPT Cloud Link command entities.

Kegerator Fan Backend is narrower: it may only manage kegerator circulation fan actions through its fan-auto switch. Compressor/cooling target behavior remains owned by `climate.kegerator_kylskap` and its Home Assistant climate/thermostat layer.

---

## Architecture layers

| Layer | Purpose |
| --- | --- |
| Python Core | Normalize source entities and expose dashboard-safe state. |
| Brewday Runtime | Resolve Brewfather RAW Brew Tracker and Manual Brewday sessions. |
| Stage Engine | Interpret runtime state plus BrewZilla telemetry into current brewday stage. |
| BrewZilla Orchestration | Apply target/heater/pump/utilization strategies when allowed by runtime state. |
| BrewZilla Temperature Resolver | Separate mash, wort/kettle and mash-wort delta temperature roles. |
| Brewday Advice | Advisory recommendations using the shared temperature resolver; backend notifies the operator when new pending advice appears. |
| Brewday Event Log | Persist event snapshots for post-run analysis of runtime and BrewZilla actions. |
| CFC Sanitation | Optional Counter Flow Chiller boil-sanitation reminder and CFC Ready pump action. |
| Climate Supervisor | Calculate and apply dynamic kegerator/serving air targets through climate control. |
| Kegerator Guard | Safety/watchdog layer for kegerator climate and compressor guard diagnostics. |
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
→ Brewday Event Log
→ Brewday Advice backend notification when new pending advice appears
→ Dashboard verification
```

Key beta behavior:

```text
- Brewfather paused state freezes current step/target.
- Manual Brewday can own prepare/start/pause/next/reset/finish runtime.
- Manual Brewday can jump directly to Mash, Boil, Whirlpool/Hopstand and Cooling.
- Mash steps can sync BrewZilla target from normalized runtime.
- Heating to mash-in uses a staged BrewZilla strategy: pump off at full heat, taper/mix near target, then pump off for mash-in confirmation.
- Boil stages fall back to 100°C when Brew Tracker omits a temperature target.
- Pump is stopped during boil unless an explicit operator action, such as CFC Ready, starts it.
- Runtime completion can be inferred when the final Brew Tracker step reaches zero.
- ABORT blocks automatic re-apply and enforces heater/pump/utilization safe state during lockout.
- New Brewday Advice recommendations create a backend-owned persistent notification.
```
