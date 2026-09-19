# Brewday backend

Status: active on shared `dev`  
Documentation checkpoint: 2026-09-19 (HLT SIM-1 handoff; previous Brewday execution validation remains separately gated)

`brewday` owns BrewAssistant's normalized process model. It arbitrates Brewfather Brew Tracker, RAPT profile runtime and the Python-owned Manual Brewday engine into one runtime contract, interprets readable process stages, keeps physical timing and records the Brewday/BrewZilla Flight Recorder. It is **not** a BrewZilla hardware backend; physical target/heat/pump actuation belongs in [`../brewzilla/`](../brewzilla/). Recipe source, runtime/timer owner and physical control policy are distinct; see [`brewday-execution-modes.md`](../../../docs/brewday-execution-modes.md).

## Responsibilities

- normalize Brewfather Brew Tracker, active RAPT BrewZilla profiles and Manual Brewday into stable snapshots;
- arbitrate source ownership from real tracker start/profile evidence, not broad batch/device state alone;
- keep operator ABORT/rearm above all process sources and preserve recorder continuity;
- derive operator-facing stages, physical timing, addition alerts and guarded refresh advice;
- persist the compact Brewday Audit/Event Log and record meaningful transitions;
- expose normalized runtime facts to independent **read-only consumers** such as HLT SIM-1, without making Brewday depend on or actuate a physical HLT.

## Source priority

The public `brewday_runtime.py` resolver applies:

```text
operator ABORT latch -> explicit aborted, non-owning runtime
active/uncertain/stopped-handoff RAPT profile -> RAPT owns process source
active Brewfather Brew Tracker -> Brewfather owns runtime
active Manual Brewday -> Python Manual runtime
otherwise -> normalized idle/core snapshot
```

When RAPT wins, running Manual Brewday is paused for handoff. Genuine RAPT source loss after active observation retains the handoff rather than silently substituting Brewfather; confirmed STOP retains a stop guard until explicit/new handoff. Broad Brewfather phase `Brewing` or `active: true` is not start evidence; positive Brew Tracker start/advance is required. Once legitimately started, the tracker may retain ownership through normal pauses.

## Execution ownership and Brewfather PAUS

Keep `recipe/profile source`, `runtime/timer owner`, and `physical BrewZilla control policy` separate. In Brewfather/BrewTracker supervised mode, Brewfather provides recipe/runtime and owns timer progression; BA interprets checkpoints and owns physical target/heat/pump policy. A future BA-owned imported-recipe runtime may use Brewfather only as the recipe source and BA's Python engine for timers, starting rests only after actual temperature reach; that mode remains future work. Runtime ownership does not bypass Supervised Apply or physical guards.

A 2026-09-11 water test verified that a zero-minute BrewTracker `PAUS` freezes tracker status, step, progress and timer until operator Resume. While paused, BA must latch the **current** target, continue only the physical work needed for it and never pre-actuate `next_step`; following target becomes eligible only after Resume/advance. The same historical test found premature 40→45 and 45→55 °C requests; verify the corrected combined runtime physically before claiming that regression closed. The tracker path does not automatically Resume Brewfather.

## Operator ABORT

The persistent Brewday ABORT ownership latch yields non-owning runtime and excludes RAPT/Brewfather/Manual reclamation, discards pending positive intent and invokes the authoritative BrewZilla physical safe-down through the integration service layer. Explicit Brewday rearm is required; it does not release separate hardware ABORT lockout.

## Manual Brewday

`manual_brewday_runtime.py` is UI-independent with `idle`, `prepared`, `running`, `paused`, `awaiting_confirm`, `completed`. Default BIAB plan: Setup, Mash, Sparge, Boil, Whirlpool and Chill/Transfer, with step duration/target/pause/advance metadata. The adapter maps this internal plan onto the normalized surface.

| File | Purpose |
| --- | --- |
| `manual_brewday_runtime.py` | Manual plan, session, timers and transitions |
| `manual_brewday_store.py` | Session storage and access |
| `manual_brewday_adapter.py` | Normalized manual snapshot |
| `rapt_profile_runtime.py` | Normalized active RAPT profile intent |

## Normalization and stage interpretation

`brewday_runtime_core.py` resolves Brewfather/core runtime; `brewday_runtime.py` is the public source arbiter; `brewday_ramp_target_gate.py` guards physical ramp progression. `brewday_stage_engine.py` is read-only, converting normalized runtime and BZ telemetry to presentation stages such as:

```text
Idle -> Prepare -> Heating Strike / Strike Water -> Mash In -> Mash
-> Mash Out -> Heating To Boil -> Boiling / Hop Addition -> Whirlpool
-> Wort Cooling -> Pitch Ready / Transfer -> Cleaning -> Completed
```

Stage engine output does not control Cooling or BrewZilla hardware and is **not automatically equivalent** to the HLT simulator's preparation-stage contract.

## HLT SIM-1 – new consumer, 2026-09-19

[PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212) is merged into shared `dev` alongside separate SG-driven fermentation work. HLT is a separate, unloadable **read-only** simulation runner in [`../hlt/`](../hlt/) with its own 30 s timer. It reads `build_brewday_runtime_snapshot(hass)` (`stage`, `step`, `target_temperature`, `runtime_state`, operator ABORT), active Brewday Audit session and effective BrewZilla Batch Context `sparge_water_l`. It never makes Brewday a real HLT controller and issues no BZ caps, HLT writes or supervised-apply requests.

Contract for a virtual HLT opportunity:

```text
active Audit and non-terminal, non-aborted Brewday
AND known positive normalized sparge_water_l (0 means No Sparge)
AND explicitly eligible preparation stage
AND BZ heat utilization known, physical BZ watt/temperature samples fresh
AND BZ device and Brewday runtime targets agree, actual temp at target
AND no explicit ramp-step indication
AND entire virtual HLT wattage fits the simulation scenario
```

The current conservative eligible stage names are `Setup`, `Heat strike`, `Heat strike water`, `Mash`, `Mash in`, `Mash out`, `Sparge`; an unknown/new/terminal stage fails closed. Explicit step text such as `Ramp to 72°C` vetoes cruise, even if sampled temperature/target appear stable. **Brewday must not silently relabel a new step as HLT-eligible**; coordinate step-intent normalization and regression tests with the HLT backend first. The allowlist/ramp parser is an interim safeguard, not a validated source-independent sparge-intent API.

The physical-water test on 2026-09-19 verified BZ watt readings around 2.3 kW and propagation of 11.38 L sparge water to HLT; it exposed target/utilization numeric-setting age misclassification. JSONL also captured a **false virtual HLT grant** during explicit `Ramp to 72°C`, followed by yielding and a hypothetical overlap. These findings were corrected in `dev` and CI-checked, but **the final fixes have not yet been retested in installed HA**. Keep physical HLT disconnected; do not promote to beta/main or use 30 s polling as an electrical interlock. Read [dated field evidence and test handoff](../../../docs/hlt-sim1-field-validation-2026-09-19.md), [HLT sensor contract](../../../docs/hlt-dashboard-backend.md), [test/card instructions](../../../docs/hlt-dashboard-card.md) and [HLT code-local README](../hlt/README.md).

## Physical timing

`brewday_physical_timing.py` and `brewday_physical_timing_phase_patch.py` separate physical phase/timer evidence from external schedule time. Source stage/pause does **not** prove physical target reached. Brewfather's zero-minute PAUS can freeze its timer while BA continues the current target approach. A future BA-owned imported-recipe runtime must start its own hold timer only once the selected physical sensor reaches the target band. This layer is read-only and not a HLT/BZ power arbiter.

## Brewday Flight Recorder / Audit

`brewday_audit.py` persists through HA Storage using `brewassistant_brewday_audit_log` (schema 2, max 250 events). It records runtime, ownership, BZ plan/action/confirmation, safety and freshness evidence; trust those events over dashboard appearance when diagnosing physical hot-side transitions. Session boundary and continuity code prevents Brewfather pre-start from rotating logs unnecessarily. Audit events remain compact.

HLT additionally records per-session JSONL under `/config/brewassistant/logs/hlt-sim-<session-hash>.jsonl`; `sensor.brewassistant_hlt_trace_path` supplies its absolute HA-server path. It separates measured and virtual wattage and estimated/measured temperature, and significant virtual transitions enter the Brewday Event Log. HLT time/Wh counters are in-memory and reset on HA/integration restart even when JSONL persists. A 30 s simulator can show *hypothetical* overlaps; it is never physical electrical protection.

## Other important files

| File | Purpose |
| --- | --- |
| `brewfather_ownership.py` | Actual-start tracker ownership |
| `rapt_profile_runtime.py` | RAPT profile ownership/normalization |
| `brewday_operator_abort.py` | Persistent operator latch |
| `brewday_refresh.py` / `brewday_refresh_policy.py` | Guarded BF refresh |
| `brewday_addition_alerts.py` | Additions and step alerts |
| `brewday_*_sensor.py` | HA presentation |
| `brewday_audit_autostart.py` | Recorder lifecycle |
| `brewday_audit_session_boundary.py` | Deterministic new-session boundary |
| `brewday_audit_session_continuity.py` | Continuity around tracker start |

## Public service surface

The integration root registers `brewassistant.force_brewfather_refresh`, `brewassistant.brewday_audit_start`, `brewassistant.brewday_audit_stop`, `brewassistant.brewday_audit_clear`, `brewassistant.brewday_audit_snapshot`, and Manual Brewday services `manual_brewday_prepare`, `start`, `pause`, `next`, `start_mash`, `start_boil`, `start_whirlpool`, `start_cooling`, `finish`, `reset` under the `brewassistant.` domain. HLT SIM-1 adds **no public actuator service**. Exact HA entity IDs originate in root platform registration; runtime code should expose snapshots rather than depend on Lovelace helpers.

## Do not change casually

1. Brewday Runtime must stay independent of BrewZilla hardware where possible and never depend on HLT simulation availability.
2. Ownership uses real source evidence; operator ABORT outranks RAPT/BF/Manual.
3. Manual Brewday is a real Python engine, not UI/YAML emulation; stage engine stays read-only.
4. Recipe source, timer owner and physical apply policy remain separate.
5. Paused BrewTracker never authorizes next-step physical pre-actuation; physical timing is independent from tracker clock.
6. Recorder continuity is not reset by cosmetic source changes.
7. HLT's virtual budget, priority, timers and stage policy must never be mistaken for electrical authorization or BZ hardware caps.
8. Coordinate new Brewday step labels/normalized ramp intent with HLT; unknown intent must fail closed pending explicit contract tests.
