# Brewday / BrewZilla: physical mash and grain-bed settling test plan — 2026-09-19

Status: **code and CI validation only; HA/RAPT/BrewZilla field validation pending**. This is a supervised development test, not unattended brewing control. Applies to current combined `dev`, not `main`/`beta`. HLT remains **simulation-only** and is not part of the physical test.

## Scope and behavior under test

Brewfather provides the recipe schedule, but its step advancing to 72 °C must not raise BrewZilla above the still-active **physical 66 °C hold**. Mash-In Started releases strike target and keeps the pump off; an observed Brewfather PAUSED after Started followed by RUNNING is the normal Mash-In Complete acknowledgement. Manual Complete is a fallback, not a separate pump-start grant.

At Complete: pump utilization 0% and switch OFF; begin a 10-minute settling substate parallel to the physical mash hold. After ten minutes, a button may **propose** 25% utilization; only an explicit operator press may command LOW FLOW. Require actual device readback before a five-minute low-flow interval begins. Afterwards propose 50%, requiring a **second** operator confirmation. A completed physical hold and confirmed normal-flow state are jointly required before the next Brewfather target is released. The recipe/physical hold timer starts on its existing Mash-In Complete plus process-temperature-within-±0.3 °C criteria, not merely when the settling timer begins.

Pump percentages are configured utilization setpoints, **not verified flow measurements**. No flow or level sensor exists; observe the liquid level and drainage yourself. The interlock's timers do not energize a pump. Process-temperature freshness must be valid for either positive pump command; stale observations must refuse the command. On HA restart mid-mash, the volatile phase must not be inferred from Brewfather's later step; expect recovery lockout, not silent pump restart. ABORT and independent safety always override the sequence.

## Preparation and installation

1. Finish the current run and ensure BrewZilla is idle, pump/heater OFF. Back up the installed BrewAssistant integration and current dashboard YAML; record the installed revision. Do not overwrite the entire installation with an older branch archive because other work is integrated on `dev`.
2. Update the whole `custom_components/brewassistant` integration from **current `dev`**, not `main`, `beta` or an older feature branch. Restart Home Assistant fully. Update the actual dashboard card in use from `dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml` and/or `dashboard/cards/brewzilla_mash_in_controls_sv.yaml`; the GitHub commit does not automatically replace dashboard YAML already pasted into HA. Refresh dashboard browser cache.
3. In HA Developer Tools / States verify `sensor.brewassistant_brewzilla_control_reason` has `physical_mash_interlock_active`, `mash_recirculation_phase`, `mash_physical_hold_target`, and countdown/readback fields in the relevant phases. Verify `button.brewassistant_start_mash_circulation` exists. Check that the process probe is fresh, BrewZilla target, heater utilization, pump utilization and both switches report actual values. Verify the hardware ABORT is accessible. **Stop before physical testing if any entity or attribute is missing.**
4. Do the initial source/timeline and target-ownership check with cold hardware/observation where possible. Use a separate **attended water-only run** for pump command/readback checks at suitable operating water level and in accordance with BrewZilla's minimum-volume and pump instructions. Water alone cannot validate a grain bed; follow with a separately supervised small grist trial only after the telemetry/target gates pass. Do not heat a dry vessel or leave heating unattended.

## Step-by-step evidence to record

| Checkpoint | Expected BA behavior | Physical / RCL evidence |
| --- | --- | --- |
| BF Play, Heatstrike, READY | Existing heatstrike and ±1 °C automatic readiness/±2 °C operator override remain unchanged. | Source, live process and kettle temperature, BZ target, heater/pump readback. |
| Mash-In Started | BF must be observed PAUSED **after** Started for auto Complete. Strike target lowers to real mash hold target; pump OFF and 0%. | Time, `mash_in_gate_state`, effective target, target readback and pump readback. |
| Brewfather Continue | Backend marks Mash-In Complete and enters `settling`, **no automatic pump start**. | BF PAUSED→RUNNING timestamps; BZ utilization 0%, switch OFF. |
| During settling, 0–10 min | `settling`; 66 °C physical target remains authoritative even if BF next target is 72 °C; low-flow button hidden. | Requested vs applied target, physical timer, process and kettle temperature, actual heat and pump outputs. |
| Settling expires | `recirculation_ready` only; **no pump command from timer**. | Countdown reaches 0; switch remains OFF. |
| First operator confirmation | With fresh process temperature and pump verified OFF, command ~25%, switch ON; `low_flow_pending` until readback, then `low_flow`. | Operator confirmation timestamp, utilization and switch `last_reported`, actual flow / visual liquid level. |
| Five minutes after low-flow readback | `normal_ready`; 25% continues; **no automatic increase**. | Phase, timer, utilization readback, grain-bed/drainage visual check. |
| Second operator confirmation | After fresh probe and visible good drainage, command ~50%; `normal_pending` then `normal` only after readback. | Timestamp, actual utilization and switch readback, liquid level. |
| Before 66 °C hold completes | BF may display next step, but BA still requests physical 66 °C. | Compare BF target, BA requested target and actual BZ target. |
| When physical 66 °C hold completes, normal flow confirmed | Interlock releases next step; follow-up 66→72 °C ramp is allowed through existing supervised/safety controls. | `mash_physical_hold_complete`, phase, BF/BA/BZ targets, actual heating onset. |
| Stale process probe or pump readback timeout | No new pump start without fresh probe; readback timeout sets `blocked` after 120 s. | Error reason, no positive writes; ABORT / diagnose rather than retry blindly. |
| Source change, ABORT, unexpected HA restart | Never infer a positive pump grant or advance from BF alone; require explicit recovery/new safe session. | Phase `blocked`/`recovery_required`, outputs and audit trail. |

**Stop criteria:** actual target rises to a future recipe target while 66 °C hold is incomplete; pump starts or jumps in utilization without operator acknowledgement; liquid climbs above the grain bed, runoff stalls, kettle temperature diverges dangerously from mash temperature, pump loses prime, outputs disagree with readback, or source/session state becomes ambiguous. Take manual control / press ABORT as appropriate and log observed states before resetting. Do **not** treat a passing GitHub Actions run as verification of hardware safety.

## Outcome to capture

Record Git commit SHA, HA version, integration version, dashboard YAML version, Brewfather recipe and exact step durations, batch volume, grain bill and mill gap, controller source, RCL report timestamps, both temperature traces, BZ target/heat/pump setpoint and readback, each operator button press, Flight Recorder/audit export, and any error or unexpected automatic write. Mark each table row **PASS / FAIL / NOT TESTED**. Only after a successful attended test should this code be considered for promotion to `beta`. Follow-up engineering work should explicitly review conservative heating while the pump is OFF and real post-command pump readback semantics before any unattended use.
