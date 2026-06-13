# Dashboard Card Baselines

This document records the current BrewAssistant dashboard/UI baseline used during the beta Home Assistant workflow.

The dashboard should remain presentation-focused. Runtime decisions, normalization, orchestration and safety checks belong in the Python integration. Lovelace cards may display state and call explicit operator actions, but they should not hide business logic.

## Current directory layout

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

The old plural `dashboards/` directory was removed during the clean baseline cleanup. The current source of truth is singular `dashboard/`.

## Current baseline cards

```text
BrewAssistant Hub
BrewAssistant Brewday Runtime
Brewday Event Log
Manual Brewday
Source Health
Brewfather Feed
BrewZilla
BrewZilla Learning
Carbonation
Fermentation
Kegerator
Sanity dashboard
```

## BrewAssistant Hub

File: `dashboard/cards/brewassistant_hub.yaml`

Purpose: provide a compact mission-control overview above the domain cards.

Current policy:

```text
- Show the major BrewAssistant domains in one compact overview.
- Show source/feed status as supporting status, not as a fifth primary workflow.
- Keep inactive/disconnected modules visually calm.
- Prioritize active cooling, active fermentation/cold-crash, active brewday and carbonation-ready states.
```

## Brewday Runtime

File: `dashboard/cards/brewassistant_brewday.yaml`

Purpose: operator-facing normalized runtime card for Brewfather-driven and manual brewday state.

Current policy:

```text
- Show normalized BrewAssistant runtime state, not raw Brewfather internals by default.
- Brewfather/BrewTracker and Manual Brewday should feed the same operator mental model.
- Keep direct hardware actions explicit and supervised.
- Debug/source details belong in expanders or source health cards.
```

## Brewday Event Log

File: `dashboard/cards/brewassistant_brewday_event_log.yaml`

Purpose: show event-log state, latest event information and explicit audit/log actions.

Current policy:

```text
- UI wording should say Event Log.
- Backend service names may still use brewday_audit_* for compatibility.
- Event count, latest event, latest step and latest target should be visible quickly.
- Clear/reset actions should require confirmation.
```

## Manual Brewday

File: `dashboard/cards/brewassistant_manual_brewday.yaml`

Purpose: operator controls for manual brewday runtime.

Current policy:

```text
- Manual controls should use the same visual family as other BrewAssistant cards.
- Manual Brewday is an operator runtime source, not a separate backend universe.
- Direct jumps such as Mash, Boil, Hopstand and Chill should require deliberate operator actions.
```

## Source Health

File: `dashboard/cards/brewassistant_source_health.yaml`

Purpose: compact source/feed/integration health overview.

Current policy:

```text
- Show whether expected feeds/entities are present and fresh.
- Keep this card diagnostic/supportive rather than workflow-primary.
- It is acceptable for this card to show installed-but-idle source state.
```

## Brewfather Feed

File: `dashboard/cards/brewfather_feed.yaml`

Purpose: show active Brewfather/BrewTracker feed state, runtime source, snapshot age and refresh controls.

Current policy:

```text
- Hide the main card when Brewfather/BrewTracker is not actively sending data.
- Installed/available source state may appear as a small badge/status elsewhere.
- Force Refresh is allowed as an explicit operator/debug action.
- Normal operation should rely on the smart Brewfather refresh policy.
```

## BrewZilla

File: `dashboard/cards/brewzilla.yaml`

Purpose: operator-facing hot-side BrewZilla orchestration card.

Current UI policy:

```text
- When BrewZilla is off/disconnected, the top card is enough.
- Apply/Deny and detailed BrewZilla controls should be hidden when BrewZilla is off.
- Gauge cards should be hidden when BrewZilla is off.
- The normal temperature gauge should be visible outside BOIL.
- The boil-specific gauge should be visible during BOIL.
- BrewZilla-specific hardware logic must remain in BrewZilla-specific backend code.
```

## BrewZilla Learning

File: `dashboard/cards/brewzilla_learning.yaml`

Purpose: advisory/learning view for BrewZilla heating and temperature behavior.

Current policy:

```text
- Treat learning output as advisory, not authoritative control.
- Prefer shared mash/wort resolver output instead of parsing raw hardware values in the card.
- Hide when there is no active/meaningful BrewZilla or brewday context.
```

## Kegerator

File: `dashboard/cards/kegerator.yaml`

Purpose: compact kegerator/cooling/fan-auto visibility.

Current UI policy:

```text
- Show compressor/fan/afterrun status from the Python kegerator fan backend.
- Use switch.brewassistant_kegerator_fan_auto_enabled attributes as the main fan-auto diagnostic source.
- Keep legacy kegerator YAML helpers out of the card.
- Do not let the card control compressor behavior directly; climate.kegerator_kylskap owns target/cooling behavior.
```

## Fermentation

File: `dashboard/cards/fermentation.yaml`

Purpose: show fermentation chamber state, supervisor state, Pill/gravity context and recommendations without making OFF state noisy.

Current UI policy:

```text
- OFF means climate.fermentation_chamber is off.
- OFF state should show only a compact top card.
- Idle means the chamber/supervisor is ready but no active fermentation or cold-crash scope exists.
- Active fermentation/cold-crash may show the full cockpit details.
- Pill/gravity values should be treated carefully; unrealistic SG values should not be emphasized.
- Current RAPT Pill gravity entity is sensor.yellow_pill_gravity.
```

## Carbonation

File: `dashboard/cards/carbonation.yaml`

Purpose: show carbonation runtime, target volumes, temperature, pressure recommendations and operator controls.

Current UI policy:

```text
- Use existing stable control entities without the _control suffix:
  - select.brewassistant_carbonation_method
  - number.brewassistant_carbonation_target_volumes
  - number.brewassistant_carbonation_start_volumes
  - number.brewassistant_carbonation_pressure_bar
- Use Python runtime sensors for display:
  - sensor.brewassistant_carbonation_status
  - sensor.brewassistant_carbonation_method
  - sensor.brewassistant_carbonation_target_volumes
  - sensor.brewassistant_carbonation_temperature
  - sensor.brewassistant_carbonation_recommended_pressure_bar
- Keep quick targets human-readable; avoid exposing internal entity IDs in labels.
- Show source labels as human-readable text, for example `kegerator temp` instead of raw entity IDs.
```

## Sanity dashboard

File: `dashboard/brewassistant_sanity.yaml`

Purpose: quick validation after Home Assistant restarts or BrewAssistant updates.

Current policy:

```text
- Keep it compact and boring.
- Focus on core version/module summary, kegerator guard/fan, event log and obvious runtime health.
- This is not the full brewing UI.
```

## Deferred UI polish

```text
- Add navigation/subviews after core cards stabilize.
- Decide final placement of source badges across Hub, Source Health and Brewfather Feed.
- Validate card visibility behavior with real Brewfather active/idle snapshots.
- Validate full fermentation/cold-crash card behavior during a real batch.
```
