# BrewAssistant v0.2.0-beta.8

**BrewAssistant v0.2.0-beta.8** is a modular Home Assistant brewing assistant for supervised Brewday runtime intelligence, BrewZilla/RAPT hardware control and visualization, cooling, carbonation, climate/serving supervision, fermentation tracking, dashboard cards and notifications.

> [!WARNING]
> BrewAssistant Beta is under active development. It is intended for supervised hobby brewing and testing, not unattended automation. Always verify hot-side actions, electrical safety, pump/heater state, pressure equipment, sanitation and fermentation decisions manually.

The project has moved away from YAML-heavy Home Assistant packages toward a Python custom integration where business logic, runtime normalization, stage interpretation, calculations, safety guards and hardware orchestration live in `custom_components/brewassistant/`.

```text
Python custom integration = runtime + ownership + logic + safety + hardware decisions
Dashboard YAML             = presentation + explicit operator actions
Legacy local packages      = compatibility/cleanup only
```

---

## Documentation map

| Area | Document |
| --- | --- |
| Current roadmap | [`docs/roadmap.md`](docs/roadmap.md) |
| Brewday ↔ BrewZilla operator/control flow | [`docs/brewday-brewzilla.md`](docs/brewday-brewzilla.md) |
| Flight Recorder / Event Log | [`docs/brewday-audit.md`](docs/brewday-audit.md) |
| BrewZilla backend responsibilities | [`docs/backends/brewzilla-backend.md`](docs/backends/brewzilla-backend.md) |
| BrewZilla Advice control profile | [`docs/brewzilla-control-profile.md`](docs/brewzilla-control-profile.md) |
| Equipment Learning | [`docs/brewzilla-equipment-learning.md`](docs/brewzilla-equipment-learning.md) |
| Dashboard baseline | [`docs/dashboard-baselines.md`](docs/dashboard-baselines.md) |
| Localization | [`docs/localization.md`](docs/localization.md) |
| Beta 8 release notes | [`docs/beta8-release-notes.md`](docs/beta8-release-notes.md) |

Backend docs should explain intent, safety boundaries, ownership, event-log proof markers and operator controls rather than merely restating code structure.

---

## AI-assisted development

BrewAssistant is a hobby/beta project developed collaboratively by Joachim Eriksson and ChatGPT. Large parts of the Python integration, dashboard YAML, documentation, refactoring and troubleshooting have been generated or iterated with ChatGPT from real Home Assistant/BrewZilla tests and operator feedback.

The generated code should be treated as experimental and reviewed carefully before use anywhere it can affect heat, pumps, cooling, pressure equipment or other physical brewing hardware.

---

## Current hot-side architecture

BrewAssistant is an **operator-supervised** hot-side controller.

```text
Brewfather Brew Tracker or Manual Brewday
        ↓
normalized Brewday Runtime
        ↓
BrewZilla orchestration + safety guards
        ↓
Supervised Apply for positive AUTO actions
        ↓
BrewZilla/RAPT hardware
        ↓
Flight Recorder + passive learning evidence
```

Safety priority:

```text
ABORT / safe-down
  > runtime/source ownership
  > explicit positive confirmation
  > normal orchestration / advice / learning
```

Runtime progression does not itself authorize physical positive actions.

---

## Brewfather ownership baseline

Brewfather batch phase and Brew Tracker execution are not the same thing.

```text
Planning
  -> visible/ready
  -> no hot-side ownership

Brewing but paused on initial Start step
  -> visible/ready
  -> no hot-side ownership

Brewing after positive tracker-start evidence
  -> Brewfather becomes hot-side runtime owner

Started tracker paused later
  -> ownership remains latched to that tracker/batch
```

`active: true` alone is not start evidence.

This behavior was physically validated on 2026-08-29: moving the batch to Brewing without Play left BrewAssistant non-owning and BrewZilla outputs safe; Play then produced the expected Brewfather takeover.

---

## Supervised Apply baseline

Automatic positive actions require explicit confirmation, including:

```text
target increase
heat-utilization increase
pump-utilization increase
heater ON
pump ON
```

The general Brewday cockpit deliberately separates three operator intents:

```text
CONFIRM ACTION / BEKRÄFTA ÅTGÄRD
  -> execute a still-valid pending positive plan

REJECT ACTION / AVVISA ÅTGÄRD
  -> reject one pending plan only

ABORT BREWDAY / ABORT BRYGGDAG
  -> physical BrewZilla safe-down + persistent BA ownership lock
```

After Brewday ABORT, control is released only by:

```text
REARM CONTROL / ÅTERAKTIVERA STYRNING
```

Rearm does not bypass BrewZilla's independent hardware ABORT lockout.

---

## Physically validated 2026-08-29 chain

The current Brewfather/BrewZilla supervised baseline has verified:

```text
✅ Planning can start/keep Flight Recorder without owning hot side
✅ Brewing pre-start does not own hot side even with active:true
✅ Play / paused->running creates Brewfather ownership
✅ Planning -> pre-start -> Play remains one Flight Recorder session
✅ pending confirmation causes no positive physical write
✅ explicit confirmation applies heat utilization
✅ explicit confirmation applies pump utilization
✅ explicit confirmation turns heater ON
✅ explicit confirmation turns pump ON
✅ supervised_executed is recorded after complete plan execution
✅ hardware ABORT turns heater OFF
✅ hardware ABORT turns pump OFF
✅ hardware ABORT zeros both utilizations
✅ hardware ABORT lockout blocks recreated positive actions
```

The next short physical regression is the Brewday-level persistent operator ABORT/rearm path.

---

## RAPT Cloud Link safeguards

RCL can replay stale configuration after a successful write. BrewAssistant now keeps effective runtime target separate from physical device target and uses a narrow confirmed-plan readback grace so an old target/heat/pump number value does not immediately reopen confirmation for the same already-approved intention.

The grace does not silently re-energize heater or pump and ABORT invalidates it immediately.

Telemetry recovery is separate from physical control: stale RCL may trigger refresh/reload diagnostics, but recovery itself must not rewrite target/heat/pump when BrewZilla already has a valid local regulation target.

---

## External process-temperature sensor ownership

The optional external process-temperature sensor, e.g. a RAPT BLE Thermometer, has fixed phase-scoped ownership:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday/BrewZilla hot-side runtime

Boil starts
  Brewday releases external sensor ownership

Chill -> Transfer
  owner = CFC backend
  role = CFC outlet / wort-out temperature
```

BrewZilla internal temperature remains Brewday Runtime's primary kettle temperature throughout the hot-side process.

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
✅ explicit/non-bypassable Supervised Apply
✅ cancelled-plan suppression
✅ confirmed RCL number-readback grace
✅ BrewZilla hardware ABORT + lockout
✅ Brewday persistent operator ABORT + explicit rearm
✅ clean heat-strike + mash-in state machine
✅ RCL recovery/local-regulation preservation
✅ Manual channel-scoped target/heat/pump ownership
✅ passive BrewZilla Equipment Learning foundation
✅ Counterflow Wort Cooling backend/cockpit
✅ Carbonation Runtime/cockpit
✅ Climate Supervisor
✅ Kegerator fan/guard logic
✅ Fermentation cockpit foundation
✅ English canonical + Swedish dashboard mirror policy
```

---

## Immediate validation focus

```text
🧪 Brewday ABORT button: safe-down + runtime_state aborted
🧪 Brewfather cannot reclaim ownership while operator control is aborted
🧪 HA restart preserves operator ABORT latch
🧪 explicit rearm restores eligibility without bypassing hardware lockout
🧪 first supervised real-mash heat-strike/mash-in validation
🧪 66°C hold and 66 -> 72°C real-mash ramp
🧪 boil ramp / boil validation
🧪 external process-sensor release at Boil
🧪 CFC acquisition during Chill/Transfer
🧪 Equipment Learning planned-vs-actual timing evidence
```

See [`docs/roadmap.md`](docs/roadmap.md) for the detailed sequence.
