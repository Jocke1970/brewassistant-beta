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

Examples:

```text
cards/brewzilla.yaml       -> canonical English UI
cards/brewzilla_sv.yaml    -> Swedish UI
cards/fermentation.yaml    -> canonical English UI
cards/fermentation_sv.yaml -> Swedish UI
```

When adding or materially changing a canonical dashboard card, update its `_sv.yaml` mirror in the same development pass whenever practical.

## Current structure

```text
dashboard/
  brewassistant_sanity.yaml
  brewassistant_sanity_sv.yaml
  cards/
    brewassistant_hub.yaml
    brewassistant_hub_sv.yaml
    brewassistant_visibility_badges.yaml
    brewassistant_visibility_badges_sv.yaml
    brewassistant_brewday.yaml
    brewassistant_brewday_sv.yaml
    brewassistant_brewday_bf_reload.yaml
    brewassistant_brewday_bf_reload_sv.yaml
    brewassistant_brewday_event_log.yaml
    brewassistant_brewday_event_log_sv.yaml
    brewassistant_manual_brewday.yaml
    brewassistant_manual_brewday_sv.yaml
    brewassistant_source_health.yaml
    brewassistant_source_health_sv.yaml
    brewfather_feed.yaml
    brewfather_feed_sv.yaml
    brewfather_recipe.yaml
    brewfather_recipe_sv.yaml
    brewtracker_runtime.yaml
    brewtracker_runtime_sv.yaml
    brewzilla.yaml
    brewzilla_sv.yaml
    brewzilla_mash_in_confirm.yaml
    brewzilla_mash_in_confirm_sv.yaml
    brewzilla_mash_in_controls.yaml
    brewzilla_mash_in_controls_sv.yaml
    brewzilla_local_control.yaml
    brewzilla_local_control_sv.yaml
    brewzilla_advice_auto.yaml
    brewzilla_advice_auto_sv.yaml
    brewzilla_safety_rcl.yaml
    brewzilla_safety_rcl_sv.yaml
    brewzilla_learning.yaml
    brewzilla_learning_sv.yaml
    carbonation.yaml
    carbonation_sv.yaml
    counterflow_chiller.yaml
    counterflow_chiller_sv.yaml
    fermentation.yaml
    fermentation_sv.yaml
    kegerator.yaml
    kegerator_sv.yaml
```

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

## Cards

Every card listed below has a matching `_sv.yaml` presentation mirror.

| Canonical file | Purpose |
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
| `brewzilla_mash_in_confirm.yaml` | Legacy mash-in confirmation and explicit mash-circulation action card. |
| `brewzilla_mash_in_controls.yaml` | Two-step mash-in operator controls: Mash-In Started, then Mash-In Complete. |
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

`brewfather_feed.yaml` remains for compatibility while the split cards are tested. The same split is preserved in the Swedish mirrors.

## BrewZilla two-step mash-in controls

`cards/brewzilla_mash_in_controls.yaml` is the canonical operator card for the mash-in handoff; `cards/brewzilla_mash_in_controls_sv.yaml` is the Swedish presentation mirror.

Expected flow:

```text
1. BrewAssistant detects mash-in/strike readiness.
2. Only button.brewassistant_mash_in_started is visible.
3. Operator starts adding malt and presses Mash-In Started.
4. BA releases strike target toward the next mash target, keeps pump OFF and allows low anti-drop heat.
5. Only button.brewassistant_mash_in_complete is visible.
6. Operator finishes stirring/settling the malt bed and presses Mash-In Complete.
7. BA starts mash circulation using pump utilization 50 % plus pump switch.
8. Both mash-in buttons disappear.
```

Entities used:

```text
button.brewassistant_mash_in_started
button.brewassistant_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
```

The legacy `cards/brewzilla_mash_in_confirm.yaml` remains for compatibility during migration, but the two-step card should be used for realistic 69°C strike / 66°C mash-in tests.

The fallback `Starta mäskcirkulation` button in the Swedish UI is intentionally explicit. It calls the same BrewAssistant button entity as the canonical UI and must not be replaced with a duplicate service workaround.

## BrewZilla local-control split

The intended split is:

```text
BrewZilla = operator/hardware cockpit
BrewZilla Mash-In Controls = explicit two-step mash-in handoff
BrewZilla Local Control = what BA handed to BZ and whether lease is active
Brewday Advice = why BA selected a profile; hidden by default unless meaningful
Safety/RCL = freshness/guards/filter/abort; hidden by default unless meaningful
```

`brewzilla_advice_auto.yaml` and `brewzilla_safety_rcl.yaml`, and their Swedish mirrors, use card-level display rules: they stay hidden during normal operation, but appear when there is a recommendation, warning, missing context, guard activity, or when the matching switch is enabled.

## Brewfather reload placement

Use `cards/brewassistant_brewday_bf_reload.yaml` or `cards/brewassistant_brewday_bf_reload_sv.yaml` as a quick action on or directly below the Brewday Runtime card. Both call `brewassistant.force_brewfather_refresh`.

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
- Keep only the current approved card baseline in dashboard/cards/.
- Avoid storing every visual iteration in the repo.
- Put backend logic in Python, not in dashboard templates.
- Use dashboard YAML for presentation and explicit operator actions.
- Use BrewAssistant button entities for operator actions; avoid duplicate service-workaround paths.
- Use BrewAssistant dashboard visibility switches for daily dashboard show/hide.
- Prefer clean BrewAssistant entity IDs without local area/device prefixes.
```
