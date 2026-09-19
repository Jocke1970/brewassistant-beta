# BrewAssistant 0.2.0-beta.9

Status: **prerelease candidate / physical validation incomplete**

Beta.9 consolidates the supervised Heatstrike/Mash-In controller, Brewfather handoff hardening, RCL freshness/recovery fixes, operator-facing BrewZilla/BrewTracker UI work and the three-branch promotion workflow.

This remains a supervised beta. It is not an unattended brewing-control release.

## Hot-side / Heatstrike

### Heatstrike gradient relief — PR #197 + 2026-09-06 refinement

Physical water-only runs showed a repeatable pre-mash gradient where the external MASH/BLE process probe remained below strike while BrewZilla internal/WORT was already above strike.

Current contract:

```text
normal hottest-view overshoot > +0.5 °C
  -> explicit safe-down remains the default

narrow pre-mash gradient exception:
  MASH/BLE still below strike
  real mash/wort gradient >= 1.5 °C
  hottest-view overshoot > +0.5 °C and <= +2.0 °C

  -> local thermostat remains available
  -> heat authority capped at 5 %
  -> pump forced to 100 % for equalization

hottest-view overshoot > +2.0 °C
  -> heat 0 % / heater OFF hard stop remains authoritative
```

The wider +2.0 °C span is gradient-only. It is not a general Mash-In READY tolerance or generic overshoot allowance.

## Mash-In pump hold / Brewfather handoff — PR #202 follow-ups

Mash-In is a one-way physical handoff:

```text
READY
  -> Mash-In Started
  -> strike target releases toward actual mash target
  -> pump OFF / utilization 0 %
  -> grain addition / stirring
  -> BA must observe Brewfather PAUSED after Mash-In Started
  -> later Brewfather RUNNING / Continue
  -> Mash-In Complete
  -> normal mash circulation resumes
```

The following are **not** automatic completion evidence by themselves:

```text
BF already running when Mash-In Started is pressed
active Brewfather mash target changing
normalized BA runtime remaining live/running
```

The 2026-09-06 second field run produced positive backend evidence for the strict post-start `PAUSED -> RUNNING` handoff. The remaining issue from that run is UI observability: completion was not visually obvious enough before the operator aborted the test.

## RAPT Cloud Link freshness / active polling

The same 2026-09-06 run exposed a separate freshness-semantics bug.

BrewAssistant had mixed:

```text
report freshness
  = when Home Assistant last received/reported the entity

value age
  = when the state/attributes last actually changed
```

A stable temperature or target could therefore look stale even when RCL continued reporting the same value. In one path the value-age clock also replaced canonical process-temperature freshness, allowing fail-passive to block new BA writes simply because a physical value had not changed enough.

Beta.9 now separates the concepts:

```text
control/report freshness
  -> entity last_reported, fallback last_updated
  -> used for orchestration/fail-passive trust

value stagnation
  -> last_updated + explicit change tracking
  -> diagnostics only

active hot-side refresh
  -> one BrewZilla CoordinatorEntity
  -> homeassistant.update_entity
  -> real DataUpdateCoordinator async_request_refresh()
  -> every 30 seconds while Brewday owns an active hot-side phase
```

Only one coordinator-backed entity is used as the refresh trigger to avoid duplicate cloud-fetch fan-out. Disruptive `reload_config_entry` remains reserved for hard connection loss/extreme report staleness and retains a 15-minute minimum interval.

The RCL patch has regression coverage but still requires a fresh physical run.

## Operator UI

### BrewTracker phase visibility

```text
Planning   -> visible, no hot-side ownership
Pre-start  -> visible, no hot-side ownership
Brewing    -> ownership only after positive tracker-start evidence
```

The runtime cockpit remains the authoritative operator view; raw Brewfather state must not imply hardware authority by itself.

### Temperature gauge

The existing `gauge-card-pro` dual-temperature card remains the current baseline.

A BrewAssistant-specific SVG/JavaScript pilot now exists for the **pre-boil** temperature instrument only:

```text
dashboard/js/brewassistant-temperature-gauge.js
dashboard/cards/brewzilla_temperature_gauge_js.yaml
dashboard/cards/brewzilla_temperature_gauge_js_sv.yaml
```

The pilot gives Mash and Wort exact shared needle geometry and explicit target/tolerance presentation. It is not yet the canonical replacement and should remain side-by-side/optional until physically and visually validated.

## Repository watchdogs

Beta.9 includes:

- Python compile checks
- fatal Ruff checks
- integration JSON validation
- pytest on Python 3.11, 3.12 and 3.13
- HACS Action
- Hassfest
- daily Dependabot checks

The 2026-09-06 RCL regression tests pass. HACS and Hassfest also pass on the current code checkpoint.

Known repository debt before promotion: dashboard EN/SV content parity still reports existing drift in `brewassistant_brewday.yaml` vs `_sv.yaml`. The JS gauge filename mirror is fixed in the parking sync, but the older cockpit parity drift still needs a deliberate UI sync. Do not promote while CI is red.

## Development / release workflow

The repository uses three long-lived branches:

```text
dev -> beta -> main -> GitHub Release
```

- `dev`: active development
- `beta`: integrated field-test candidate
- `main`: installable/runnable version
- releases are created only from `main`

Promotion PRs use **Create a merge commit**.

## Physical validation still required

Before beta.9 is physically proven through the Mash-In boundary:

```text
[ ] active hot-side RCL report freshness remains bounded under 30 s refresh requests
[ ] stable physical values do not create false stale/fail-passive blocks
[ ] 5 % / 100 % gradient relief converges MASH/BLE safely
[ ] > +2.0 °C hottest-view overshoot still hard-stops heat
[ ] Mash-In Started holds pump OFF / 0 % for the full grain-addition window
[ ] post-start BF PAUSED is observed before later RUNNING completion
[ ] target becomes the actual mash target after Mash-In Started
[ ] normal mash circulation resumes only after Mash-In Complete
[ ] Mash-In completion becomes immediately obvious in the operator UI
[ ] 66 °C physical hold starts only on real target reach
[ ] 66 -> 72 °C physical ramp/next hold behavior is validated
```

See:

- `docs/physical-validation-2026-09-05.md`
- `docs/physical-validation-2026-09-06.md`
- `docs/parking-checkpoint-2026-09-06.md`

## Release note

When the candidate has passed intended `beta` validation and is promoted to `main`, create GitHub prerelease:

```text
v0.2.0-beta.9
```

from the promoted `main` commit.
