# BrewAssistant dashboard

This directory contains the current dashboard card baseline for BrewAssistant Beta.

Dashboard files are examples/operator UI only. Runtime normalization, orchestration, safety checks and calculations live in the Python custom integration under `custom_components/brewassistant/`.

## Current structure

```text
dashboard/
  brewassistant_sanity.yaml
  cards/
    brewassistant_hub.yaml
    brewassistant_brewday.yaml
    brewassistant_brewday_bf_reload.yaml
    brewassistant_brewday_event_log.yaml
    brewassistant_manual_brewday.yaml
    brewassistant_source_health.yaml
    brewfather_feed.yaml
    brewzilla.yaml
    brewzilla_learning.yaml
    carbonation.yaml
    counterflow_chiller.yaml
    fermentation.yaml
    kegerator.yaml
```

## Hub replacement workflow

`cards/brewassistant_hub.yaml` is the daily mission-control card and should replace the existing BrewAssistant Hub card in the Home Assistant dashboard.

The Hub card exposes:

```text
switch.brewzilla
switch.brewassistant_show_brewday
switch.brewassistant_show_manual_brewday
switch.brewassistant_show_brewfather_feed
switch.brewassistant_show_brewzilla
switch.brewassistant_show_brewzilla_learning
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
| `brewassistant_brewday.yaml` | Normalized brewday runtime/operator card. |
| `brewassistant_brewday_bf_reload.yaml` | Compact Brewfather/BrewTracker reload button for placement on or near the Brewday Runtime card. |
| `brewassistant_brewday_event_log.yaml` | Brewday event log controls and latest-event diagnostics. |
| `brewassistant_manual_brewday.yaml` | Manual Brewday operator controls and runtime overview. |
| `brewassistant_source_health.yaml` | Source/feed health and integration status overview. |
| `brewfather_feed.yaml` | Brewfather/BrewTracker feed card; intended to be hidden when no active feed data exists. |
| `brewzilla.yaml` | BrewZilla orchestration/operator card. |
| `brewzilla_learning.yaml` | BrewZilla learning/advisory card. |
| `carbonation.yaml` | Carbonation runtime/status/control card. |
| `counterflow_chiller.yaml` | Counter Flow Chiller sanitation/ready controls. |
| `fermentation.yaml` | Fermentation chamber/Pill/smart recommendation cockpit. |
| `kegerator.yaml` | Kegerator fan, guard and cooling visibility card. |

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
- Use BrewAssistant dashboard visibility switches for daily dashboard show/hide.
- Prefer clean BrewAssistant entity IDs without local area/device prefixes.
```
