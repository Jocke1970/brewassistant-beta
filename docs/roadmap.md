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
Continuous water regression on the #193 + #194 + #157 baseline
↓
First supervised real-mash BrewZilla validation
↓
BrewZilla Equipment Learning timing/profile advisor evidence pass
↓
Boil / hop validation + external-temperature ownership release
↓
Cooling/CFC Chill / Transfer ownership handoff validation
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

The 2026-08-29 physical Brewfather/BrewZilla tests moved the project beyond basic ownership/gating uncertainty. Brewday operator ABORT, persistence and explicit rearm are physically verified.

The 2026-08-31 supervised water test then exposed two near-strike edge cases:

```text
1. Heatstrike final-approach dead zone
   -> fixed by PR #193
   -> BrewZilla local regulation stays active through final approach / READY

2. RAPT Cloud MASH/process telemetry becoming stale near Mash-In
   -> bounded by PR #194
   -> automatic READY requires fresh process telemetry within ±1.0 °C
   -> stale process values are diagnostic-only
   -> operator may accept a physically plausible strike condition up to ±2.0 °C
```

PR #157 remains the read-only physical ramp/hold timing layer. The immediate goal is one continuous supervised water regression of the merged #193/#194 behavior plus the physical timing and Mash-In pump-off checkpoint before the first real-mash validation.

See [`physical-validation-2026-08-31.md`](physical-validation-2026-08-31.md) for the current physical evidence and contracts.

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
[x] Mash-In and physical timing presented as one Brewday Runtime process flow (#188)
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
[x] Heatstrike final-approach local-regulation contract (#193)
[x] Mash-In Started target release
[x] Pump stop during grain addition
[x] Brewfather Continue -> auto Mash-In Complete path
[x] One-way mash-in state machine
[x] Mash-in gate sensors/buttons/cards
[x] Automatic Mash-In READY requires fresh canonical process telemetry within ±1.0 °C (#194)
[x] Stale locked process temperature preserved for diagnostics only, never automatic READY (#194)
[x] Bounded operator strike acceptance up to ±2.0 °C; readiness latch only (#194)
[x] Active hot-side RCL recovery
[x] Local-regulation preservation when a valid BZ target already exists
[x] Explicit heat safe-down bypasses local-regulation preservation for true safety/overshoot/ABORT contexts
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

Physical findings from 2026-08-31 now covered by merged fixes:

```text
[x] Reproduced Heatstrike final-approach dead zone at target 71.8 / MASH 69.6 / WORT 71.5 °C
[x] PR #193 keeps BrewZilla local regulation active instead of disabling the heater master near strike
[x] Reproduced stale RAPT Cloud MASH/process telemetry near Mash-In
[x] PR #194 prevents stale external process temperature from creating automatic READY
[x] PR #194 adds bounded operator strike acceptance without changing hardware state
```

Continuous regression still required:

```text
[ ] Heatstrike closes the final few degrees without the pre-#193 dead zone
[ ] BrewZilla local regulation remains active through final approach / READY
[ ] Automatic Mash-In READY occurs only from fresh canonical process telemetry within ±1.0 °C
[ ] Stale process telemetry remains diagnostic-only
[ ] Bounded operator strike acceptance behaves correctly when intentionally used
[ ] Mash-In Started is explicitly observed before Continue with pump OFF / pump utilization 0%
[ ] Near-strike supervised pump increases are understood/confirmed where required
```

Near-term physical checks:

```text
[ ] Continuous water regression of Heatstrike / Mash-In on #193/#194
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
  Cooling/CFC backend owns the same sensor
  role = CFC outlet / wort-out temperature
```

BrewZilla internal temperature remains Brewday Runtime's primary kettle temperature throughout the hot-side path.

Validation still required:

```text
[ ] Verify ownership release exactly at Boil start
[ ] Verify no competing Brewday/Cooling external-sensor role during Boil
[ ] Verify Cooling/CFC acquires the external sensor during Chill
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
[x] Water-only runs captured the Heatstrike and Mash-In telemetry edge cases clearly enough to isolate deterministic fixes
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
[x] Separate EN/SV timing views integrated with Brewday Runtime flow
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

## Cooling / Chill / Transfer Assistant

Cooling Runtime v2 is downstream of Brewday hot-side ownership and supports both CFC and traditional immersion-coil/manual-water workflows.

Architecture goals:

```text
- acquire external process sensor after Brewday releases it at Boil when the selected method needs it
- interpret the external sensor as CFC outlet / wort-out temperature for CFC workflows
- use BrewZilla internal temperature or manual measurement where traditional coil cooling does not need an external outlet sensor
- support manual cooling-water flow as well as pump-assisted flow where available
- sanitize the cooling path for both CFC and immersion-coil workflows
- keep wort-pump control advisory/operator-owned where the backend must not own that hardware
- keep BrewZilla internal kettle temperature available as upstream thermal context
- expose clear Chill / Transfer handoff state to dashboard and diagnostics
```

Next validation:

```text
[ ] Boil -> Chill ownership handoff
[ ] CFC outlet temperature acquisition
[ ] Traditional coil path using internal/manual temperature
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
[x] EN/SV physical timing views
[x] Consolidated EN/SV Brewday Runtime flow with physical timing + Mash-In process controls (#188)
[x] EN/SV bounded Mash-In readiness override + stale-age diagnostics (#194)
[x] Cooling Runtime v2 dashboard cards and Swedish mirror
[x] Hub Manual Brewday visibility uses authoritative runtime idle state
[x] Safety/RCL card accepts canonical and legacy visibility switch IDs
```

Known UI cleanup:

```text
[ ] `Starta mäskcirkulation` compatibility action must only be visible in the narrow post-Mash-In / pump-off window
[ ] Decide whether validated physical timing presentation should be folded even tighter into the main Brewday cockpit after field test
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
[x] Cooling Runtime v2 + CFC/coil/manual-water method model
[x] Counterflow Wort Cooling backend + cockpit
[x] Python-owned Carbonation Runtime/session + persistence
[x] Carbonation services + cockpit
[x] Climate Supervisor backend + UI
[x] Kegerator fan modes Off / Always on / Afterrun
[x] Kegerator guard/fan async-safety cleanup
[x] Fermentation Cockpit scope guard + UI
[x] Clean HA entity baseline without old bryggeriet_ BrewAssistant prefix
```

These remain secondary to completing deterministic supervised hot-side and cooling ownership validation.

---

## Immediate next sequence

```text
1. Run one continuous supervised Water only Brewfather/BrewTracker regression on the merged #193 + #194 + #157 baseline.
2. Verify Heatstrike closes the final few degrees without the previous final-approach dead zone.
3. Verify BrewZilla local regulation remains active through final approach / READY.
4. Verify automatic Mash-In READY occurs only from fresh canonical process telemetry within ±1.0 °C.
5. If RAPT process telemetry becomes stale, verify the stale value stays diagnostic-only and test bounded operator strike acceptance only if physically appropriate.
6. Stop explicitly at Mash-In Started and verify pump OFF / pump utilization 0 before Brewfather Continue.
7. Validate physical 66°C hold countdown, PAUSE freeze and separate 66 -> 72°C ramp telemetry.
8. Verify Brewsteps follows BrewTracker ownership and physical phase.
9. If the water-only regression is clean, perform the first supervised real-mash run and validate real grain thermal behavior.
10. Continue through Mash out / Sparge / Pre-boil and validate full boil ramp + boil.
11. At Boil start, verify Brewday releases the external process-temperature sensor.
12. Validate Cooling/CFC acquisition for Chill and continued wort-out use during Transfer; separately validate traditional coil/manual-temperature behavior.
13. Use Flight Recorder + validated physical timing evidence to drive the next Equipment Learning/profile-advisor patch.
```
