# Dashboard Card Baselines

This document records the current BrewAssistant dashboard/UI baselines used during the beta Home Assistant workflow.

The dashboard should remain presentation-focused. Runtime decisions, normalization, orchestration and safety checks belong in the Python integration. Lovelace cards may display state and call explicit operator actions, but they should not hide business logic.

## Current baseline cards

```text
BrewAssistant Hub v1.3
BrewZilla Brew Day Card v1.4-style baseline
Kegerator Card v1.2 Safe
Fermentation Cockpit v1.2 OFF Minimal
Carbonation Cockpit v1.2 Polish
```

## BrewAssistant Hub

Purpose: provide a compact mission-control overview above the domain cards.

Current layout:

```text
BrewZilla     | Fermentation
Carbonation   | Kegerator
```

Current policy:

```text
- Brewfather/runtime source is shown as a small source strip, not as a fifth primary module.
- BrewZilla disconnected/blocked should stay visually neutral when no active brewday is running.
- Kegerator cooling/afterrun should be prioritized when it is actively doing work.
- Carbonation ready should be high-priority.
- Fermentation active/cold-crash states should be high-priority.
```

## BrewZilla Brew Day Card

Purpose: operator-facing hot-side brewday card.

Current UI policy:

```text
- Gauge Pro is only shown when BrewZilla power is above the idle threshold.
- When BrewZilla is off/disconnected, the top card is enough.
- Manual Brewday visibility versus Brewfather-driven runtime is deferred to final UI polish.
```

Recommended conditional for Gauge Pro display:

```yaml
conditions:
  - condition: numeric_state
    entity: sensor.brewzilla_power
    above: 1
```

## Kegerator Card

Purpose: compact kegerator/cooling/fan-auto visibility.

Current UI policy:

```text
- Show compressor/fan/afterrun status from the Python kegerator fan backend.
- Use switch.brewassistant_kegerator_fan_auto_enabled attributes as the main fan-auto diagnostic source.
- Keep legacy kegerator YAML helpers out of the card.
- Do not let the card control compressor behavior directly; climate.kegerator_kylskap owns target/cooling behavior.
```

## Fermentation Cockpit

Purpose: show fermentation chamber state, supervisor state, Pill/gravity context and recommendations without making OFF state noisy.

Current UI policy:

```text
- OFF means climate.fermentation_chamber is off.
- OFF state should show only a compact top card.
- Idle means the chamber/supervisor is ready but no active fermentation or cold-crash scope exists.
- Active fermentation/cold-crash may show the full cockpit details.
- Pill/gravity values should be treated carefully; unrealistic SG values should not be emphasized.
```

## Carbonation Cockpit

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
```

## Deferred final UI polish

```text
- Manual Brewday should probably be hidden when Brewfather Brew Tracker owns the runtime.
- Dashboard navigation/subviews should be added after core cards stabilize.
- Source health / diagnostics card should come before final navigation polish.
- Fermentation cleanup can remain separate from UI polish and should be handled carefully.
```
