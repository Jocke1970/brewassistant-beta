# BrewAssistant v0.2.0-beta.8 release notes

## Summary

v0.2.0-beta.8 is the BrewZilla hot-side supervised-control baseline.

This release moves the BrewZilla/Brewfather path from repeated water-test hardening into a baseline that is ready for the first supervised real-mash validation. It is still a beta: the operator must stay present, verify every physical action and be ready to stop BrewZilla directly if the hardware behaves unexpectedly.

## Release focus

```text
BrewAssistant v0.2.0-beta.8
Focus: BrewZilla hot-side supervised control baseline
Status: ready for first supervised real-mash validation
```

This is not a fully unattended automation release. It is the first baseline where the heatstrike, mash-in handoff, runtime audit, RCL recovery and ABORT lockout pieces are aligned enough to test against a real grain bed.

## Highlights

- Clean heatstrike control makes the physical pre-mash-in phase dominant until mash-in starts.
- Mash/BLE/control-probe temperature is the readiness gate for strike temperature.
- Wort/kettle/internal temperature is the safety cap that limits heat when the hot side is racing ahead.
- BrewZilla device target stays clamped to the real strike target instead of a boosted target.
- Pump utilization is raised during heatstrike mixing and equalization.
- Mash-In Started releases the target to the real Brewfather mash target and stops the pump for malt addition/stirring.
- Brewfather Continue/resume can auto-complete mash-in and restart circulation through the supervised path.
- Mash-in state is one-way: late/stale Mash-In Started calls cannot revert `mash_in_complete` back to `mash_in_started`.
- Brewday Event Log autostart now follows normalized Brewday Runtime, with Brewfather Planning as fallback.
- Active hot-side RCL recovery requests non-disruptive refresh while telemetry is flowing.
- RCL reload is suppressed when live BrewZilla temperature or power telemetry is fresh.
- RCL reload is reserved for true hard disconnect or hard-stale telemetry without fresh live temperature/power.
- Legacy heatstrike value-stale recovery is update-only and no longer attempts its own RCL reload.
- ABORT lockout blocks late positive BrewZilla actions, including delayed pump/heater/number-service races.
- Equipment Learning remains passive evidence/suggestion only.

## Validated in supervised water tests

The beta.8 baseline has been validated with repeated supervised water tests covering:

```text
✅ heatstrike to 71.8°C
✅ progressive heat braking near strike target
✅ pump mixing/equalization during heatstrike
✅ mash-in readiness based on Mash/BLE gate
✅ Mash-In Started target release to 66°C
✅ pump off during mash-in handling
✅ Brewfather resume -> auto Mash-In Complete
✅ pump/circulation resume after mash-in complete
✅ 66°C hold behavior
✅ 66 -> 72°C ramp using about 9 min planned ramp time
✅ 72°C hold behavior
✅ 72 -> 77°C / mash-out-style ramp
✅ 77°C hold start
✅ Event Log autostart
✅ RCL soft-stale refresh without needless reload
✅ ABORT safe-down and post-abort lockout
```

## Still unproven

The following items need a real supervised mash/brew before they can be called validated:

```text
[ ] mash-in temperature drop with grain
[ ] Mash/BLE readiness behavior inside a real grain bed
[ ] 66°C hold with malt pipe/grain-bed thermal lag
[ ] 66 -> 72°C ramp with real mash inertia
[ ] mash-out behavior with real mash viscosity
[ ] pump flow without stuck/channeled bed symptoms
[ ] equipment-learning evidence quality for Real mash context
[ ] first post-batch timing/profile advisor observations
```

## Operator model

BrewAssistant remains supervised.

During the first beta.8 real-mash validation, the operator should:

```text
- verify BrewZilla target, heat utilization, pump utilization and pump/heater state before each physical step
- press Mash-In Started only when malt addition/stirring actually begins
- press Brewfather Continue only after mash-in is physically complete
- keep manual BrewZilla/RAPT controls available as fallback
- use ABORT immediately if BA/BZ behavior diverges from expected physical state
- treat Equipment Learning output as evidence, not automatic profile mutation
```

## Expected beta.8 proof markers

Useful Event Log / orchestration markers during the next validation:

```text
clean_heat_strike_active: true
clean_heat_strike_gate_temperature
clean_heat_strike_gate_delta_to_target
clean_heat_strike_safety_temperature
clean_heat_strike_safety_delta_to_target
clean_heat_strike_pump_reason
mash_in_gate_state: ready_for_mash_in -> mash_in_started -> mash_in_complete
mash_in_auto_complete_reason
rcl_active_hot_side_recovery_reload_suppressed_reason
rcl_active_hot_side_recovery_live_telemetry_fresh
rcl_value_stale_guard_reload_requested: false
abort_lockout_final_guard_active
orchestration_apply_blocked:abort_lockout_active
```

## Upgrade / restart notes

- Full Home Assistant restart is recommended after updating to this backend baseline.
- Refresh Lovelace/dashboard cache if updated dashboard cards are copied locally.
- Keep the first real-mash run small and supervised.
- Water-only evidence should not be treated as Real mash learning evidence.

## Next validation target

The next main target is:

```text
First supervised beta.8 real-mash BrewZilla validation
```

That test should produce the first meaningful Real mash evidence for heatstrike timing, mash-in drop, ramp timing, pump behavior and future Brewfather timing/profile advisor suggestions.
