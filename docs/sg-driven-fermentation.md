# SG-driven fermentation: contract and implementation status

Status: **pure rule engine and tests only** on `dev`; **not integrated or deployable as a control mode yet**. Keep the installed fermentation test on the existing recipe schedule. Do not promote to `beta` or `main` until explicitly approved after runtime validation.

## Ownership and mode selection

- Brewfather provides the original scheduled fermentation steps as read-only planning data.
- `fermentation_tracking` owns interpretation and an optional, explicitly enabled **per-batch SG control mode**. Default remains `recipe_schedule` for backward compatibility.
- `fermentation_chamber` consumes the effective recommended beer temperature through its existing supervised-apply boundary. No new direct heater, compressor or climate services.
- The SG mode must identify the configured RAPT Pill gravity entity; a manual SG value or an arbitrary SG sensor must not silently advance the stage.
- If Pill evidence goes stale, hold the *persisted last confirmed stage* and expose a clear diagnostic. Do not resume a date-based recipe ramp and do not infer progression from an absent value.

## Initial target profile for Julöl 2026 V2

| Latched stage | Trigger | Temperature |
| --- | --- | --- |
| 0: primary | initial | 18.0 °C |
| 1: rise | two credible Pill readings at SG <= 1.035 | 19.0 °C |
| 2: finish | two credible Pill readings at SG <= 1.020 | 20.5 °C |

For each threshold, require two distinct fresh measurements at least five minutes apart. Sensor re-polls of the same observation do not count; the confirmation window expires after two hours. An accepted stage must never regress or skip a stage when SG rises or fluctuates. Stage, pending confirmation, sample timestamp and batch identity must survive Home Assistant restarts. No default-on migration of an active session.

## Validity

The pure engine in `sg_control_rules.py` rejects readings older than 20 minutes, more than one minute in the future, outside SG 0.980–1.150, or over the known OG by more than 0.005. The integration still needs to prove that readings originate from the configured Pill. Stale or invalid readings must result in HOLD of the last confirmed fermentation target, with an exposed reason.

## FG and cold crash

Expected FG approximately 1.014. The optional SG mode must persist *actual automatic Pill observation history* rather than mistake a current sensor value for a stability history. Default stability verification is 72 hours (48–72 configurable explicitly), SG range <= 0.001, at least six observations, no gap > 12 hours, fresh latest value, and latest SG <= configured FG + tolerance (default 0.002). Missing FG or insufficient history means NOT READY.

Readiness is **advisory**. On the transition to ready, notify once and ask for explicit user confirmation. No automatic cold crash, `input_boolean` switch-on, or climate action is permitted from readiness alone. A separate explicit confirmation must attest that protection against suck-back is installed (e.g. suitable CO2/positive-pressure protection); an ordinary airlock cannot be inferred safe from SG or time. The actual start must remain under the existing cold-crash/supervised control boundary.

## Integration work still required

1. Persist SG mode, batch-scoped stage, threshold confirmation state and Pill history through Home Assistant Storage; reset only for an explicitly new batch.
2. Evaluate only new readings from the validated configured Pill in the coordinator/event flow, never as a side effect of a sensor property.
3. Arbitrate recipe/time vs SG targets in the tracking snapshot with `sg` winning only when explicitly enabled. Expose selected mode, stage, threshold, observation age, hold reason and readiness diagnostics.
4. Add a clear operator flow for readiness notification, suck-back-protection attestation and explicit cold-crash confirmation. Verify it cannot actuate while climate supervisor is OFF.
5. Add persistence, coordinator, restart and supervised-apply regression tests; validate on a real batch before any promotion.

Current code (`sg_control_rules.py`) implements only the *pure decisions* for monotonic stage changes and evidence-based readiness. Tests: `tests/test_fermentation_sg_control_rules.py`. It is intentionally not imported into the active runtime yet.
