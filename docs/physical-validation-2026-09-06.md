# Physical validation — 2026-09-06

Scope: supervised BrewAssistant / BrewZilla hot-side water-only validation on `dev`, focused on the final Heatstrike approach before Mash-In.

## Observed field state

The final Heatstrike approach again showed a meaningful difference between the operator-facing mash/BLE process probe and the BrewZilla internal/wort view.

Representative snapshot:

```text
strike target        71.8 °C
MASH/BLE              69.1 °C
BrewZilla internal    73.36 °C
MASH below strike     2.7 °C
internal overshoot    1.56 °C
```

At that point the previous clean Heatstrike guard selected:

```text
heat 0 %
pump 90 %
phase clean_safety_overshoot_stop
```

The process probe therefore still needed roughly 2.7 °C while the hotter internal view had already crossed the old +1.5 °C hard boundary.

RCL/BrewZilla telemetry around the same final-approach window was typically tens of seconds old (roughly 10–67 s in captured snapshots). This is not treated as proof that more `update_entity` calls will produce fresher cloud telemetry; the controller should instead tolerate bounded telemetry latency without becoming needlessly aggressive.

## Heatstrike refinement

The bounded gradient-relief rule is tightened in power but widened slightly in temperature span:

```text
MASH/BLE still below strike
AND real mash/wort gradient >= 1.5 °C
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +2.0 °C

=> heat authority cap 5 %
=> heater master remains available to BrewZilla local regulation
=> pump utilization 100 % for equalization
```

Hard boundary:

```text
hottest-view overshoot > +2.0 °C
=> heat 0 % / heater OFF remains authoritative
```

This is deliberately not a wider Mash-In READY tolerance. READY continues to depend on the process probe reaching its own readiness band.

## UI observations

The same field run identified presentation cleanup in the Swedish operator view:

- `Fas`, `Steg`, `Nästa`, `Åtgärd` and `Styrning` must wrap rather than truncate operational text.
- BrewTracker status is already visible in the runtime header/chip, so the separate `BrewTracker-status` button is redundant.
- The remaining Brewfather refresh control should use the full row.
- The dual-temperature gauge should make the active strike target more explicit in its secondary text.
- The gauge right-side status icon is left at the component's native `icons.right` position for now; moving it requires brittle shadow-DOM styling and is not worth risking another needle/layout regression.

## Validation status

This run provides evidence for the Heatstrike final-approach refinement, but it does not by itself promote `dev` to `beta`.

Next physical checkpoint remains the complete sequence:

```text
Heatstrike
-> READY
-> Mash-In Started
-> pump OFF / 0 %
-> Brewfather PAUSED observed after Mash-In Started
-> Brewfather Continue / RUNNING
-> Mash-In Complete
-> normal mash circulation resumes
```
