# BrewAssistant dashboard

This directory contains the current dashboard card baseline for BrewAssistant Beta.

Dashboard files are examples/operator UI only. Runtime normalization, orchestration, safety checks and calculations live in the Python custom integration under `custom_components/brewassistant/`.

## Current structure

```text
dashboard/
  brewassistant_sanity.yaml
  cards/
    brewassistant_hub.yaml
    brewassistant_visibility_badges.yaml
    brewassistant_brewday.yaml
    brewassistant_brewday_bf_reload.yaml
    brewassistant_brewday_event_log.yaml
    brewassistant_manual_brewday.yaml
    brewassistant_source_health.yaml
    brewfather_feed.yaml
    brewfather_recipe.yaml
    brewtracker_runtime.yaml
    brewzilla.yaml
    brewzilla_mash_in_confirm.yaml
    brewzilla_local_control.yaml
    brewzilla_advice_auto.yaml
    brewzilla_safety_rcl.yaml
    brewzilla_learning.yaml
    carbonation.yaml
    counterflow_chiller.yaml
    fermentation.yaml
    kegerator.yaml
```

## Hub replacement workflow

`cards/brewassistant_hub.yaml` is the daily mission-control card and should replace the existing BrewAssistant Hub card in the Home Assistant dashboard.

The Hub card exposes the main daily module toggles. Advanced diagnostic toggles can also be placed as compact badges using `cards/brewassistant_visibility_badges.yaml`.

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

## Cards

| File | Purpose |
| --- | --- |
| `brewassistant_hub.yaml` | Compact mission-control overview with module visibility switches and BrewZilla main power. |
| `brewassistant_visibility_badges.yaml` | Compact toggle badges for advanced Brewday Advice and Safety/RCL cards. |
| `brewassistant_brewday.yaml` | Normalized brewday runtime/operator card. |
| `brewassistant_brewday_bf_reload.yaml` | Compact Brewfather/BrewTracker reload button for placement on or near the Brewday Runtime card. |
| `brewassistant_brewday_event_log.yaml` | Brewday event log controls and latest-event diagnostics. |
| `brewassistant_manual_brewday.yaml` | Manual Brewday operator controls and runtime overview. |
| `brewassistant_source_health.yaml` | Source/feed health and integration status overview. |
| `brewfather_feed.yaml` | Legacy combined Brewfather/BrewTracker feed card. |
| `brewfather_recipe.yaml` | Brewfather recipe/batch/instruction card. |
| `brewtracker_runtime.yaml` | BrewTracker live runtime card with current step, next step, batch status, progress and refresh action. |
| `brewzilla.yaml` | BrewZilla orchestration/operator card. |
| `brewzilla_mash_in_confirm.yaml` | Mash-in confirmation and explicit mash-circulation action card. |
| `brewzilla_local_control.yaml` | BrewZilla local regulator handoff card: target, lease, heat profile and pump profile. |
| `brewzilla_advice_auto.yaml` | Brewday Advice conditional card; auto-shows on advice/risk/unknown context or by switch. |
| `brewzilla_safety_rcl.yaml` | Safety/RCL conditional card; auto-shows on warning/guard/filter/abort or by switch. |
| `brewzilla_learning.yaml` | Full BrewZilla learning/advisory card for deep manual review. |
| `carbonation.yaml` | Carbonation runtime/status/control card. |
| `counterflow_chiller.yaml` | Counter Flow Chiller sanitation/ready controls. |
| `fermentation.yaml` | Fermentation chamber/Pill/smart recommendation cockpit. |
| `kegerator.yaml` | Kegerator fan, guard and cooling visibility card. |

## Brewfather / BrewTracker split

The intended split is:

```text
Brewfather Recipe = recipe, batch, current/next instructions
BrewTracker Runtime = current live step, next step, batch status, target, remaining time, progress, refresh
```

`brewfather_feed.yaml` remains for compatibility while the split cards are tested.

## BrewZilla mash-in confirmation

`cards/brewzilla_mash_in_confirm.yaml` is the explicit operator card for the mash-in handoff.

Expected flow:

```text
1. BrewAssistant detects mash-in target reached.
2. BrewAssistant exposes binary_sensor.brewassistant_brewzilla_mash_in_gate_pending = on.
3. The conditional Mash-in button is shown.
4. Operator mashes in manually.
5. Operator presses button.brewassistant_brewzilla_mash_in_complete.
6. BrewAssistant marks the gate complete and starts mash circulation using pump utilization plus pump switch.
```

Entities used:

```text
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_brewzilla_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
```

The fallback `Starta mäskcirkulation` button is intentionally explicit. It sets mash pump utilization and turns the pump on through the BrewAssistant button entity. It should not be replaced with duplicate service workarounds.

## BrewZilla local-control split

The intended split is:

```text
BrewZilla = operator/hardware cockpit
BrewZilla Mash-In Confirm = explicit mash-in completion and circulation action
BrewZilla Local Control = what BA handed to BZ and whether lease is active
Brewday Advice = why BA selected a profile; hidden by default unless meaningful
Safety/RCL = freshness/guards/filter/abort; hidden by default unless meaningful
```

`brewzilla_advice_auto.yaml` and `brewzilla_safety_rcl.yaml` use card-level display rules: they stay hidden during normal operation, but appear when there is a recommendation, warning, missing context, guard activity, or when the matching switch is enabled.

## Brewfather reload placement

Use `cards/brewassistant_brewday_bf_reload.yaml` as a quick action on or directly below the Brewday Runtime card. It calls `brewassistant.force_brewfather_refresh` so the operator can refresh Brewfather/BrewTracker immediately after starting a brew in Brewfather, instead of waiting for the normal refresh policy interval.

## Sanity dashboard

`brewassistant_sanity.yaml` is a compact post-restart validation dashboard. It is intended for quick checks after updating Home Assistant or the BrewAssistant integration.

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
- Keep only the current approved card baseline in dashboard/cards/.
- Avoid storing every visual iteration in the repo.
- Put backend logic in Python, not in dashboard templates.
- Use dashboard YAML for presentation and explicit operator actions.
- Use BrewAssistant button entities for operator actions; avoid duplicate service-workaround paths.
- Use BrewAssistant dashboard visibility switches for daily dashboard show/hide.
- Prefer clean BrewAssistant entity IDs without local area/device prefixes.
```
