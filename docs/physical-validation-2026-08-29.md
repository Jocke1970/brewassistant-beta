# Physical validation — 2026-08-29

This note records the supervised BrewAssistant / Brewfather / BrewZilla validation performed on real Home Assistant hardware on 2026-08-29.

The purpose of this note is to preserve observed runtime evidence separately from implementation claims in PR descriptions.

Final code baseline prepared for the next physical run:

```text
main commit: 6ad9d57ecfc1efaf9a11cab972c4f042f93e4652
includes: #153 stale switch-echo readback grace
includes: #154 read-only Brewsteps for BrewTracker-owned brewday
includes: #173 heat safe-down + water-only validation regressions
includes: #174 / #157 read-only physical mash/ramp timing telemetry
```

The water-only run used approximately 15 L water in the BrewZilla and the RAPT BLE thermometer as the external process-temperature input. Learning context was explicitly set to `Water only`.

---

## Supervised Apply / Brewfather ownership baseline

Observed and accepted during the physical test sequence:

```text
[x] Brewfather Planning is ready/visible but not hot-side owner.
[x] Brewing before BrewTracker Play remains pre-start and does not send positive BrewZilla actions.
[x] BrewTracker Play creates Brewfather hot-side ownership without rotating the existing Flight Recorder session.
[x] A pending Supervised Apply plan does not perform positive hardware actions before explicit confirmation.
[x] Explicit confirmation applied heat utilization 100%.
[x] Explicit confirmation applied pump utilization 70%.
[x] Explicit confirmation turned heater ON.
[x] Explicit confirmation turned pump ON.
[x] Confirmed stale switch echoes did not create duplicate confirmation during the live run.
[x] Hardware BrewZilla ABORT turned heater/pump OFF and utilization to 0%.
[x] Hardware ABORT lockout blocked recreated positive orchestration.
```

This gives a physical PASS for the intended #153 confirmed-plan/readback behavior under this run.

---

## Brewday operator ABORT / persistence / rearm

The Brewday-level operator ABORT path was exercised before the water-only end-to-end run.

Observed immediately after `ABORT BRYGGDAG`:

```text
[x] Normalized Brewday Runtime = aborted.
[x] Operator control state = aborted / locked.
[x] Active runtime ownership was removed.
[x] BrewZilla heater = OFF.
[x] BrewZilla pump = OFF.
[x] Heat utilization = 0%.
[x] Pump utilization = 0%.
[x] BrewZilla orchestration presented blocked/safe state.
[x] Manual Brewday cockpit disappeared because Manual session was reset.
```

Home Assistant was then restarted while the Brewday operator ABORT latch was active:

```text
[x] Brewday Runtime still presented ABORTED after restart.
[x] Operator lockout was still active.
[x] Brewfather did not reclaim BrewAssistant hot-side ownership.
[x] BrewZilla remained heater OFF / pump OFF / heat 0% / pump 0%.
[x] Explicit REARM / ÅTERAKTIVERA STYRNING remained available.
```

After `ÅTERAKTIVERA STYRNING`:

```text
[x] Brewday operator lockout cleared.
[x] Normalized Brewday Runtime returned to idle.
[x] BrewZilla remained physically safe.
[x] No positive action was sent merely because operator control was rearmed.
```

The independent BrewZilla hardware ABORT lockout remains a separate lower-level safety mechanism. Rearming Brewday control does not bypass or clear that lockout.

---

## Water-only end-to-end run — observed findings

The water-only run intentionally followed the same supervised flow planned for a real mash where possible.

### Heat strike

Observed:

```text
[x] BrewTracker Play created Brewday ownership.
[x] Initial positive plan waited for confirmation.
[x] Confirmed far-ramp plan applied 100% heat / 70% pump.
[x] Clean Heatstrike progressively calculated lower heat as strike was approached.
[!] Final 0% heat / heater-OFF request was suppressed by the later local-regulation heat-preserve guard.
```

Flight Recorder analysis showed that Clean Heatstrike itself calculated the intended final coast/safe-down. The failure was later in the guard chain: `brewzilla_local_regulation_heat_guard` preserved the previous positive heat utilization because a valid local BrewZilla target existed.

PR #173 fixes this precedence problem. Explicit process/safety safe-down now bypasses ordinary local-target heat preservation for:

```text
- Clean Heatstrike explicit 0% / heater OFF
- Mash-In Started explicit zero request
- general target downshift where process temperature > requested target + 0.3°C
```

The invariant for the next run is therefore:

```text
process temperature > active requested target + 0.3°C
  -> desired heat utilization = 0%
  -> desired heater = OFF
```

### Bryggråd / Learning APPLY

A recommendation approved during Heatstrike was initially suspected not to execute. Flight Recorder review corrected that interpretation:

```text
[x] Bryggråd APPLY did execute a heat-utilization change (100% -> 95%).
[ ] Observability/audit presentation is still weak; the action was easy to miss in live UI/log interpretation.
```

Do not treat this run as evidence of a failed APPLY path.

### Mash-In transition

The run reached the Mash-In gate and then continued to a 66°C hold step.

Observed:

```text
[x] Brewfather Continue advanced the runtime to the 66°C hold step.
[?] Pump remained visibly ON / 50% around Mash-In Started in the live UI.
[?] Flight Recorder did not retain an unambiguous `mash_in_started` event in the reviewed sequence before `mash_in_complete`.
```

Because the gate code already specifies pump OFF / utilization 0 during physical grain addition, this is not being patched speculatively. The next run must explicitly stop at this checkpoint and verify both the gate state and physical pump state before Brewfather Continue.

Required next-run checkpoint:

```text
mash_in_started
pump OFF
pump utilization 0%
started_at != null
```

Only after that evidence should Brewfather Continue be pressed.

### Target downshift 71.8 -> 66.0°C

Observed after Mash-In transition:

```text
[x] BrewAssistant requested/applied the lower 66.0°C target.
[!] Process temperature remained above 70°C while positive heat could remain preserved by local-regulation logic.
```

This was the same precedence bug as the Heatstrike final coast and is covered by PR #173.

### Operator ABORT at end of water-only run

The test was intentionally stopped rather than continued with known control anomalies.

Observed:

```text
[x] Operator ABORT safe-down worked.
[x] Heater OFF.
[x] Pump OFF.
[x] Heat utilization 0%.
[x] Pump utilization 0%.
[x] Positive control locked out as expected.
```

---

## UI findings from the physical run

Fixed in #173:

```text
[x] BrewAssistant Hub Manual Brewday tile no longer uses BrewTracker `state_not: active` as its ownership gate.
[x] Hub Manual Brewday tile has an explicit entity, avoiding shared button-card JS template errors.
[x] Safety/RCL dashboard accepts both canonical `switch.brewassistant_show_brewzilla_safety_rcl` and legacy `switch.brewassistant_show_safety_rcl`.
```

Known UI item still to correct:

```text
[ ] `Starta mäskcirkulation` compatibility action can be visible outside the narrow post-Mash-In/pump-off window.
    It should only be offered when mash-in is complete, Mash is active, and circulation still needs to be started.
```

The canonical two-step Mash-In flow remains the preferred operator path; stale compatibility controls must not invite an out-of-context action.

---

## Physical mash/ramp timing telemetry (#157)

PR #174 implements #157 as a strictly read-only telemetry layer so the next water-only run can validate timing without changing BrewZilla control behavior.

Key contract:

```text
- ramp timing is separate from mash-hold timing
- mash hold starts only when selected process temperature reaches target band (±0.3°C)
- first mash hold also waits for Mash-In Complete when that gate exists
- PAUSE freezes active process timing
- ABORT stops timing
- Brewfather schedule may run ahead without forcing the physical timer to advance
- source-schedule mismatch is exposed diagnostically
```

Current-brew telemetry records:

```text
ramp/hold kind
from/to temperature
started / target-reached / completed timestamps
duration
wall duration
pause duration
average °C/min for ramps
process-temperature source
Water only / Real mash context
heat utilization start/end
pump utilization start/end
```

Initial UI is intentionally a separate expander card:

```text
dashboard/cards/brewday_physical_timing.yaml
dashboard/cards/brewday_physical_timing_sv.yaml
```

The first implementation is volatile across a Home Assistant restart. Persistence can be added after physical field validation.

---

## External process-temperature ownership

Architecture remains fixed:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  Brewday Runtime owns the optional external process sensor

Boil starts
  Brewday Runtime releases the external process sensor

Chill -> Transfer
  CFC backend owns the same sensor
  role = CFC outlet / wort-out temperature
```

BrewZilla internal temperature remains Brewday Runtime's primary kettle temperature throughout the hot-side path.

This handoff was not reached in the aborted water-only run and remains unverified physically.

---

## Next physical run

The next run should again be supervised and may use water-only to isolate control behavior.

Checkpoint sequence:

```text
1. Planning: visible/ready, no hot-side ownership.
2. Brewing pre-start: still no ownership / no positive action.
3. BrewTracker Play: ownership + pending Supervised Apply.
4. Confirm far Heatstrike plan.
5. Observe Heatstrike taper and confirm final 0% heat / heater-OFF safe-down is physically applied.
6. Observe any supervised pump-utilization increases near strike.
7. At Mash-In Started: stop and verify gate state + pump OFF + pump utilization 0%.
8. Brewfather Continue only after Mash-In Started evidence is captured.
9. Verify 71.8 -> 66.0°C target downshift keeps heat at 0% while process temperature is above target.
10. Validate #157: physical 66°C hold timer starts only on actual target reach and freezes under PAUSE.
11. Validate #157: 66 -> 72°C ramp has independent elapsed time / ΔT / °C/min and the next hold starts only after 72°C is physically reached.
12. Verify Brewsteps follows the BrewTracker-owned physical process.
13. Continue through Mash out / Sparge / Pre-boil / Boil if all prior checkpoints pass.
14. At Boil start verify external-process-sensor release.
15. During Chill/Transfer verify CFC acquisition of the same sensor.
```

This remains supervised beta validation. No unattended/autopilot brewing claim is implied.
