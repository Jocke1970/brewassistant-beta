# Parking checkpoint — 2026-09-06

Purpose: capture the exact BrewAssistant state before a pause in physical testing so the next session can resume without reconstructing the 2026-09-06 investigation.

## Branch / promotion state

Work remains on:

```text
dev
```

Do **not** promote to `beta` yet.

The code checkpoint before this documentation parking sync includes the RCL freshness/polling fixes:

```text
4d0e09ea2a8057f88dccc88e530dce43bc81eeb6
  fix: separate RCL report freshness from value age

5486446e68b0dbc84af575c14e74689e24911e6d
  fix: keep RCL value stagnation separate from freshness

257e2ee4954ba25913d135712d35f1a31157cf3e
  fix: actively refresh RCL during hot-side control
```

Use the latest `dev` head when resuming; documentation commits after those code commits do not change the physical-control implementation.

## What the second 2026-09-06 test proved

The apparent Mash-In failure was not a backend state-machine failure.

Flight Recorder evidence showed:

```text
Mash-In Started
-> Brewfather PAUSED observed after the boundary
-> Brewfather RUNNING observed
-> mash_in_complete
-> target released to 66.0 °C
-> pump utilization 50 %
-> pump ON
```

The operator ABORT happened roughly 25 seconds later.

Conclusion:

```text
Mash-In backend handoff = positive evidence
Mash-In UI observability = needs improvement
```

The strict automatic completion contract remains:

```text
post-start BF PAUSED
THEN later BF RUNNING / Continue
```

Neither an already-running BF state nor active-target movement is sufficient by itself.

## Heatstrike contract at parking time

Current bounded gradient-relief rule:

```text
MASH/BLE still below strike
AND mash/wort gradient >= 1.5 °C
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +2.0 °C

=> heat authority cap 5 %
=> heater master remains available
=> pump 100 %
```

Above +2.0 °C hottest-view overshoot:

```text
heat 0 % / heater OFF hard stop
```

READY remains a separate process-probe/operator gate; the +2.0 °C limit is not a READY tolerance.

## RCL root cause and fix

The investigation found that BrewAssistant had mixed:

```text
last_reported
  = report/transport freshness

last_updated
  = state/attribute value-change age
```

A stable value could therefore be misclassified as stale. One Heatstrike value-stagnation guard also replaced canonical process-temperature freshness with value age, so fail-passive could trigger merely because a temperature had not changed enough.

Current fixed semantics:

```text
control/report freshness
  -> last_reported, fallback last_updated

value stagnation
  -> last_updated + explicit change tracking
  -> diagnostics only

active hot-side RCL refresh
  -> every 30 seconds
  -> one BrewZilla CoordinatorEntity
  -> homeassistant.update_entity
  -> DataUpdateCoordinator.async_request_refresh()

hard config-entry reload
  -> hard connection loss/extreme report staleness only
  -> 15-minute minimum interval
```

Important: `homeassistant.update_entity` on the RCL CoordinatorEntity is a real coordinator refresh request; it is not merely a cosmetic HA state update.

## What still needs physical validation

Next physical run should verify, in this order:

```text
1. active RCL polling diagnostics become active
2. coordinator refresh requests occur on the 30 s cadence
3. report freshness remains bounded even when numeric values stay stable
4. false process_temperature_stale/fail-passive does not appear from stability alone
5. Heatstrike final approach remains responsive
6. 5 % / 100 % gradient relief converges safely when needed
7. > +2.0 °C hottest-view overshoot still hard-stops heat
8. READY
9. Mash-In Started -> target becomes actual mash target
10. pump OFF / 0 % during grain addition
11. post-start BF PAUSED observed
12. BF Continue / RUNNING
13. Mash-In Complete
14. normal mash circulation resumes
15. completion is immediately obvious in the UI
```

If practical, continue into:

```text
66 °C physical hold
-> hold timer starts only at ±0.3 °C and after Mash-In Complete
-> 66 -> 72 °C physical ramp
-> next hold begins only on target reach
```

## RCL diagnostics to inspect

Useful orchestration attributes:

```text
rcl_active_hot_side_polling_active
rcl_active_hot_side_poll_interval_seconds
rcl_active_hot_side_poll_requested
rcl_active_hot_side_poll_recently_requested
rcl_active_hot_side_poll_entity_ids
rcl_active_hot_side_poll_last_requested_at
rcl_active_hot_side_poll_last_reason
rcl_active_hot_side_poll_error

rcl_active_hot_side_recovery_active
rcl_active_hot_side_recovery_reason
rcl_value_stale_guard_active
rcl_value_stale_guard_refresh_delegated
fail_passive_mode
```

Expected active trigger entity is normally:

```text
sensor.brewzilla_temperature
```

## UI state at parking time

A BrewAssistant-specific JS/SVG temperature gauge pilot exists for the **pre-boil gauge only**:

```text
dashboard/js/brewassistant-temperature-gauge.js
dashboard/cards/brewzilla_temperature_gauge_js.yaml
dashboard/cards/brewzilla_temperature_gauge_js_sv.yaml
```

The pilot is promising but not yet canonical. The existing `gauge-card-pro` card remains available.

Potential future direction, after current physical validation:

```text
Python backend
-> normalized HA entities/state
-> BrewAssistant JS cards for complex UI
-> thin YAML wrappers/config
```

Do not turn a full YAML-to-JS migration into beta.9 scope during the test pause.

## Repository health at parking time

RCL-specific regression tests pass across the tested Python matrix. HACS validation and Hassfest pass for the current checkpoint.

General CI is still red because of known dashboard EN/SV **content parity** drift in the main Brewday cockpit. The new JS gauge previously added only an `_sv.yaml` wrapper; this parking sync adds the missing English mirror so that newly introduced filename mismatch is removed.

Remaining parity debt:

```text
dashboard/cards/brewassistant_brewday.yaml
vs
dashboard/cards/brewassistant_brewday_sv.yaml
```

The Swedish card currently exposes machine entity/action references not mirrored by the canonical English card. Fix this deliberately before `dev -> beta`; do not weaken the parity tests.

## Resume checklist

When physical testing resumes:

```text
[ ] install latest dev into /config/custom_components/brewassistant
[ ] restart Home Assistant
[ ] confirm JS resource only if the pilot gauge will be used
[ ] clear/rearm old ABORT state as appropriate through normal operator controls
[ ] start a fresh Flight Recorder/Brewday test session
[ ] capture the full RCL + Heatstrike + Mash-In sequence
[ ] compare backend events with UI presentation before judging a handoff failure
```

Primary references:

- `docs/physical-validation-2026-09-06.md`
- `docs/brewday-brewzilla.md`
- `docs/backends/brewzilla-backend.md`
- `custom_components/brewassistant/brewzilla/README.md`
- `docs/beta9-release-notes.md`
- `docs/roadmap.md`
