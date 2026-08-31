# Roadmap

This document outlines the BrewAssistant beta roadmap.

BrewAssistant continues to move runtime state, process interpretation, safety guards and hardware decisions into the Python custom integration under `custom_components/brewassistant/`.

```text
Python integration = source of truth for runtime/control/safety
Dashboard YAML      = presentation + explicit operator actions
```

---

## Current project status

### Current phase

```text
BrewZilla supervised hot-side baseline
↓
Water-only regression retest after #173 + physical timing validation #157
↓
First supervised real-mash BrewZilla validation
↓
BrewZilla Equipment Learning timing/profile advisor evidence pass
↓
Boil / hop validation + external-temperature ownership release
↓
CFC Chill / Transfer ownership handoff validation
↓
RAPT Cloud Link profile-orchestration investigation
↓
Climate Supervisor full-cycle validation
↓
Carbonation runtime validation
↓
Fermentation cockpit/runtime validation
↓
Full YAML logic retirement
```

The 2026-08-29 physical Brewfather/BrewZilla tests moved the project beyond basic ownership/gating uncertainty. Brewday operator ABORT / persistence / explicit-rearm is physically verified. A supervised 15 L water-only run then exposed a concrete heat safe-down precedence bug and a Mash-In checkpoint ambiguity. PR #173 fixes the heat safe-down path; PR #174 implements #157 as read-only physical ramp/hold timing telemetry. The immediate focus is one clean supervised water-only regression run before the first real-mash validation.

### Branch policy

```text
main = installable/stable beta baseline
short-lived feature/fix branches = active development only
merge after regression tests/CI are green
```

---

## Python Core / Brewday Runtime status

Completed:

```text
[x] Custom integration + config flow + coordinator
[x] Normalized Brewday Runtime
[x] Brewfather RAW Brew Tracker timeline resolver
[x] Human-friendly ramp/hold labels
[x] Paused Brewfather freeze-state behavior
[x] Smart Brewfather refresh policy + manual refresh
[x] Manual Brewday Python engine + adapter + services
[x] Manual/Brewfather mutual exclusion and safe handoff
[x] Brewday Stage Engine v2
[x] Brewday Event Log / Flight Recorder backend + persistence + dashboard
[x] Flight Recorder early Planning autostart
[x] Deterministic new-brewday session boundary
[x] Same Brewfather batch keeps one log through Planning -> pre-start -> Play
[x] Brewfather Planning is visible/ready but not hot-side owner
[x] Brewing pre-start is visible/ready but not owner
[x] Brewfather ownership begins only after positive tracker-start evidence
[x] Started Brewfather tracker retains ownership through later legitimate pause
[x] Effective target and physical BrewZilla device target are separate diagnostics
[x] Manual Brewday prepared state is physically safe
[x] Positive automatic BrewZilla actions use explicit Supervised Apply
[x] Confirmation path rebuilds and validates the live plan before execution
[x] Rejected pending plan is suppressed while exact intent/context remains unchanged
[x] Confirmed-plan RCL number-readback grace prevents duplicate confirmation from stale cloud replay
[x] Confirmed heater/pump switch echo gets bounded observe-only grace without auto re-energizing
[x] BrewZilla hardware ABORT safe-down + positive-action lockout
[x] Brewday operator ABORT semantics separated from pending-plan rejection
[x] Brewday operator ABORT persistent ownership latch
[x] Explicit Brewday control rearm action
[x] Persisted Brewday ABORT loaded before coordinator/orchestration decisions
[x] Read-only Brewsteps process view for BrewTracker-owned brewday
[x] Read-only physical mash-hold timer and ramp telemetry (#157)
[x] Physical timer separates source schedule from actual process target reach
[x] Physical timer freezes on PAUSE and stops on ABORT
[x] Current-brew ramp/hold history includes context/source/utilization diagnostics
```

Current operator-control rule:

```text
CONFIRM ACTION
  -> explicitly execute a still-valid pending positive plan

REJECT ACTION / AVVISA ÅTGÄRD
  -> reject one pending positive intention

ABORT BREWDAY / ABORT BRYGGDAG
  -> physical BrewZilla safe-down
  -> discard pending positive intent
  -> reset Manual Brewday
  -> persistent BA hot-side ownership lock

REARM CONTROL / ÅTERAKTIVERA STYRNING
  -> release only the Brewday ownership lock
  -> never bypass independent BrewZilla ABORT lockout
```

---

## BrewZilla hot-side status

Completed implementation:

```text
[x] BrewZilla normalized runtime sensors
[x] Target sync from normalized runtime
[x] Heater/pump direct action helpers
[x] Heat/pump utilization direct action helpers
[x] Clean heat-strike model
[x] Real strike-target latch; no boosted physical target
[x] Mash/BLE readiness gate + BrewZilla internal/wort safety view
[x] Heat-strike pump mixing/equalization
[x] Mash-In Started target release
[x] Pump stop during grain addition
[x] Brewfather Continue -> auto Mash-In Complete path
[x] One-way mash-in state machine
[x] Mash-in gate sensors/buttons/cards
[x] Active hot-side RCL recovery
[x] Local-regulation preservation when a valid BZ target already exists
[x] Explicit heat safe-down bypasses local-regulation preservation when process/safety requires zero heat (#173)
[x] Target-downshift invariant: process > requested target + 0.3°C permits 0% heat / heater OFF
[x] RCL reload suppression while live temp/power telemetry is fresh
[x] No-positive-control gate
[x] Final low-level ABORT positive-action lockout
[x] Supervised Apply gate for target/utilization/switch positive actions
[x] Confirmed number-write readback grace
[x] Confirmed switch-OFF echo observe-only grace (30 s)
[x] BrewZilla heat/pump live visualization
```

Physically verified 2026-08-29:

```text
[x] Brewing before Play leaves heater/pump OFF and no positive write occurs
[x] Play creates Brewfather runtime ownership without rotating Flight Recorder
[x] Pending confirmation leaves positive physical actions unapplied
[x] Explicit confirmation applies heat utilization 100%
[x] Explicit confirmation applies pump utilization 70%
[x] Explicit confirmation turns heater ON
[x] Explicit confirmation turns pump ON
[x] supervised_executed follows complete execution
[x] Confirmed stale switch echo does not reopen the same confirmation during the observed run
[x] Hardware ABORT turns heater OFF
[x] Hardware ABORT turns pump OFF
[x] Hardware ABORT zeros heat utilization
[x] Hardware ABORT zeros pump utilization
[x] Hardware ABORT lockout blocks recreated positive orchestration
[x] Brewday ABORT produces physical safe-down and runtime_state=aborted
[x] Brewfather does not reclaim BA hot-side ownership while operator control is aborted
[x] HA restart preserves Brewday operator ABORT latch before orchestration resumes
[x] Explicit rearm releases Brewday operator lock and returns runtime to safe idle
[x] Rearm does not itself perform a positive BrewZilla action or bypass the independent hardware lockout
[x] Bryggråd APPLY executed a live 100% -> 95% heat-utilization recommendation in the water-only run
```

Physical findings that require retest after #173:

```text
[ ] Heatstrike final coast physically reaches heat 0% / heater OFF instead of preserving previous positive utilization
[ ] 71.8 -> 66.0°C target downshift keeps heat 0% while process temperature remains above target
[ ] Mash-In Started is explicitly observed before Continue with pump OFF / pump utilization 0%
[ ] Near-strike supervised pump increases are understood/confirmed where required
```

Near-term physical checks:

```text
[ ] Water-only regression retest of Heatstrike / Mash-In / target-downshift
[ ] Physical #157 timer starts 66°C hold only on actual target reach
[ ] Physical #157 timer records 66 -> 72°C ramp separately and starts 72°C hold only on actual target reach
[ ] Physical #157 PAUSE freezes timer
[ ] Read-only Brewsteps follows BrewTracker-owned physical process phases correctly
[ ] First real-mash heat-strike / mash-in temperature-drop validation
[ ] Real-mash 66°C hold and 66 -> 72°C ramp validation
[ ] Full boil ramp + boil validation
```

---

## External process-temperature sensor ownership

Architecture decision is fixed:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  Brewday Runtime owns the optional external process sensor
  e.g. RAPT BLE Thermometer

Boil starts
  Brewday Runtime releases the external sensor

Chill -> Transfer
  CFC backend owns the same sensor
  role = CFC outlet / wort-out temperature
```

BrewZilla internal temperature remains Brewday Runtime's primary kettle temperature throughout the hot-side path.

Validation still required:

```text
[ ] Verify ownership release exactly at Boil start
[ ] Verify no competing Brewday/CFC external-sensor role during Boil
[ ] Verify CFC acquires the external sensor during Chill
[ ] Verify Transfer continues using it as wort-out temperature
```

---

## Flight Recorder / diagnostics status

Completed:

```text
[x] Persistent Brewday Event Log
[x] Normalized Brewfather + Manual runtime context
[x] Runtime/stage/step/target/action diagnostics
[x] RAPT/RCL freshness diagnostics
[x] Mash-in gate diagnostics
[x] Supervised Apply confirmation/execution/rejection events
[x] Explicit effective-target vs physical-device-target fields
[x] One recorder session per Brewfather brewday through Planning/pre-start/Play
[x] Deterministic boundary for truly new brewday
[x] Hardware ABORT evidence + lockout evidence
[x] Brewday operator ABORT / rearm events
[x] Persisted operator ABORT remains visible after HA restart
[x] Water-only run captured heat safe-down suppression clearly enough to isolate the later local-regulation guard
```

Physical continuity baseline from 2026-08-29:

```text
Planning started_at = 2026-08-29T16:39:42.512671+00:00
Brewing pre-start     -> same started_at
Play / paused-running -> same started_at
```

No new `audit_started` at Play is the expected regression baseline.

Known diagnostics gap:

```text
[ ] Bryggråd APPLY needs clearer explicit audit/UI observability even though execution worked
[ ] Mash-In Started must be captured unambiguously in the next physical checkpoint
```

---

## Physical mash/ramp timing telemetry

Implemented in #157 / PR #174 as a read-only layer:

```text
[x] Physical ramp timer
[x] Mash hold timer starts only in target band (±0.3°C)
[x] First hold waits for Mash-In Complete when gate exists
[x] PAUSE subtracts paused time from process elapsed
[x] ABORT stops telemetry without control writes
[x] Brewfather/source schedule mismatch is diagnostic only
[x] Current-brew history for ramp/hold duration, ΔT and °C/min
[x] Water only / Real mash context retained
[x] Heat/pump utilization start/end retained
[x] Separate EN/SV timing expander cards
```

Current limitation:

```text
- timing ledger is volatile across Home Assistant restart during first field-validation implementation
```

Persistence should be considered after the physical behavior is verified.

---

## BrewZilla Equipment Learning / Brewfather timing advisor

Current status:

```text
[x] Passive equipment-learning storage model
[x] Rolling evidence/profile buckets by equipment/context/volume/grain/stage
[x] Learning sensors and recommendation context
[x] Water-only evidence distinguished from real-mash evidence
[ ] Planned-vs-actual timing segment detector
[ ] Heat-strike timing suggestion
[ ] Mash-ramp timing suggestion using validated physical ramp telemetry
[ ] Mash-out timing suggestion
[ ] Boil-ramp timing suggestion
[ ] Confidence model using observation count/context/source quality
[ ] Optional JSON/Markdown batch learning report
[ ] Dashboard section for Brewfather timing suggestions
```

Persistent learning feedback loop — later beta work:

```text
[ ] Store operator-approved learned profile overrides separately from built-in defaults
[ ] Add explicit APPLY / DENY flow for learned profile candidates
[ ] Match approved overrides by equipment + learning context + volume + grain + phase on a future brewday
[ ] Load a matching approved override as profile input on the next brew without rewriting the Brewfather recipe
[ ] Keep precedence explicit: hard safety / ABORT > active process guard > approved learned override > built-in profile default
[ ] Record override provenance: evidence bucket, confidence, approved value, approval timestamp and source model version
[ ] Expose which learned override is active, why it matched and which built-in value it replaced
[ ] Provide reversible disable/revert/reset controls for accepted overrides
[ ] Never promote a raw candidate into live control without explicit operator approval
[ ] Add regression coverage proving Water only evidence cannot activate a Real mash override
```

Target feedback-loop model:

```text
current brew observations
  -> persistent equipment/context evidence
  -> learned candidate suggestion
  -> explicit operator review / APPLY
  -> persistent approved override
  -> next matching brew loads override on top of built-in profile
  -> live safety/ABORT remains authoritative at all times
```

Learning remains advisory until a candidate has been explicitly approved:

```text
- no silent Brewfather recipe/profile rewrite
- no automatic live target/heat/pump change from an unreviewed learning candidate
- operator reviews suggestions
- approved overrides may influence a later matching brew through the normal controller/profile path
- source/RCL quality affects confidence
```

---

## CFC Chill / Transfer Assistant

The CFC backend is downstream of Brewday hot-side ownership.

Architecture goals:

```text
- acquire external process sensor after Brewday releases it at Boil
- interpret it as CFC outlet / wort-out temperature
- keep BrewZilla internal kettle temperature available as upstream thermal context
- supervise Chill and Transfer without ownership conflict
- expose clear handoff state to the dashboard/event log
```

Next validation:

```text
[ ] Boil -> Chill ownership handoff
[ ] CFC outlet temperature acquisition
[ ] Chill target / pitch-ready behavior
[ ] Transfer completion behavior
```

---

## UI localization / dashboard status

Architecture:

```text
English = canonical backend identifiers and default UI
Swedish = presentation mirror/localization
entity IDs / unique IDs / runtime keys remain stable English
```

Completed:

```text
[x] EN/SV dashboard mirror policy
[x] Dashboard parity regression checks for entity/action references
[x] en.json canonical translation source
[x] sv.json localization
[x] Button translation-key migration where applicable
[x] Switch translation-key migration where applicable
[x] Number translation-key migration where applicable
[x] EN/SV read-only Brewsteps cards for BrewTracker-owned brewday
[x] EN/SV physical timing expander cards
[x] Hub Manual Brewday visibility uses authoritative runtime idle state
[x] Safety/RCL card accepts canonical and legacy visibility switch IDs
```

Known UI cleanup:

```text
[ ] `Starta mäskcirkulation` compatibility action must only be visible in the narrow post-Mash-In / pump-off window
[ ] Decide whether validated physical timing UI should be folded into the main Brewday cockpit after field test
[ ] Inventory remaining hard-coded sensor names
[ ] Inventory remaining binary-sensor names
[ ] Migrate select names/options with compatibility-safe state handling
[ ] Expand service/action translations
```

See [`localization.md`](localization.md) and [`dashboard-baselines.md`](dashboard-baselines.md).

---

## Other active backends

Already present in Python Core:

```text
[x] Counterflow Wort Cooling backend + cockpit
[x] Python-owned Carbonation Runtime/session + persistence
[x] Carbonation services + cockpit
[x] Climate Supervisor backend + UI
[x] Kegerator fan modes Off / Always on / Afterrun
[x] Kegerator guard/fan async-safety cleanup
[x] Fermentation Cockpit scope guard + UI
[x] Clean HA entity baseline without old bryggeriet_ BrewAssistant prefix
```

These remain secondary to completing deterministic supervised hot-side and CFC process validation.

---

## Immediate next sequence

```text
1. Run one supervised Water only Brewfather/BrewTracker regression on the #173 + #157 baseline.
2. Verify Heatstrike taper ends with physical heat 0% / heater OFF.
3. Stop explicitly at Mash-In Started and verify gate state + pump OFF / utilization 0 before Brewfather Continue.
4. Verify 71.8 -> 66.0°C target downshift keeps positive heat suppressed while above target.
5. Validate physical 66°C hold countdown, PAUSE freeze and separate 66 -> 72°C ramp telemetry.
6. Verify Brewsteps follows BrewTracker ownership and physical phase.
7. If the water-only regression is clean, perform the first supervised real-mash run and validate real grain thermal behavior.
8. Continue through Mash out / Sparge / Pre-boil and validate full boil ramp + boil.
9. At Boil start, verify Brewday releases the external process-temperature sensor.
10. Validate CFC acquisition for Chill and continued wort-out use during Transfer.
11. Use Flight Recorder + validated physical timing evidence to drive the next Equipment Learning/profile-advisor patch.
```
