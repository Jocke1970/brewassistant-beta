# Dashboard baselines

This document summarizes the current BrewAssistant dashboard baseline.

Runtime interpretation, calculations, safety guards, BrewZilla orchestration, source ownership and session state belong in the Python custom integration. Presentation and explicit operator actions belong in the dashboard/frontend layer.

Current direction:

```text
Python integration = runtime + logic + safety + ownership
YAML cards          = current presentation / thin wrappers
JS custom cards     = pilot path for complex BrewAssistant-specific instruments
```

---

## Current baseline directories

```text
dashboard/
  brewassistant_sanity.yaml
  brewassistant_sanity_sv.yaml
  cards/
  js/
```

`dashboard/cards/` is the reusable daily-dashboard source. `dashboard/js/` contains BrewAssistant-specific frontend prototypes/resources.

Canonical language policy:

```text
English card = canonical machine-reference layout
Swedish card = presentation mirror using the same entity/action references
```

Every canonical card must have a corresponding `_sv.yaml` mirror.

---

## Current reusable card set

After adding the English mirror for the JS temperature-gauge pilot, the card directory contains **29 canonical filenames and 29 Swedish `_sv.yaml` mirrors** under the current parity convention.

Current canonical set includes:

```text
brewassistant_hub.yaml
brewassistant_visibility_badges.yaml
brewassistant_brewday.yaml
brewassistant_brewday_runtime_flow.yaml
brewassistant_brewsteps.yaml
brewday_physical_timing.yaml
brewassistant_brewday_bf_reload.yaml
brewassistant_brewday_event_log.yaml
brewassistant_manual_brewday.yaml
brewassistant_source_health.yaml
brewfather_feed.yaml
brewfather_recipe.yaml
brewtracker_runtime.yaml
brewzilla.yaml
brewzilla_batch_context.yaml
brewzilla_ble_status.yaml
brewzilla_ble_indicator.yaml
brewzilla_dual_temperature_gauge.yaml
brewzilla_temperature_gauge_js.yaml
brewzilla_mash_in_confirm.yaml
brewzilla_mash_in_controls.yaml
brewzilla_local_control.yaml
brewzilla_safety_rcl.yaml
brewzilla_learning.yaml
counterflow_chiller.yaml
carbonation.yaml
fermentation.yaml
kegerator.yaml
kegerator_temperature_presets.yaml
```

`brewzilla_advice_auto.yaml` is retired; advice/learning presentation is consolidated into `brewzilla_learning.yaml`.

---

## Known EN/SV parity debt at parking checkpoint

The new JS-gauge filename mirror is fixed by the 2026-09-06 parking sync.

General CI still reports older **content** drift between:

```text
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_sv.yaml
```

The Swedish cockpit currently contains entity/action references not yet mirrored by the canonical English card. This is a known UI-sync task and should be fixed deliberately before `dev -> beta` promotion. It is not part of the RCL backend fix.

Do not hide or disable the parity test merely to make CI green.

---

## Brewday Runtime operator cockpit

The main cockpit should show normalized BrewAssistant runtime rather than raw Brewfather internals.

Policy:

```text
- Brewfather and Manual Brewday share one operator mental model.
- Positive hardware actions are explicit and supervised outside dedicated phase authority.
- REJECT and physical ABORT are separate concepts.
- ABORT state is visually obvious and requires explicit rearm.
- Fas / Steg / Nästa / Åtgärd / Styrning must wrap full operational text.
- redundant BrewTracker-status action is omitted when status is already visible in the runtime header/chip.
```

The remaining Brewfather refresh action may use the full row.

### Mash-In presentation

Expected master-cockpit sequence:

```text
ready_for_mash_in
  -> STRIKE READY / START MASH-IN action

mash_in_started
  -> strong waiting presentation
  -> pump OFF / 0 % must be obvious
  -> BF post-start PAUSED requirement should be visible/understandable

mash_in_complete
  -> waiting presentation disappears immediately
  -> actual mash target visible
  -> normal circulation state visible
```

The 2026-09-06 second physical run proves the backend completed `PAUSED -> RUNNING -> mash_in_complete`, but the operator did not perceive that transition quickly enough. UI observability is therefore an explicit next polish item.

---

## Physical step timing

`brewday_physical_timing.yaml` / `_sv.yaml` are read-only presentation for #157.

Policy:

```text
- source schedule time != actual physical process time
- ramp starts on observed physical movement
- first mash hold starts only after Mash-In Complete and target reach
- hold target band = ±0.3 °C
- PAUSE freezes physical elapsed time
- timing does not issue hardware commands
```

---

## Brewsteps

Brewsteps is the read-only BrewTracker-owned process map:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Boil -> Hopstand -> Chill -> Transfer
```

It must never expose Manual Brew progression/control actions while Brewfather owns runtime.

---

## BrewTracker Runtime

Raw Brewfather/BrewTracker state is source visibility, not hardware authority.

```text
Planning / Brewing pre-start
  -> may be visible
  -> no hot-side ownership

positive tracker-start evidence
  -> normalized Brewday ownership may begin
```

---

## BrewZilla operator baseline

Core surfaces:

```text
BrewZilla hardware cockpit
BLE/process-source visibility
dual-temperature gauge
Mash-In controls/status
local-control diagnostics
Safety/RCL diagnostics
Brewing Advice / Equipment Learning
```

Safety/RCL should distinguish:

```text
report freshness
value stagnation
active 30 s coordinator polling
hard recovery/reload
ABORT/fail-passive state
```

The UI must not label `last_updated` value age as RCL poll age.

---

## JavaScript temperature-gauge pilot

Files:

```text
dashboard/js/brewassistant-temperature-gauge.js
dashboard/cards/brewzilla_temperature_gauge_js.yaml
dashboard/cards/brewzilla_temperature_gauge_js_sv.yaml
```

Scope is currently **pre-boil only**. The existing boil-mode gauge and the rest of the dashboard remain on the current implementation.

Pilot goals:

```text
- Mash and Wort needles share exact SVG center/radius/angle geometry
- explicit target marker/value
- precision band ±0.3 °C
- quality band ±1.0 °C
- thermal-state background
- BrewAssistant-specific status/source presentation
- minimal YAML wrapper
```

The existing `gauge-card-pro` dual-temperature card remains the canonical fallback until the JS pilot is accepted.

This pilot is evidence for a possible future staged YAML -> JS-card migration. It does **not** make a full migration beta.9 release scope.

### Local resource

The pilot resource is expected to be installed into Home Assistant under a path such as:

```text
/config/www/brewassistant/brewassistant-temperature-gauge.js
```

and loaded as a Lovelace module resource:

```text
/local/brewassistant/brewassistant-temperature-gauge.js?v=<cache-buster>
```

---

## Brewday Event Log / Flight Recorder

The event log is the preferred evidence source for physical regression.

Policy:

```text
- event count/latest event/latest step/latest target visible quickly
- ownership/setpoint/readback evidence preserved
- clear/reset actions require confirmation
- backend truth wins over ambiguous dashboard appearance
```

---

## Button-action policy

Use BrewAssistant button entities where a dedicated action entity exists:

```text
button.press -> button.brewassistant_*
```

Do not create parallel workaround paths for the same physical action.

Compatibility infrastructure actions may remain where already authoritative, for example the BrewZilla hardware ABORT service.

---

## Visibility policy

Daily dashboard sections may use visibility switches such as:

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

Diagnostic cards may auto-show when risk, missing context, guard activity, pending confirmation or ABORT state is present.

---

## Frontend dependencies

Current YAML examples may use HACS/custom frontend cards including:

```text
custom:button-card
custom:vertical-stack-in-card
custom:mushroom-*
custom:expander-card
custom:gauge-card-pro
custom:bar-card
custom:apexcharts-card
```

The BrewAssistant JS temperature gauge is a repository/local custom resource, not a HACS dependency.
