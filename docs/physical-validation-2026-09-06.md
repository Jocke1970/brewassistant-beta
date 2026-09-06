# Physical validation — 2026-09-06

Scope: supervised BrewAssistant / BrewZilla hot-side water-only validation on `dev`, focused on Heatstrike, Mash-In handoff and RAPT Cloud Link freshness.

## First field run — Heatstrike final approach

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

## Second field run — Mash-In handoff

The later run initially looked like BrewAssistant had failed to release Mash-In when Brewfather resumed. Flight Recorder evidence shows that the backend handoff itself completed correctly:

```text
Mash-In Started
-> Brewfather PAUSED observed after the boundary
-> Brewfather RUNNING observed
-> mash_in_complete
-> target released to 66.0 °C
-> pump utilization 50 %
-> pump ON
```

The operator ABORT occurred roughly 25 seconds after that automatic completion. The remaining Mash-In issue is therefore presentation/observability: the UI did not make the successful backend transition obvious enough during the physical run.

## RCL freshness root cause

The second run exposed a separate RAPT Cloud Link freshness problem that was already present before Mash-In.

RCL uses a Home Assistant `DataUpdateCoordinator` with a normal default poll interval of three minutes. BrewAssistant, however, had mixed two different concepts:

```text
report freshness
  = when Home Assistant last received/reported the entity

value age
  = when the state/attributes last actually changed
```

Several BrewAssistant RCL diagnostics called `last_updated`-based value age a poll/freshness age. A stable target or temperature could therefore look many minutes old even when RCL had continued reporting it. More importantly, the RCL value-stale Heatstrike guard temporarily replaced canonical process-temperature freshness with value age. The fail-passive guard could then block new BA writes after 90 seconds simply because a physical temperature had not changed enough.

Home Assistant `CoordinatorEntity` handling confirms that `homeassistant.update_entity` is a real coordinator refresh request: it calls the entity coordinator's `async_request_refresh()`. The problem was therefore not that BA lacked a refresh mechanism; it was that freshness semantics and refresh cadence were wrong.

The `dev` fix establishes three separate concepts:

```text
control/report freshness
  -> last_reported, fallback last_updated
  -> used by orchestration and fail-passive control trust

value stagnation
  -> last_updated plus explicit temperature-change tracking
  -> diagnostics only; does not redefine canonical freshness

active hot-side RCL refresh
  -> one BrewZilla CoordinatorEntity via update_entity
  -> every 30 seconds while Brewday owns an active hot-side phase
  -> one coordinator trigger only, avoiding duplicate cloud refresh fan-out
```

Disruptive `reload_config_entry` recovery remains separate and throttled to hard connection loss/extreme report staleness, with a 15-minute minimum interval.

## UI observations

The field runs identified presentation cleanup in the Swedish operator view:

- `Fas`, `Steg`, `Nästa`, `Åtgärd` and `Styrning` must wrap rather than truncate operational text.
- BrewTracker status is already visible in the runtime header/chip, so the separate `BrewTracker-status` button is redundant.
- The remaining Brewfather refresh control should use the full row.
- The dual-temperature gauge is being prototyped as a BrewAssistant-specific SVG/JavaScript card so Mash and Wort share exact geometry and target/tolerance bands can be presented explicitly.
- Mash-In completion needs a clearer visual transition so a successful `paused -> running -> mash_in_complete` backend handoff is immediately obvious to the operator.

## Validation status

The Mash-In state-machine contract now has positive physical evidence for the strict post-start Brewfather `PAUSED -> RUNNING` handoff. The RCL report-freshness/active-refresh patch still requires a fresh physical validation before `dev` can be considered for promotion.

Next checkpoint:

```text
active hot-side run
-> RCL report age remains bounded by active refresh cadence
-> Heatstrike final approach remains responsive
-> READY
-> Mash-In Started
-> pump OFF / 0 %
-> Brewfather PAUSED observed after Mash-In Started
-> Brewfather Continue / RUNNING
-> Mash-In Complete
-> target becomes mash target
-> normal mash circulation resumes
```
