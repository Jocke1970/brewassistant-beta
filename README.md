# BrewAssistant v0.2.0-beta.9 candidate

**BrewAssistant** is a modular Home Assistant brewing assistant for supervised Brewday runtime intelligence, BrewZilla/RAPT hardware control and visualization, cooling, carbonation, climate/serving supervision, fermentation tracking, dashboard cards and notifications.

> [!WARNING]
> BrewAssistant Beta is under active development. It is intended for supervised hobby brewing and testing, not unattended automation. Always verify hot-side actions, electrical safety, pump/heater state, pressure equipment, sanitation and fermentation decisions manually.

The project has moved away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations, safety guards and hardware orchestration live in `custom_components/brewassistant/`.

```text
Python custom integration = runtime + ownership + logic + safety + hardware decisions
Dashboard YAML             = presentation + explicit operator actions
```

---

## Development / release flow

BrewAssistant now uses only three long-lived branches:

```text
dev  ->  beta  ->  main  ->  GitHub Release
```

- `dev` = ongoing development
- `beta` = integrated practical-test candidate
- `main` = installable/runnable version
- GitHub releases are created only from `main`

Promotion PRs use **Create a merge commit** so the permanent branches keep an explicit ancestry chain. Do not squash `dev -> beta` or `beta -> main`.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Repository watchdogs

The repository runs:

```text
CI / Python compile / fatal Ruff checks
pytest on Python 3.11 / 3.12 / 3.13
HACS Action
Hassfest
Dependabot
promotion-branch guard
```

CI, HACS and Hassfest run across `dev`, `beta` and `main`. Dependabot targets `dev`.

---

## Documentation map

| Area | Document |
| --- | --- |
| Current roadmap | [`docs/roadmap.md`](docs/roadmap.md) |
| Brewday ↔ BrewZilla operator/control flow | [`docs/brewday-brewzilla.md`](docs/brewday-brewzilla.md) |
| Latest physical validation | [`docs/physical-validation-2026-09-05.md`](docs/physical-validation-2026-09-05.md) |
| Previous physical validation | [`docs/physical-validation-2026-08-31.md`](docs/physical-validation-2026-08-31.md) |
| Beta.9 candidate release notes | [`docs/beta9-release-notes.md`](docs/beta9-release-notes.md) |
| Flight Recorder / Event Log | [`docs/brewday-audit.md`](docs/brewday-audit.md) |
| BrewZilla backend summary | [`docs/backends/brewzilla-backend.md`](docs/backends/brewzilla-backend.md) |
| BrewZilla code-local architecture | [`custom_components/brewassistant/brewzilla/README.md`](custom_components/brewassistant/brewzilla/README.md) |
| Cooling backend responsibilities | [`docs/backends/cooling-backend.md`](docs/backends/cooling-backend.md) |
| BrewZilla control profile | [`docs/brewzilla-control-profile.md`](docs/brewzilla-control-profile.md) |
| Equipment Learning | [`docs/brewzilla-equipment-learning.md`](docs/brewzilla-equipment-learning.md) |
| Dashboard baseline | [`docs/dashboard-baselines.md`](docs/dashboard-baselines.md) |
| Localization | [`docs/localization.md`](docs/localization.md) |
| Development / release policy | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

Historical physical-validation documents are evidence snapshots and should not be rewritten to make later fixes look retroactively correct.

---

## Current hot-side architecture

BrewAssistant is an operator-supervised hot-side controller.

```text
Brewfather Brew Tracker or Manual Brewday
        ↓
normalized Brewday Runtime
        ↓
BrewZilla orchestration + phase/safety guards
        ↓
BrewZilla/RAPT physical target / heat / pump
        ↓
Flight Recorder + diagnostics + passive learning evidence
```

Safety priority:

```text
ABORT / hard safety
  > source ownership
  > dedicated phase authority
  > generic supervised positive control
  > local-regulation preservation
  > advice / learning / UI
```

---

## Brewfather ownership baseline

Brewfather batch phase and Brew Tracker execution are separate concepts.

```text
Planning
  -> visible/ready
  -> no hot-side ownership

Brewing but still on initial Start step
  -> visible/ready
  -> no hot-side ownership

positive tracker-start evidence
  -> Brewfather becomes hot-side runtime owner

started tracker paused later
  -> ownership remains latched to that tracker/batch
```

`active: true` alone is not start evidence.

This behavior was physically validated during the 2026-08-29 supervised run.

---

## Dedicated Heatstrike / Mash-In controller

`Brewfather Play` authorizes the dedicated pre-mash physical controller. Inside this phase BrewAssistant may make bounded target/heat/pump adjustments without opening a new generic confirmation for every small modulation.

Outside dedicated phase authority, positive automatic control continues through Supervised Apply where applicable.

Temperature roles:

```text
external MASH/process probe = readiness + process authority
BrewZilla internal/WORT     = kettle context + limiter/safety view
```

The external process probe remains hot-side-owned from Heat strike through Pre-boil, then is released at Boil for later Cooling/CFC ownership when applicable.

---

## Heatstrike gradient relief — PR #197

The 2026-09-05 field test reproduced a physical deadlock where the external MASH/BLE probe was still below strike while BrewZilla internal temperature had already crossed the target.

Current narrow exception:

```text
MASH/BLE still below strike
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +1.5 °C

=> heat authority capped at 15%
=> BrewZilla local thermostat remains available
=> pump 100% for equalization
```

Hard boundary:

```text
hottest-view overshoot > +1.5 °C
  -> explicit hard stop
```

This is not a general relaxation of overshoot safety; it only prevents the observed pre-mash gradient deadlock.

---

## Mash-In handoff — PR #202

Current physical state machine:

```text
ready_for_mash_in
  -> Mash-In Started
  -> target releases toward mash target
  -> pump OFF / utilization 0%
  -> grain addition / stirring
  -> wait for real Brewfather progression
  -> Mash-In Complete
  -> normal circulation resumes
```

Automatic completion requires real progression evidence:

```text
paused -> running
OR
active Brewfather mash target moves away from captured strike target
```

A plain Brewfather `running` state alone is not sufficient.

The Mash-In status UI now prefers live gate/orchestration state and should disappear after completion.

---

## ABORT / safe-down

The authoritative BrewZilla ABORT path performs:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
positive-action lockout
```

Brewday operator ABORT adds a persistent BrewAssistant ownership latch around that physical safe-down. Brewfather cannot silently reclaim hot-side ownership while the latch remains aborted.

The latch survives Home Assistant restart and is released only by explicit rearm.

---

## External process-temperature sensor ownership

Fixed architecture:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday / BrewZilla hot-side

Boil starts
  hot-side releases external sensor

Chill -> Transfer
  owner = Cooling/CFC when method requires it
  role = CFC outlet / wort-out temperature
```

BrewZilla internal temperature remains the primary kettle temperature throughout the hot-side path.

---

## Current implemented areas

```text
✅ Python custom integration + coordinator/config flow
✅ Brewfather RAW tracker resolver + smart refresh policy
✅ Manual Brewday Python runtime
✅ Brewday Stage Engine
✅ Brewday Event Log / Flight Recorder
✅ deterministic one-log-per-brewday boundary
✅ Brewfather actual-start ownership gate
✅ BrewZilla target/heat/pump orchestration
✅ dedicated Heatstrike/Mash-In phase authority
✅ Heatstrike gradient relief
✅ Mash-In progression/pump-hold contract
✅ generic Supervised Apply outside dedicated phase authority
✅ confirmed RCL readback grace
✅ BrewZilla hardware ABORT + lockout
✅ Brewday persistent operator ABORT + explicit rearm
✅ read-only physical ramp/hold timing telemetry
✅ RCL recovery / fail-passive local-regulation preservation
✅ Manual channel-scoped target/heat/pump ownership
✅ passive BrewZilla Equipment Learning foundation
✅ Cooling Runtime v2 / CFC + coil/manual-water method model
✅ Carbonation Runtime/cockpit
✅ Climate Supervisor
✅ Kegerator fan/guard logic
✅ Fermentation tracking/cockpit foundation
✅ English canonical + Swedish dashboard mirror policy
✅ HACS/Hassfest/CI watchdog baseline
```

---

## Immediate validation focus

```text
🧪 verify Heatstrike gradient relief converges MASH/BLE safely
🧪 verify > +1.5 °C hottest-view overshoot still hard-stops heat
🧪 verify Mash-In Started holds pump OFF / 0% until BF progression
🧪 verify Mash-In waiting UI clears immediately after completion
🧪 validate physical 66 °C hold and separate 66 -> 72 °C ramp timing
🧪 first supervised real-mash Heatstrike/Mash-In validation
🧪 Mash out / Sparge / Pre-boil
🧪 boil ramp / boil
🧪 external process-sensor release at Boil
🧪 Cooling/CFC acquisition during Chill/Transfer
🧪 Equipment Learning planned-vs-actual timing evidence
```

See [`docs/roadmap.md`](docs/roadmap.md) for the detailed sequence.

---

## AI-assisted development

BrewAssistant is a hobby/beta project developed collaboratively by Joachim Eriksson and ChatGPT. Python integration code, dashboard YAML, documentation, refactoring and troubleshooting are iterated from real Home Assistant/BrewZilla tests and operator feedback.

Generated or AI-assisted code should be treated as experimental and reviewed carefully before use anywhere it can affect heat, pumps, cooling, pressure equipment or other physical brewing hardware.
