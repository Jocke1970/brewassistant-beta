# Physical mash control checkpoint — water-only test 2026-09-19

Status: **observed safety/design failure; not fixed by PR #212**. Work directly on `dev`; leave `main` untouched. Do not start a malt mash test until the acceptance cases below pass in an additional water-only run.

## Verified field evidence (local Stockholm time, UTC+02)

- 10:26:11 Mash-In Started correctly set the pump to 0/OFF and target to the next mash target, 66 °C.
- 10:26:35 Mash-In Complete set the pump to 50% and ON immediately. This contradicts the requested grain-bed settling behavior; there is no ten-minute settling state in the installed build.
- Brewfather finished its scheduled Hold 66 °C and progressed to Ramp 72 °C while BA's read-only physical Hold 66 °C timer had not completed. This is not merely a dashboard label disagreement.
- 10:32:14 operator confirmed the supervised Ramp 72 °C plan; 10:32:25 BA applied target 72 °C, heat 75%, pump 70%.
- 10:33:47 a second supervised plan was confirmed; 10:33:51 BA applied heat 90%, pump 85% even though the physical 66 °C hold remained unfinished.
- 10:36:16 ABORT disabled heater and pump and zeroed both utilizations; subsequent control reason showed ABORT lockout. This is positive evidence for the abort path, not evidence that the mash transition was safe.
- Learning context `Water only` is **correct** for this test and must not be treated as a defect.

Sources: operator screenshots, `Inklistrad text(20260919-083813).txt` flight-recorder export and `Inklistrad text (2).txt` orchestration attributes provided in chat. Relevant code: `brewzilla_mash_in_gate.py`, `brewzilla_mash_in_complete_safe_down_guard.py`, `brewzilla_hot_side_contract.py`, `brewday_physical_timing.py`, `brewzilla_supervised_runtime_guard.py`.

## Required behavioral contract

1. Mash-In Started: preserve the existing strict BF post-start PAUSED -> RUNNING completion contract, release strike target to actual mash target, immediately pump OFF/0 and retain lower-priority safety/fail-passive/ABORT guards.
2. Mash-In Complete means grain stirred in and hydrated; **never** use Complete as an alias for pump ON. Start a configurable `mash_settle_minutes` wall-clock interval (default 10 min), pump OFF during and after expiry until explicit operator confirmation. Heat may continue maintaining the latched *current physical mash target*, subject to canonical BLE/internal-temperature safety; do not preheat to a later BF target.
3. Once settling is done, propose low flow (default `recirculation_initial_utilization: 25`); operator confirmation is required. Apply utilization before switch ON, verify real readback and require visual drainage check. No automatically escalating pump from advice/thermal-mix or stale pending plans.
4. After a configurable `recirculation_ramp_minutes` (default 5), propose normal flow (initial candidate `recirculation_normal_utilization: 50`), requiring a second explicit confirmation. Elapsed time by itself never energizes the pump or raises utilization.
5. Physical mash hold uses the canonical mash/process sensor and the independent elapsed timer. If BF schedules the next ramp early, present **BF schedule step** and **physical active step** separately. Physically latch the unfinished hold temperature and prohibit *every positive actuator path*, including normal tick, direct policy, confirmed supervised plan and stale plans, from advancing to BF's next target until the hold has completed. Pure read-only physical timing is not enough.
6. If the current physical target is missing, process data stale/unknown, stage ownership lost, conflicting external profile, or HA has restarted without recoverable session/timer state, fail closed. Do not infer that an unfinished hold completed or automatically resume heater/pump. Persist state or require an explicit safe recovery procedure before releasing the next physical step.
7. ABORT wins at every point, clears/suppresses pending confirmations, and cannot be bypassed by timer callback, BF handoff, manual circulation service, RCL/profile, HA restart or stale queued action. Detect actual readback, not merely sent commands.
8. Do not couple HLT SIM-1 to this controller. PR #212 is simulation-only; it never grants physical power, caps BZ or provides an electrical interlock. HLT stage/target observations may be affected by the difference between BF's scheduled target and BA's physical target, so report both rather than inventing agreement.

## Before any real malt test

- Unit tests: Complete from invalid state; BF already RUNNING; proper post-start PAUSED->RUNNING; no pump at Complete; settling start/restart; expiry with no action; two distinct operator confirmations; stop/lower flow; unexpected pump ON; loss of probe/RCL; stale pending Supervised Apply; BF 66 hold -> early 72 ramp (before reaching 66, during hold and after hold); abort at each state; HA restart during settling, ramp and hold; new batch isolation.
- Water-only integration: verify actual BrewZilla target, heater switch/utilization, pump switch/utilization and timestamps alongside BA UI, BF schedule, physical-step timer and Flight Recorder. Provoke early BF progression. Confirm zero unapproved positive actions, correct hold release and unchanged HLT virtual-only behavior.
- Dashboard: explicitly display settling countdown, `Pump OFF`, low-flow confirmation, ramp confirmation, physical hold vs BF step and ABORT/unsafe condition. Update both EN and SV card variants and preserve content parity.
- Ensure CI, Hassfest and HACS run on the final `dev` commit; passing tests alone is not physical approval. Never promote to `main` based on the water-only evidence alone.

## Current release gate

**BLOCKED:** no mash with malt. PR #212 merged on `dev` as `746633c` with a green CI result; the physical mash controller fix is independent and must be implemented and validated separately. This document records the requirements and field evidence; it does not implement control or authorize a test.