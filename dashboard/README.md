# BrewAssistant dashboard

This directory contains the current dashboard baseline for BrewAssistant Beta.

Dashboard files are examples/operator UI only. Runtime normalization, orchestration, safety checks and calculations live in the Python custom integration under `custom_components/brewassistant/`.

## Current structure

```text
dashboard/
  brewassistant_sanity.yaml
  cards/
    brewassistant_hub.yaml
    brewassistant_brewday.yaml
    brewassistant_brewday_event_log.yaml
    brewassistant_manual_brewday.yaml
    brewassistant_source_health.yaml
    brewfather_feed.yaml
    brewzilla.yaml
    brewzilla_learning.yaml
    carbonation.yaml
    fermentation.yaml
    kegerator.yaml
```

## Cards

| File | Purpose |
| --- | --- |
| `brewassistant_hub.yaml` | Compact mission-control overview for the major BrewAssistant domains. |
| `brewassistant_brewday.yaml` | Normalized brewday runtime/operator card. |
| `brewassistant_brewday_event_log.yaml` | Brewday event log controls and latest-event diagnostics. |
| `brewassistant_manual_brewday.yaml` | Manual Brewday operator controls and runtime overview. |
| `brewassistant_source_health.yaml` | Source/feed health and integration status overview. |
| `brewfather_feed.yaml` | Brewfather/BrewTracker feed card; intended to be hidden when no active feed data exists. |
| `brewzilla.yaml` | BrewZilla orchestration/operator card. |
| `brewzilla_learning.yaml` | BrewZilla learning/advisory card. |
| `carbonation.yaml` | Carbonation runtime/status/control card. |
| `fermentation.yaml` | Fermentation chamber/Pill/smart recommendation cockpit. |
| `kegerator.yaml` | Kegerator fan, guard and cooling visibility card. |

## Sanity dashboard

`brewassistant_sanity.yaml` is a compact post-restart validation dashboard. It is intended for quick checks after updating Home Assistant or the BrewAssistant integration.

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
- Prefer clean BrewAssistant entity IDs without local area/device prefixes.
```
