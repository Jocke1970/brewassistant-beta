# Physical validation — 2026-08-29

This note records the supervised BrewAssistant / Brewfather / BrewZilla validation performed on real Home Assistant hardware on 2026-08-29.

Test baseline after the final restart:

```text
main commit: 0facaf79026687bb3d4e43bac86f4febed07af55
includes: #153 stale switch-echo readback grace
includes: #154 read-only Brewsteps for BrewTracker-owned brewday
```

The purpose of this note is to preserve observed runtime evidence separately from implementation claims in PR descriptions.

---

## Supervised Apply / Brewfather ownership baseline

Observed and accepted earlier in the same physical test sequence:

```text
[x] Brewfather Planning is ready/visible but not hot-side owner.
[x] Brewing before BrewTracker Play remains pre-start and does not send positive BrewZilla actions.
[x] BrewTracker Play creates Brewfather hot-side ownership without rotating the existing Flight Recorder session.
[x] A pending Supervised Apply plan does not perform positive hardware actions before explicit confirmation.
[x] Explicit confirmation applied heat utilization 100%.
[x] Explicit confirmation applied pump utilization 70%.
[x] Explicit confirmation turned heater ON.
[x] Explicit confirmation turned pump ON.
[x] Hardware BrewZilla ABORT turned heater/pump OFF and utilization to 0%.
[x] Hardware ABORT lockout blocked recreated positive orchestration.
```

PR #153 then bounded the remaining RCL switch-echo problem: confirmed heater/pump ON actions receive a short observe-only grace for stale OFF echoes. The guard never auto re-energizes a switch; persistent OFF requires a fresh Supervised Apply confirmation after the grace window.

---

## Brewday operator ABORT — physical regression

The Brewday-level operator ABORT path from #150 was then exercised.

Observed immediately after `ABORT BRYGGDAG`:

```text
[x] Normalized Brewday Runtime = aborted.
[x] Operator control state = aborted / locked.
[x] Previous runtime source remained visible as Brewfather Brew Tracker for diagnostics.
[x] Active runtime ownership was removed.
[x] BrewZilla heater = OFF.
[x] BrewZilla pump = OFF.
[x] Heat utilization = 0%.
[x] Pump utilization = 0%.
[x] BrewZilla orchestration presented blocked/safe state.
[x] Manual Brewday cockpit disappeared because Manual session was reset and no longer owned runtime.
```

This is the intended distinction:

```text
REJECT ACTION / AVVISA ÅTGÄRD
  = reject one pending positive plan

ABORT BREWDAY / ABORT BRYGGDAG
  = physical safe-down + persistent BrewAssistant hot-side ownership lock
```

---

## Persistence across Home Assistant restart

Home Assistant was restarted while the Brewday operator ABORT latch was active.

Observed after restart:

```text
[x] Brewday Runtime still presented ABORTED.
[x] Operator lockout was still active.
[x] Brewfather did not reclaim BrewAssistant hot-side ownership.
[x] BrewZilla remained heater OFF / pump OFF / heat 0% / pump 0%.
[x] Explicit REARM / ÅTERAKTIVERA STYRNING remained available.
```

This physically verifies the storage/startup ordering requirement: the persisted Brewday operator ABORT latch is restored before normal coordinator/orchestration ownership decisions can resume.

---

## Explicit rearm

`ÅTERAKTIVERA STYRNING` was pressed after the restart.

Observed result:

```text
[x] Brewday operator lockout cleared.
[x] Normalized Brewday Runtime returned to idle.
[x] The dashboard again exposed FÖRBERED MANUELL BRYGGDAG.
[x] BrewZilla heater remained OFF.
[x] BrewZilla pump remained OFF.
[x] Heat/pump utilization remained 0%.
[x] No positive BrewZilla action was sent merely because operator control was rearmed.
```

The independent BrewZilla hardware ABORT lockout remains a separate lower-level safety mechanism with its own bounded lifetime. Rearming Brewday control does not itself bypass or clear that lockout.

---

## Dashboard state after validation

The Swedish read-only Brewsteps card from #154 was added to the physical test dashboard:

```text
dashboard/cards/brewassistant_brewsteps_sv.yaml
```

Its next physical validation is intentionally deferred until a Brewfather/BrewTracker-owned active brewday. Expected contract:

```text
runtime_source = Brewfather Brew Tracker
runtime_state != idle
  -> Brewsteps visible
  -> read-only Heat strike -> Transfer process map
  -> no Manual Brewday progression/services exposed
```

At idle after rearm, Brewsteps remains hidden by design.

---

## Resulting next test scope

The short safety/ownership regression is complete. Do not repeat it as a prerequisite unless a later patch touches the same guards.

Next physical sequence:

```text
1. First supervised real-mash Brewfather/BrewTracker run.
2. Heat strike with external process-temperature gate and BrewZilla internal safety view.
3. Real grain addition / mash-in thermal drop.
4. Mash-In Started -> Mash-In Complete transition.
5. Stable 66°C mash hold.
6. Supervised 66 -> 72°C ramp.
7. Verify Brewsteps follows the BrewTracker-owned physical phase.
8. Continue through Mash out / Sparge / Pre-boil / Boil.
9. Verify external process-temperature ownership release at Boil start.
10. Verify CFC acquisition for Chill and continued wort-out use during Transfer.
```

This is still supervised beta validation. No unattended/autopilot brewing claim is implied.
