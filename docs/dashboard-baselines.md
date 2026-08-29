# Dashboard baselines

This document summarizes the current BrewAssistant dashboard baseline.

Dashboard YAML is a presentation and explicit operator-action layer. Runtime interpretation, calculations, safety guards, BrewZilla orchestration, source ownership and session state belong in the Python custom integration.

---

## Current baseline directories

```text
dashboard/
  brewassistant_sanity.yaml
  brewassistant_sanity_sv.yaml
  cards/
```

`dashboard/brewassistant_sanity.yaml` is the compact post-update smoke-test dashboard. The `_sv.yaml` file is its Swedish presentation mirror.

`dashboard/cards/` contains reusable daily-dashboard snippets. The old plural `dashboards/` directory is not the current source of truth.

Canonical dashboard language policy:

```text
English card = canonical machine-reference layout
Swedish card = presentation mirror using the same entity/action references
```

---

## Current reusable cards

The current baseline contains 24 canonical cards and 24 Swedish `_sv.yaml` mirrors:

```text
dashboard/cards/brewassistant_hub.yaml
dashboard/cards/brewassistant_visibility_badges.yaml
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewsteps.yaml
dashboard/cards/brewassistant_brewday_bf_reload.yaml
dashboard/cards/brewassistant_brewday_event_log.yaml
dashboard/cards/brewassistant_manual_brewday.yaml
dashboard/cards/brewassistant_source_health.yaml
dashboard/cards/brewfather_feed.yaml
dashboard/cards/brewfather_recipe.yaml
dashboard/cards/brewtracker_runtime.yaml
dashboard/cards/brewzilla.yaml
dashboard/cards/brewzilla_ble_status.yaml
dashboard/cards/brewzilla_ble_indicator.yaml
dashboard/cards/brewzilla_dual_temperature_gauge.yaml
dashboard/cards/brewzilla_mash_in_confirm.yaml
dashboard/cards/brewzilla_mash_in_controls.yaml
dashboard/cards/brewzilla_local_control.yaml
dashboard/cards/brewzilla_safety_rcl.yaml
dashboard/cards/brewzilla_learning.yaml
dashboard/cards/counterflow_chiller.yaml
dashboard/cards/carbonation.yaml
dashboard/cards/fermentation.yaml
dashboard/cards/kegerator.yaml
```

Every canonical card must have a corresponding `_sv.yaml` presentation mirror.

`brewzilla_advice_auto.yaml` / `_sv.yaml` are retired. Their compact recommendation content is consolidated into `brewzilla_learning.yaml` / `_sv.yaml`, which is now the single Brewing Advice / Bryggråd surface.

---

## BrewAssistant Hub

File:

```text
dashboard/cards/brewassistant_hub.yaml
```

Purpose: compact mission-control overview above domain cards.

Policy:

```text
- Show major BrewAssistant domains in one overview.
- Keep inactive/disconnected modules visually calm.
- Prioritize active brewday, cooling, fermentation/cold-crash and carbonation states.
- Source/feed status supports the workflow; it does not replace domain ownership state.
```

---

## Brewday Runtime operator cockpit

Files:

```text
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_sv.yaml
```

Purpose: normalized operator cockpit for Brewfather-driven and Manual Brewday state.

Current policy:

```text
- Show normalized BrewAssistant runtime, not raw Brewfather internals by default.
- Brewfather and Manual Brewday share the same operator mental model.
- Positive hardware actions are explicit and supervised.
- Pending-plan rejection and physical ABORT must never share the same label/meaning.
- Operator ABORT state must be visually obvious and require explicit rearm.
```

### Supervised Apply controls

```text
CONFIRM ACTION / BEKRÄFTA ÅTGÄRD
  -> executes a still-valid pending positive plan
  -> pulses only while a pending plan exists

REJECT ACTION / AVVISA ÅTGÄRD
  -> rejects the current pending plan
  -> does not physically ABORT BrewZilla
```

The confirmation pulse remains reduced-motion safe through `prefers-reduced-motion`.

### Brewday ABORT controls

```text
ABORT BREWDAY / ABORT BRYGGDAG
  -> physical BrewZilla safe-down
  -> persistent BrewAssistant ownership lock

REARM CONTROL / ÅTERAKTIVERA STYRNING
  -> visible when operator control state is aborted
  -> releases the Brewday ownership lock
  -> does not bypass BrewZilla's independent hardware ABORT lockout
```

Relevant entities:

```text
sensor.brewassistant_brewday_operator_control_state
button.brewassistant_abort_brewday
button.brewassistant_rearm_brewday_control
```

The cockpit should show a red ABORT presentation while:

```text
sensor.brewassistant_brewday_runtime_state = aborted
```

The 2026-08-29 physical regression verified that the operator ABORT survives a Home Assistant restart, continues to block Brewfather ownership, and only clears after the explicit rearm action.

---

## Brewsteps — BrewTracker-owned process map

Files:

```text
dashboard/cards/brewassistant_brewsteps.yaml
dashboard/cards/brewassistant_brewsteps_sv.yaml
```

Purpose: read-only physical process overview when Brewfather/BrewTracker owns the active brewday.

Visibility contract:

```text
switch.brewassistant_show_brewday = on
sensor.brewassistant_brewday_runtime_source = Brewfather Brew Tracker
sensor.brewassistant_brewday_runtime_state != idle
```

Policy:

```text
- Show Heat strike -> Mash -> Mash out -> Sparge -> Boil -> Hopstand -> Chill -> Transfer.
- Use normalized Brewday stage/step/next/progress/target plus physical BrewZilla phase context.
- Never expose Manual Brewday service calls or progression buttons.
- Brewfather/BrewTracker owns progression while this card is visible.
- Manual Brewday keeps its separate interactive cockpit only while Manual owns runtime.
```

This card closes the UI gap where the interactive Manual Brewday step grid correctly disappeared under BrewTracker ownership but left no compact physical-process map in its place.

---

## BrewTracker Runtime

File:

```text
dashboard/cards/brewtracker_runtime.yaml
```

Purpose: source visibility for Brewfather/BrewTracker live state, current/next step, stage, progress, refresh and batch status.

Policy:

```text
- Show brew_tracker_batch_status separately from tracker paused/running state.
- Planning may be visible without being a hot-side owner.
- Brewing pre-start may be visible without being a hot-side owner.
- Raw Brewfather visibility must not imply BA physical-control authority.
- After positive tracker-start evidence, Brewsteps provides the read-only physical process map.
```

---

## Brewday Event Log / Flight Recorder

Files:

```text
dashboard/cards/brewassistant_brewday_event_log.yaml
dashboard/cards/brewassistant_brewday_event_log_sv.yaml
```

Purpose: show event-log state, latest event, step/target evidence and explicit log actions.

Policy:

```text
- UI wording may use Event Log / Flight Recorder.
- Backend compatibility services may still use brewday_audit_* names.
- Event count, latest event, latest step and latest target should be visible quickly.
- Clear/reset actions require confirmation.
- Use the event log as evidence for Confirm/Reject/ABORT testing.
```

---

## BrewZilla operator baseline

Main files:

```text
dashboard/cards/brewzilla.yaml
dashboard/cards/brewzilla_ble_status.yaml
dashboard/cards/brewzilla_ble_indicator.yaml
dashboard/cards/brewzilla_dual_temperature_gauge.yaml
dashboard/cards/brewzilla_mash_in_confirm.yaml
dashboard/cards/brewzilla_mash_in_controls.yaml
dashboard/cards/brewzilla_local_control.yaml
dashboard/cards/brewzilla_safety_rcl.yaml
dashboard/cards/brewzilla_learning.yaml
```

Responsibilities:

```text
BrewZilla
  = hardware cockpit + raw heater/pump visibility + physical ABORT

BLE status / indicator / dual-temperature gauge
  = external process-temperature visibility and kettle/internal comparison

Mash-In Controls
  = canonical explicit two-step mash-in handoff

Mash-In Confirm
  = legacy compatibility mash-in/circulation transition surface

Local Control
  = target/local-regulation/lease visibility

Brewing Advice / Bryggråd
  = recommendation + explanation + risk/confidence + learning evidence
  = APPLY/DENY / VERKSTÄLL/AVVISA for actionable learning recommendations
  = expandable deeper learning diagnostics in the same card

Safety/RCL
  = freshness/guards/filter/ABORT diagnostics
```

The previous separate `Brewday Advice` card is intentionally removed. Advice and Learning are one operator concept; Safety/RCL remains separate because it answers whether control/data is safe rather than what BA recommends.

The BrewZilla `AVBRYT`/ABORT control continues to use the hardware-level `brewassistant.abort_brewzilla` path. The Brewday-level ABORT button reuses that same physical path and adds the persistent Brewday ownership latch.

---

## BrewZilla mash-in operator baseline

`dashboard/cards/brewzilla_mash_in_controls.yaml` is the canonical two-step mash-in control surface. `dashboard/cards/brewzilla_mash_in_confirm.yaml` remains for compatibility during migration.

Important entities include:

```text
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_mash_in_started
button.brewassistant_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
```

Expected high-level flow:

```text
1. Heat-strike reaches readiness gate.
2. Operator starts mash-in / grain addition and confirms Mash-In Started.
3. Pump remains stopped while grain is added.
4. Brewfather Continue or operator confirmation completes mash-in.
5. Circulation resumes.
```

The state machine is one-way; UI should not invite a stale transition backwards after mash-in is complete.

---

## Button-action policy

Dashboard operator actions should use BrewAssistant button entities where a dedicated action entity exists:

```text
button.press -> button.brewassistant_*
```

Do not create parallel workaround paths for the same physical action. A single backend path makes event logging, safety review and regression testing deterministic.

Exceptions are compatibility services already established as authoritative infrastructure actions, for example the BrewZilla hardware ABORT service used by its hardware cockpit.

---

## Visibility policy

Daily dashboard sections may use BrewAssistant visibility switches such as:

```text
switch.brewassistant_show_brewday
switch.brewassistant_show_brewzilla
switch.brewassistant_show_brewzilla_learning
switch.brewassistant_show_event_log
switch.brewassistant_show_source_health
switch.brewassistant_show_fermentation
switch.brewassistant_show_carbonation
switch.brewassistant_show_kegerator
```

Diagnostic cards may auto-show when risk, warning, missing context, guard activity, pending confirmation or operator ABORT state is present.

---

## Frontend dependencies

Install required Lovelace frontend cards through HACS before copying dashboard examples:

```text
custom:button-card
custom:vertical-stack-in-card
custom:mushroom-*
custom:expander-card
custom:gauge-card-pro
custom:bar-card
custom:apexcharts-card
```
