# BrewZilla Backend

Status: **active supervised hot-side beta**  
Last synced: **2026-09-06**

This document is the repository-level architecture summary for BrewAssistant's BrewZilla/RAPT hot-side backend.

Code-local package guide:

[`../../custom_components/brewassistant/brewzilla/README.md`](../../custom_components/brewassistant/brewzilla/README.md)

End-to-end operator flow:

[`../brewday-brewzilla.md`](../brewday-brewzilla.md)

Latest field evidence:

[`../physical-validation-2026-09-06.md`](../physical-validation-2026-09-06.md)

---

## Purpose

The BrewZilla backend converts normalized Brewday intent into bounded physical BrewZilla/RAPT behavior.

Responsibilities:

```text
- read normalized Brewday source/stage/step/target intent
- read BrewZilla target, temperature, heater, pump and utilization state
- resolve process/mash vs internal/wort temperature roles
- regulate the dedicated Heatstrike/Mash-In phase
- preserve valid BrewZilla local regulation during ordinary telemetry degradation
- separate report freshness from physical value stagnation
- actively request fresh RCL coordinator data during owned hot-side phases
- enforce Manual Brew channel ownership
- enforce generic Supervised Apply outside dedicated phase authority
- enforce ABORT / hard-safety boundaries above normal ownership
- expose diagnostics for Flight Recorder and physical regression
- feed passive Equipment Learning evidence without making learning a live control source
```

The backend is not unattended autopilot.

---

## Physical entity surface

Core orchestration works against BrewZilla/RAPT entities equivalent to:

```text
number.brewzilla_target_temperature
sensor.brewzilla_temperature
sensor.brewzilla_connection
switch.brewzilla
switch.brewzilla_heater
switch.brewzilla_pump
number.brewzilla_heat_utilization
number.brewzilla_pump_utilization
```

BrewAssistant normalizes the exact configured entity surface before making control decisions.

---

## Temperature roles

```text
process_temperature / mash_temperature
  canonical external process probe while hot-side owns it
  readiness + ramp/hold authority

safety_temperature / wort_temperature
  BrewZilla internal/kettle view
  limiter + overshoot + safety context
```

The internal sensor must not silently become target-reached authority while the owned external process probe is degraded or lagging.

External sensor ownership:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner = Brewday/BrewZilla hot-side

Boil starts
  hot-side releases ownership

Chill -> Transfer
  owner = Cooling/CFC when applicable
  role = CFC outlet / wort-out temperature
```

---

## Dedicated pre-mash phase authority

`Brewfather Play` grants the dedicated Heatstrike/Mash-In controller phase authority.

While this controller owns the phase, it may make bounded internal target/heat/pump adjustments without opening a new generic confirmation for every modulation. ABORT and hard-safety guards remain authoritative.

Outside dedicated phase authority, new positive automatic control continues through generic Supervised Apply where applicable.

---

## Heatstrike model

Before Mash-In:

```text
external MASH/process probe = readiness authority
BrewZilla internal/WORT     = limiter/safety view
BrewZilla target            = real strike target
pump                         = thermal mixing/equalization
```

BrewAssistant writes/holds the actual strike target; it does not invent a boosted device target.

### Gradient relief — PR #197 + 2026-09-06 refinement

Normal rule:

```text
hottest-view overshoot > target +0.5 °C
  -> explicit heat safe-down remains the default
```

Narrow pre-mash gradient exception:

```text
MASH/BLE still below strike
AND real mash/wort gradient >= 1.5 °C
AND hottest-view overshoot > +0.5 °C
AND hottest-view overshoot <= +2.0 °C

=> heat authority cap 5 %
=> heater master remains available to BrewZilla local thermostat
=> pump utilization 100 % for equalization
```

Hard boundary:

```text
hottest-view overshoot > +2.0 °C
  -> explicit heat 0 / heater OFF
```

The +2.0 °C limit exists only for the bounded gradient exception. Do not reinterpret it as a generic overshoot tolerance or READY band.

Implementation focus:

```text
brewzilla_clean_heat_strike_guard.py
```

---

## Mash-In readiness and handoff

Automatic READY requires fresh canonical external process telemetry within the readiness band. A bounded operator acknowledgement can accept a physically verified near-strike condition without silently changing target/heat/pump.

State machine:

```text
ready_for_mash_in
  -> Mash-In Started
  -> release strike target toward actual mash target
  -> pump OFF / utilization 0 %
  -> grain addition / stirring
  -> observe Brewfather PAUSED after Mash-In Started
  -> later Brewfather RUNNING / Continue
  -> Mash-In Complete
  -> normal circulation resumes
```

Automatic completion evidence is intentionally strict:

```text
post-start BF PAUSED observed
THEN later BF RUNNING
```

Not sufficient by themselves:

```text
BF already running when Mash-In Started is pressed
active Brewfather target movement
normalized BA runtime remaining live/running
```

The 2026-09-06 second field run confirms that this backend transition can complete correctly. UI presentation still needs a clearer completion transition.

---

## RCL report freshness, value age and active polling

The 2026-09-06 run exposed a semantic bug: stable values were being treated as stale transport because `last_updated` was used as if it were poll/report age.

Current contract:

```text
report/control freshness
  -> entity last_reported
  -> fallback entity last_updated
  -> used by orchestration and fail-passive trust

value age / stagnation
  -> last_updated + explicit value-change tracking
  -> diagnostics only
  -> must not redefine canonical process-temperature freshness

active hot-side refresh
  -> every 30 seconds while Brewday owns an active hot-side phase
  -> homeassistant.update_entity on one BrewZilla CoordinatorEntity
  -> CoordinatorEntity forwards to DataUpdateCoordinator.async_request_refresh()
  -> one trigger entity only, avoiding duplicate cloud fetch fan-out
```

Hard recovery remains separate:

```text
hard connection loss / extreme report staleness
  -> reload_config_entry may be requested
  -> minimum 15 minutes between reload requests
```

A stable temperature/target is valid data when reports continue. Value stagnation may still be useful diagnostically, but it cannot by itself trigger fail-passive control loss.

---

## Fail-passive telemetry loss

Ordinary **report** degradation is not an instruction to shut down an otherwise locally regulated BrewZilla.

Expected behavior:

```text
no new BrewAssistant writes
preserve last valid local target/output context
request/indicate telemetry recovery
wait for trustworthy data
```

This does not override ABORT, hard safety or explicit process safe-down.

---

## Generic Supervised Apply

Outside dedicated phase authority, positive automatic actions remain supervised where applicable:

```text
target increase
heat-utilization increase
pump-utilization increase
heater ON
pump ON
```

Flow:

```text
orchestration computes plan
  -> pending confirmation
  -> operator confirms
  -> live plan rebuilt + identity/safety checked
  -> still-valid plan executes
  -> confirmation/execution recorded in Flight Recorder
```

Risk-reducing safe-down actions may execute without waiting for confirmation.

---

## RCL readback grace

RAPT Cloud Link may briefly republish an old value after a successful write. BrewAssistant keeps bounded confirmed-write grace for matching runtime intent so stale target/utilization readback does not immediately recreate the same positive plan.

Limits:

```text
- bounded time window
- same runtime/source/stage/step/target intention
- no silent heater/pump re-energization
- persistent mismatch requires a new decision
- ABORT invalidates grace immediately
```

---

## Manual Brew ownership

Manual Brew may split ownership independently:

```text
target                     = operator or BA
heater + heat utilization  = operator or BA
pump + pump utilization    = operator or BA
```

Manual ownership suppresses normal BA control for the operator-owned channel. It does not bypass an active safety/ABORT block.

---

## ABORT

Physical BrewZilla ABORT is authoritative:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
positive-action lockout
```

Brewday operator ABORT reuses the physical safe-down and adds a persistent Brewday ownership latch.

---

## Ordered wrapper/guard architecture

Installation order in `custom_components/brewassistant/brewzilla/__init__.py` is functional architecture.

Current active concepts include:

```text
temperature role resolution
Heatstrike target/context
RCL/value-stagnation diagnostics
learning/advice evidence
thermal/pump guards
Clean Heatstrike controller
Mash-In readiness/state machine
paused/execution/target-trust/local-regulation safety
hot-side contract
active RCL polling/recovery
ABORT boundary
Manual ownership
Supervised Apply/readback grace
phase authority
outer fail-passive boundary
```

Do not reorder wrappers casually.

---

## Important files

| File | Purpose |
| --- | --- |
| `brewzilla_orchestration.py` | Core snapshot, desired state and executor |
| `brewzilla_temperature.py` / `brewzilla_temperature_roles.py` | Temperature role resolution/ownership |
| `brewzilla_clean_heat_strike_guard.py` | Current Heatstrike regulator including gradient relief |
| `brewzilla_hot_side_contract.py` | Canonical Heatstrike/Mash-In handoff |
| `brewzilla_mash_in_gate.py` | Mash-In state storage/operator transition surface |
| `brewzilla_mash_in_readiness_contract.py` | Fresh READY + bounded operator acknowledgement |
| `brewzilla_phase_authority.py` | Dedicated pre-mash phase authority |
| `brewzilla_supervised_runtime_guard.py` | Generic positive-plan confirmation outside dedicated authority |
| `brewzilla_supervised_readback_grace.py` | Stale readback grace after confirmed writes |
| `brewzilla_manual_brew_control.py` | Channel-scoped Manual ownership |
| `brewzilla_fail_passive_guard.py` | No-new-writes behavior on real telemetry loss |
| `brewzilla_abort_lockout_final_guard.py` | Final ABORT/lockout protection |
| `brewzilla_active_rcl_recovery_guard.py` | Active 30 s coordinator refresh + hard recovery policy |
| `brewzilla_rcl_value_recovery_guard.py` | Heatstrike value-stagnation diagnostics only |
| `brewzilla_learning.py` / `brewzilla_equipment_learning.py` | Passive/advisory learning evidence |

---

## Current physical validation backlog

```text
[ ] 30 s active coordinator refresh produces bounded report age in HA
[ ] stable values no longer cause false fail-passive blocking
[ ] 5 % / 100 % gradient relief converges external process temperature safely
[ ] > +2.0 °C hottest-view overshoot hard-stops heat
[ ] Mash-In Started holds pump OFF / 0 % during grain addition
[ ] post-start BF PAUSED -> later RUNNING permits circulation restart
[ ] Mash-In completion is visually obvious
[ ] physical 66 °C hold and 66 -> 72 °C ramp timing
[ ] first real-mash thermal behavior
[ ] Mash out / Sparge / Pre-boil
[ ] full Boil ramp / Boil
[ ] external process-sensor release at Boil
[ ] Cooling/CFC acquisition during Chill/Transfer
```

---

## Do not change casually

1. Wrapper installation order is functional architecture.
2. External process and internal safety temperature roles are not interchangeable.
3. READY is not the same transition as Mash-In Started.
4. Mash-In Started owns a physical pump-off window.
5. Automatic completion requires post-start BF PAUSED followed by later RUNNING.
6. The +2.0 °C boundary is a narrow gradient exception, not generic overshoot tolerance.
7. Report freshness and value-change age are separate concepts.
8. Ordinary real data loss is fail-passive, not automatic shutdown.
9. ABORT and hard safety always outrank ownership, advice and learning.
10. Cooling owns the external process sensor after the Boil handoff; hot-side must release it.
