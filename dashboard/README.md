# BrewAssistant dashboard

This directory contains the current dashboard card baseline for BrewAssistant Beta.

Dashboard files are examples/operator UI only. Runtime normalization, orchestration, safety checks and calculations live in the Python custom integration under `custom_components/brewassistant/`.

## Dashboard languages

BrewAssistant maintains two presentation tracks over the same backend:

```text
*.yaml     = canonical English dashboard source
*_sv.yaml  = Swedish presentation mirror
```

Both tracks must use the same BrewAssistant entity IDs, service/action IDs, machine-state comparisons, conditions and hardware-control paths. The Swedish files may translate labels, headings, confirmation text and displayed status wording, but they must not translate values that backend logic or automations depend on.

When adding or materially changing a canonical dashboard card, update its `_sv.yaml` mirror in the same development pass whenever practical. CI enforces filename parity and machine-reference safety through `tests/test_dashboard_language_parity.py`.

## Dashboard composition policy

`dashboard/cards/` is a library of **standalone reusable cards**, not one prescribed BrewAssistant dashboard.

A BrewAssistant user may compose a personal Brewday view from whichever cards fit their setup. No backend feature may exist only inside a private or monolithic dashboard stack. If a UI function is generally useful, it belongs in its own card first; personal dashboards may then embed or combine those cards locally.

The intended boundary is:

```text
BrewAssistant backend
  -> entities, orchestration, safety and actions

dashboard/cards/
  -> reusable UI building blocks

dashboard/examples/
  -> composition guidance/examples only

user dashboard
  -> personal ordering, stacking and selection of the reusable cards
```

`cards/brewassistant_brewday.yaml` is therefore the compact Brewday **overview/status card**. It is intentionally action-free. Operator actions, diagnostics, timing, Mash-In and source-specific runtime surfaces are separate cards.

A typical RAPT-based Brewday composition might use:

```text
brewassistant_brewday
rapt_profile_runtime
brewzilla_mash_in_controls
brewday_physical_timing
brewday_operator_actions
brewday_details
```

A Brewfather/BrewTracker composition can replace `rapt_profile_runtime` with `brewtracker_runtime`. Users are free to omit, reorder or place cards in separate views.

## Current Brewday building blocks

```text
dashboard/cards/
  brewassistant_brewday.yaml
  brewassistant_brewday_sv.yaml
  brewday_operator_actions.yaml
  brewday_operator_actions_sv.yaml
  brewday_details.yaml
  brewday_details_sv.yaml
  brewday_physical_timing.yaml
  brewday_physical_timing_sv.yaml
  brewassistant_brewday_runtime_flow.yaml
  brewassistant_brewday_runtime_flow_sv.yaml
  brewassistant_brewday_event_log.yaml
  brewassistant_brewday_event_log_sv.yaml
  brewtracker_runtime.yaml
  brewtracker_runtime_sv.yaml
  rapt_profile_runtime.yaml
  rapt_profile_runtime_sv.yaml
  brewzilla_mash_in_controls.yaml
  brewzilla_mash_in_controls_sv.yaml
  brewzilla_mash_in_confirm.yaml
  brewzilla_mash_in_confirm_sv.yaml
```

Other module cards remain standalone in the same directory, including BrewZilla, fermentation, CFC/cooling, carbonation, kegerator, source health and Brewfather recipe/feed surfaces.

## Hub replacement workflow

`cards/brewassistant_hub.yaml` is the canonical daily mission-control card. Use `cards/brewassistant_hub_sv.yaml` for the Swedish operator UI.

The Hub card exposes the main daily module toggles. Advanced diagnostic toggles can also be placed as compact badges using `cards/brewassistant_visibility_badges.yaml` or its Swedish mirror.

Important visibility switches include:

```text
switch.brewzilla
switch.brewassistant_show_brewday
switch.brewassistant_show_manual_brewday
switch.brewassistant_show_brewfather_feed
switch.brewassistant_show_brewtracker_runtime
switch.brewassistant_show_brewfather_recipe
switch.brewassistant_show_brewzilla
switch.brewassistant_show_brewzilla_local_control
switch.brewassistant_show_brewzilla_learning
switch.brewassistant_show_brewzilla_safety_rcl
switch.brewassistant_show_event_log
switch.brewassistant_show_cfc
switch.brewassistant_show_source_health
switch.brewassistant_show_fermentation
switch.brewassistant_show_carbonation
switch.brewassistant_show_kegerator
```

The `switch.brewassistant_show_*` entities are persistent backend visibility controls. Existing dashboard cards can be wrapped with conditional-card visibility against these switches, or left as-is until that UI pass is done.

## Brewday card roles

| Canonical file | Purpose |
| --- | --- |
| `brewassistant_brewday.yaml` | Action-free Brewday overview with normalized runtime, source chain, stage, step and progress. |
| `brewday_operator_actions.yaml` | Prepare Manual Brewday, Supervised Apply CONFIRM/REJECT, Brewday ABORT and rearm. |
| `brewday_details.yaml` | Expandable normalized runtime/detail entity list. |
| `brewday_physical_timing.yaml` | Physical ramp/hold timing and history independent of the directive source. |
| `brewassistant_brewday_runtime_flow.yaml` | Runtime/process-flow guidance. |
| `brewassistant_brewday_event_log.yaml` | Brewday event log controls and latest-event diagnostics. |
| `brewtracker_runtime.yaml` | BrewTracker-specific directive/runtime surface. |
| `rapt_profile_runtime.yaml` | RAPT-profile-specific directive/runtime surface, including RAPT target versus effective BA target. |
| `brewzilla_mash_in_controls.yaml` | Two-step physical Mash-In gate: Mash-In Started and Mash-In Complete. |
| `brewzilla_mash_in_confirm.yaml` | Legacy Mash-In compatibility/fallback card. |

These cards are building blocks. None of them is required to be nested inside `brewassistant_brewday.yaml`.

## Brewfather / BrewTracker process-phase roles

The UI is split by process phase rather than by two competing views of the same source:

```text
Planning / Brewing before Play
  -> BrewTracker Runtime is the primary Brewfather-derived source/status card
  -> ready/pre-start is visible but does not imply hot-side ownership

Active BrewTracker-owned Brewing
  -> BrewTracker Runtime remains the source/status view
  -> brewassistant_brewsteps.yaml becomes the read-only physical-process map
  -> Brewsteps never exposes Manual Brewday services or competing progression controls

Fermenting
  -> BrewTracker Runtime leaves the primary view
  -> brewfather_feed.yaml becomes compact Brewfather batch/recipe context
  -> detailed temperature, Pill and climate control remains in Fermentation Cockpit

Technical feed/source health
  -> belongs in Source Health rather than a second large Brewfather runtime card
```

The normalized `sensor.brewassistant_brewfather_batch_phase` is the presentation boundary and uses the same backend phase resolver as Brewfather hot-side ownership. Dashboard code should not invent a separate interpretation of `Planning`, `Brewing` or `Fermenting`.

`brewassistant_brewsteps.yaml` / `_sv.yaml` is visible only when `sensor.brewassistant_brewday_runtime_source` is exactly `Brewfather Brew Tracker` and the normalized runtime is not `idle`. It is intentionally read-only because Brewfather/BrewTracker owns directive progression; Manual Brewday retains its own interactive cockpit only when Manual owns runtime.

## RAPT Profile runtime role

`rapt_profile_runtime.yaml` / `_sv.yaml` is the source-specific RAPT directive surface. It must not become a second BrewZilla controller.

The ownership chain is:

```text
RAPT Profile -> BrewAssistant -> RAPT Cloud Link -> BrewZilla
```

RAPT provides the current profile step, target, end condition and next-step intent. BrewAssistant remains the hot-side controller for target application, heat utilization, pump utilization and hardware ON/OFF decisions.

The reference Mash-In convention is:

```text
Heatstrike -> target reached
Mash In    -> manual/device-button step
Mash Rest  -> timed hold, timer starts at target
```

This allows BrewAssistant's physical Mash-In gate to remain synchronized with RAPT progression without starting the mash timer during the physical grain-in operation.

## BrewZilla two-step Mash-In controls

`cards/brewzilla_mash_in_controls.yaml` is the canonical operator card for the Mash-In handoff; `cards/brewzilla_mash_in_controls_sv.yaml` is the Swedish presentation mirror.

Expected flow:

```text
1. BrewAssistant detects Mash-In/strike readiness.
2. Only button.brewassistant_mash_in_started is visible.
3. Operator starts adding malt and presses Mash-In Started.
4. BA releases strike target toward the mash target, keeps pump OFF and allows low anti-drop heat.
5. Only button.brewassistant_mash_in_complete is visible.
6. Operator finishes stirring/settling the malt bed and presses Mash-In Complete.
7. BA starts mash circulation using the active pump strategy.
8. Both Mash-In buttons disappear.
```

The legacy `cards/brewzilla_mash_in_confirm.yaml` remains for compatibility during migration. The two-step card is the preferred operator surface.

## BrewZilla local-control split

The intended split is:

```text
BrewZilla = operator/hardware cockpit
BrewZilla Mash-In Controls = explicit two-step Mash-In handoff
BrewZilla Local Control = what BA handed to BZ and whether lease is active
Brewing Advice / Bryggråd = what BA recommends, why, risk/confidence and learning detail
Safety/RCL = freshness/guards/filter/abort diagnostics
```

`brewzilla_learning.yaml` / `_sv.yaml` is the single advice + learning operator surface. `brewzilla_safety_rcl.yaml` / `_sv.yaml` stays separate because it answers a different question: whether data/control is safe and healthy rather than what BA recommends.

## Brewfather reload placement

Use `cards/brewassistant_brewday_bf_reload.yaml` or `cards/brewassistant_brewday_bf_reload_sv.yaml` as an optional quick action near whichever BrewTracker/Brewday cards the user has chosen. Both call `brewassistant.force_brewfather_refresh`.

## Sanity dashboard

`brewassistant_sanity.yaml` is the canonical compact post-restart validation dashboard. `brewassistant_sanity_sv.yaml` provides the same diagnostic surface with Swedish presentation text.

The sanity dashboard is intentionally not switch-hidden, because it is meant for diagnostics even when the daily dashboard is collapsed.

## Frontend dependencies

Cards may use HACS frontend cards such as:

```text
custom:button-card
custom:vertical-stack-in-card
custom:mushroom-*
custom:expander-card
custom:gauge-card-pro
custom:bar-card
custom:apexcharts-card
```

Install required frontend cards before copying dashboard YAML into Home Assistant.

## Policy

```text
- English *.yaml files are the canonical dashboard source.
- Swedish *_sv.yaml files mirror presentation only.
- Keep entity IDs, service IDs, conditions and machine-state comparisons identical across languages.
- Do not translate machine values that backend logic or automations depend on.
- CI must fail if a canonical dashboard card lacks a Swedish mirror.
- CI must fail if a Swedish mirror introduces unexpected machine entity references or changes service/action references.
- Keep reusable functionality in standalone cards; personal composed stacks are not canonical implementation surfaces.
- Avoid storing every visual iteration in the repo.
- Put backend logic in Python, not in dashboard templates.
- Use dashboard YAML for presentation and explicit operator actions.
- Use BrewAssistant button entities for operator actions; avoid duplicate service-workaround paths.
- Use BrewAssistant dashboard visibility switches for daily dashboard show/hide.
- Prefer clean BrewAssistant entity IDs without local area/device prefixes.
```
