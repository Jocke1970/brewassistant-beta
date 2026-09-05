# BrewZilla Backend

Status: **active supervised hot-side beta**  
Last synced: **2026-09-05**

This document is the repository-level architecture summary for BrewAssistant's BrewZilla/RAPT hot-side backend.

The code-local canonical package guide is:

[`../../custom_components/brewassistant/brewzilla/README.md`](../../custom_components/brewassistant/brewzilla/README.md)

For end-to-end operator flow, see [`../brewday-brewzilla.md`](../brewday-brewzilla.md). For current field evidence, see [`../physical-validation-2026-09-05.md`](../physical-validation-2026-09-05.md).

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
- enforce Manual Brew channel ownership
- enforce generic Supervised Apply outside dedicated phase authority
- enforce ABORT / hard-safety boundaries above normal ownership
- expose enough diagnostics for Flight Recorder and physical regression
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

Two physical temperature roles must remain distinct:

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

While this controller owns the phase, it may make bounded internal target/heat/pump adjustments without opening a new generic confirmation for every modulation.

Lower ABORT and hard-safety guards remain authoritative.

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

BrewAssistant does not use an artificially boosted strike target. It writes/holds the actual strike target and modulates authority around it.

PR #193 established that the BrewZilla heater master should remain available during ordinary final approach when the external process probe is still below strike.

---

## Gradient relief — PR #197

The 2026-09-05 physical run reproduced a deadlock with the external readiness probe low while the internal view had already crossed strike.

Representative state:

```text
strike target       ~71.8 °C
MASH/BLE             ~67.8 °C
BrewZilla internal   ~72.7 °C
```

Normal rule:

```text
hottest-view overshoot > target +0.5 °C
  -> explicit heat safe-down remains the default
```

Narrow pre-mash gradient exception:

```text
MASH/BLE still below strike
AND a real external/internal gradient exists
AND overshoot > +0.5 °C
AND overshoot <= +1.5 °C

=> heat cap 15%
=> heater master remains available to BrewZilla local thermostat
=> pump 100% for temperature equalization
```

Hard boundary:

```text
overshoot > +1.5 °C
  -> explicit hard stop
```

Do not generalize the +1.5 °C boundary into a broad overshoot tolerance. It exists only to prevent the physically observed pre-mash gradient deadlock.

Implementation focus:

```text
brewzilla_clean_heat_strike_guard.py
```

---

## Mash-In readiness

Automatic READY requires fresh canonical process telemetry near strike:

```text
fresh external MASH/process temperature
within strike target ±1.0 °C
```

Stale locked process data is diagnostic-only.

A bounded operator readiness acknowledgement may be used within approximately strike ±2.0 °C when the operator has physically verified a plausible near-strike vessel and BrewZilla local/internal context supports that condition.

The acknowledgement only latches readiness. It does not itself change target, heater, pump or utilization.

---

## Mash-In handoff — PR #202

State machine:

```text
ready_for_mash_in
  -> Mash-In Started
  -> release strike target toward mash target
  -> pump OFF
  -> pump utilization 0%
  -> grain addition / stirring
  -> wait for real Brewfather progression
  -> Mash-In Complete
  -> normal circulation resumes
```

Automatic completion evidence is intentionally strict:

```text
paused -> running
OR
active Brewfather mash target leaves the captured strike target
```

A plain Brewfather `running` state alone must not complete Mash-In.

Until completion evidence exists, the physical pump hold remains authoritative.

---

## Fail-passive telemetry loss

Ordinary telemetry degradation is not an instruction to shut down an otherwise locally regulated BrewZilla.

Expected fail-passive behavior:

```text
no new BrewAssistant writes
preserve last valid local target/output context
request/indicate telemetry recovery
wait for trustworthy data
```

This does not override:

```text
ABORT
hard safety
explicit process safe-down
```

Recovery requests are diagnostic/recovery actions, not permission to casually rewrite target/heat/pump.

---

## Generic Supervised Apply

Outside dedicated phase authority, positive automatic actions remain supervised where applicable.

Examples:

```text
target increase
heat-utilization increase
pump-utilization increase
heater ON
pump ON
```

Expected flow:

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

RAPT Cloud Link may briefly republish an old value after a successful write.

BrewAssistant keeps bounded confirmed-write grace for matching runtime intent so stale target/utilization readback does not immediately recreate the same positive plan.

Limits:

```text
- bounded time window
- same runtime/source/stage/step/target intention
- no silent heater/pump re-energization
- persistent mismatch requires a new supervised decision
- ABORT invalidates grace immediately
```

---

## Manual Brew ownership

Manual Brew may split target, heat and pump ownership independently.

Conceptually:

```text
target                     = operator or BA
heater + heat utilization  = operator or BA
pump + pump utilization    = operator or BA
```

Manual ownership suppresses normal BA control for the operator-owned channel. It does not bypass an already active safety/ABORT block.

---

## ABORT

The physical BrewZilla ABORT path is authoritative:

```text
heater OFF
pump OFF
heat utilization 0
pump utilization 0
positive-action lockout
```

Brewday operator ABORT wraps the same physical safe-down with a separate persistent Brewday ownership latch.

No normal orchestration, advice, learning or Manual ownership path may re-enable positive hardware while the applicable ABORT lockout is active.

---

## Ordered wrapper/guard architecture

The package is implemented as an ordered wrapper/guard chain. Installation order in `custom_components/brewassistant/brewzilla/__init__.py` is functional architecture.

Current active concepts include:

```text
temperature role resolution
Heatstrike target/context
RCL recovery / process-sensor guards
learning/advice evidence
thermal/pump guards
Clean Heatstrike controller
Mash-In readiness/state machine
paused/execution/target-trust/local-regulation safety
hot-side contract
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
| `brewzilla_fail_passive_guard.py` | No-new-writes behavior on ordinary telemetry loss |
| `brewzilla_abort_lockout_final_guard.py` | Final ABORT/lockout protection |
| `brewzilla_active_rcl_recovery_guard.py` / `brewzilla_rcl_value_recovery_guard.py` | Recovery diagnostics/policy |
| `brewzilla_learning.py` / `brewzilla_equipment_learning.py` | Passive/advisory learning evidence |

The code-local package README should be preferred when file-level details differ from this repository summary.

---

## Diagnostics / Flight Recorder evidence

Useful evidence when debugging:

```text
runtime source/state/stage/step
effective target vs device target
process temperature + source/age
safety/internal temperature
heat/pump requested vs actual utilization
heater/pump state
Mash-In gate state
phase authority state
pending confirmation
apply_result / actions
fail-passive reason
RCL freshness/recovery
ABORT/lockout state
```

Physical fixes should be driven by Flight Recorder evidence rather than UI appearance alone.

---

## Current physical validation backlog

```text
[ ] gradient relief converges external process temperature safely
[ ] > +1.5 °C gradient overshoot still hard-stops heat
[ ] Mash-In Started holds pump OFF / 0% for the full grain-addition window
[ ] BF progression is the first event permitting circulation restart
[ ] Mash-In UI clears immediately after completion
[ ] physical 66 °C hold and 66 -> 72 °C ramp timing
[ ] first real-mash heat-strike / mash-in thermal behavior
[ ] Mash out / Sparge / Pre-boil
[ ] full Boil ramp / Boil
[ ] external process-sensor release at Boil
[ ] Cooling/CFC acquisition during Chill/Transfer
[ ] Equipment Learning planned-vs-actual timing evidence
```

---

## Do not change casually

1. Wrapper installation order is functional architecture.
2. External process and internal safety temperature roles are not interchangeable.
3. READY is not the same transition as Mash-In Started.
4. Mash-In Started owns a physical pump-off window.
5. Plain BF `running` is not Mash-In completion evidence.
6. The +1.5 °C gradient boundary is not a generic overshoot tolerance.
7. Ordinary data loss is fail-passive, not automatic shutdown.
8. ABORT and hard safety always outrank ownership, advice and learning.
9. Cooling owns the external process sensor after the Boil handoff; hot-side must release it.
