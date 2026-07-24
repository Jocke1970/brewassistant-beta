# Brewday / BrewZilla Direct Flow

This document describes the current BrewAssistant Brewday flow for Brewfather Brew Tracker or Manual Brewday → BrewAssistant → BrewZilla.

Status: **post-#112 supervised hot-side beta flow**. The latest water/system tests validated the core chain from heat-strike through mash-in, 66°C hold, 66→72°C ramp and 72→77°C hold. A longer boil-specific validation is still useful before treating the full brewday path as a final baseline.

The first verified path is BrewZilla/RAPT hardware, but the architecture should remain hardware-profile friendly. BrewAssistant should expose canonical `sensor.brewassistant_brewday_*` and `sensor.brewassistant_brewzilla_*` entities to dashboards instead of making every card parse raw Brewfather data directly.

---

## Current control philosophy

BrewAssistant is an operator-supervised hot-side controller.

```text
Brewfather Brew Tracker or Manual Brewday
        ↓
BrewAssistant normalized Brewday Runtime
        ↓
BrewAssistant BrewZilla orchestration snapshot
        ↓
BrewZilla target / heater / pump / utilization actions
        ↓
Brewday Event Log + diagnostics
```

Important safety boundaries:

```text
- ABORT and completed-runtime safe-down remain authoritative.
- RAPT Cloud Link stale/disconnected telemetry must not silently zero heat/pump.
- Once BrewZilla has a valid local target, BrewZilla may continue local regulation.
- Recovery/diagnostic guards may refresh/reload RCL, but must not change target/heat/pump as part of recovery.
- Operator mash-in confirmation remains explicit and one-way.
```

---

## Verified flow

Recent supervised water/system tests verified:

```text
✅ Brewfather Brew Tracker / Manual Brewday can feed normalized runtime
✅ BrewAssistant follows the runtime target and step sequence
✅ BrewZilla receives target changes through the mash profile
✅ Heat utilization and pump utilization are evaluated and logged
✅ Event Log captures runtime, target sync, actions and RAPT/RCL health signals
✅ ABORT remains available as a hard stop
✅ BrewZilla local regulation continues when a valid target is already applied
```

Current hot-side test profile:

```text
Heat-strike to ~71.8°C
Mash-In Started / Brewfather Continue / Mash-In Complete
Hold 66°C
Ramp 66→72°C, currently tested at 9 min
Hold 72°C
Ramp / hold toward 77°C
Boil validation still pending as its own longer test
```

Water-only tests are useful for runtime, RCL and timing validation, but should not be treated as real-mash thermal-learning evidence.

---

## Why RAW Brew Tracker is used

The convenience entity `sensor.brewfather_brew_tracker_step` may lag behind the Brewfather web UI.

BrewAssistant therefore resolves the active step from:

```text
sensor.brewfather_brew_tracker_raw.attributes.data.stages
stage.remainingSeconds
step.time anchors
```

Implemented in:

```text
custom_components/brewassistant/brewday/brewday_runtime_core.py
```

The normalized runtime wrapper can also use Manual Brewday as the active source:

```text
custom_components/brewassistant/brewday/brewday_runtime.py
custom_components/brewassistant/brewday/manual_brewday_adapter.py
```

The runtime keeps both values for diagnostics:

```text
raw_step_index
resolved_step_index
raw_step_name
```

`raw_step_index != resolved_step_index` is not automatically an error. It often means BrewAssistant has calculated the active step from the stage timeline while Brewfather/RAPT Cloud still exposes an older raw index.

---

## Runtime presentation

Brewfather may create several internal tracker steps with the same recipe name. For example, a ramp and a hold can both be named `Step 6 - 55C final low-temp sync`.

BrewAssistant exposes human-friendly labels such as:

```text
Ramp to 55°C
Hold 55°C · 2 min
```

instead of displaying duplicated raw names as current and next step. The original Brewfather name remains available as `raw_step_name` in attributes for debug use.

During clean heat-strike the operator UI should prefer BrewAssistant's physical state over Brewfather's parked next step. Brewfather can already be paused at a lower mash step while BrewAssistant is still physically heating strike water.

---

## Paused Brewfather behavior

When Brewfather status is paused, BrewAssistant treats the snapshot as a freeze-frame:

```text
runtime_state = paused
awaiting_snapshot = false
paused_freeze = true
live_timer_active = false
```

BrewAssistant keeps the current step and target instead of advancing into `awaiting_snapshot` just because remaining time reaches zero while paused.

---

## Target and output actions

Target sync and hardware output actions are separate decisions.

The orchestration layer evaluates:

```text
target_sync_needed
heater_action_needed
heater_stop_needed
pump_action_needed
pump_stop_needed
heat_utilization_action_needed
pump_utilization_action_needed
```

Therefore this case is valid and should trigger an action:

```text
Brew Tracker target = 30°C
BrewZilla target = 30°C
BrewZilla current = 25.6°C
heater = off

→ target_sync_needed = false
→ heater_action_needed = true
→ heater should turn on
```

Implemented in:

```text
custom_components/brewassistant/brewzilla/brewzilla_orchestration.py
```

`target_delta` means synchronization delta:

```text
requested_target - applied_target
```

It is not the same as temperature delta:

```text
current_temperature - target_temperature
```

---

## Clean heat-strike model

The current pre-mash-in heat-strike model is intentionally physical-state dominant.

```text
Mash/BLE/control probe = readiness gate
Wort/kettle/internal = safety cap against overshoot
Pump utilization = mixing tool when wort/internal runs hotter than mash/BLE
BrewZilla target = real strike target, not a boosted target
```

Expected heat schedule from the gate delta:

```text
>10°C below strike: 100%
8–10°C below strike: 75%
5–8°C below strike: 50%
3–5°C below strike: 25%
1–3°C below strike: 10%
<=1°C below strike / overshoot: 0%, heater off
```

Safety cap uses the hottest wort/kettle/internal view as a limiter, so desired heat is effectively:

```text
min(gate_heat, safety_cap)
```

Pump mixing floors during heat-strike:

```text
large wort-mash delta: 100%
mid delta: 90%
small delta: 80%
otherwise: 70–100% depending on strike proximity
```

Do not rewrite this model casually. Small threshold or diagnostic changes are acceptable after logs show a specific reason.

---

## Mash-in state machine

Mash-in is an operator-supervised transition.

Normal flow:

```text
1. Heat-strike reaches readiness gate on mash/BLE/control probe.
2. BrewAssistant shows Mash-In Started.
3. Operator presses Mash-In Started when malt addition starts.
4. BrewAssistant releases strike target to the effective mash target and keeps pump paused.
5. Operator presses Continue/FORTSÄTT in Brewfather when mash-in is physically complete.
6. BrewAssistant auto-runs Mash-In Complete when Brewfather resumes in mash context.
7. Mash circulation starts.
```

Manual `Mash-In Complete` remains a fallback button.

Post-#112 guardrail:

```text
mash_in_ready → mash_in_started → mash_in_complete
```

is one-way. A stale or late Mash-In Started call after `mash_in_complete` must be ignored and logged as an ignored action, not move the state machine backwards.

Relevant modules:

```text
custom_components/brewassistant/brewzilla/brewzilla_mash_in_gate.py
custom_components/brewassistant/brewzilla/brewzilla_mash_in_complete_safe_down_guard.py
custom_components/brewassistant/brewzilla/brewzilla_mash_in_state_guard.py
```

---

## Brewday audit autostart

Autostart should no longer depend only on exact Brewfather `Planning` state. Post-#112 behavior:

```text
Primary gate:
- normalized Brewday Runtime is active/trusted
- runtime source is Brewfather Brew Tracker or Manual Brewday
- runtime stage/step is hot-side relevant
- BrewZilla/RAPT backend entities are present
- audit/event log is inactive
- runtime is not completed/idle/archived

Fallback gate:
- Brewfather batch status Planning, for early startup/race conditions
```

The watchdog still runs at about 30 s intervals while the event log is inactive. The last autostart decision is stored in:

```text
hass.data["brewassistant"]["brewday_audit_autostart_last_result"]
```

---

## Active hot-side RCL recovery

RAPT Cloud Link may become stale or disconnected while BrewZilla is already holding a valid local target. BrewAssistant should attempt recovery without changing live control state.

Post-#112 recovery behavior:

```text
When active hot-side runtime + RCL/BrewZilla stale/disconnected:
- request homeassistant.update_entity for known RCL/BrewZilla entities
- request throttled homeassistant.reload_config_entry when available
- expose rcl_active_hot_side_recovery_* diagnostics on orchestration attributes
- set rapt_critical_refresh_recommended true
- preserve BrewZilla local target/regulation
- do not change target, heat utilization, pump utilization, heater or pump as part of recovery
```

Relevant module:

```text
custom_components/brewassistant/brewzilla/brewzilla_active_rcl_recovery_guard.py
```

---

## Refresh policy

BrewAssistant requests Brewfather entity refreshes through a smart refresh policy.

Implemented in:

```text
custom_components/brewassistant/brewday/brewday_refresh_policy.py
custom_components/brewassistant/brewday/brewday_refresh.py
```

Policy overview:

```text
Normal real batch:
- Mash / boil / other active stage: about every 5 minutes
- Chilling: about every 2 minutes
- Idle/setup/cleanup: about every 10 minutes

Test batch / short-step recipe:
- about every 30 seconds

Step ending soon:
- about every 15 seconds

Awaiting snapshot:
- about every 15 seconds with a bounded burst limit

Minimum cooldown:
- 10 seconds
```

Manual refresh is still available as a service, but normal operation should not require an Apply Target button.

---

## Event log

Brewday Event Log records post-run analysis data for runtime and BrewZilla orchestration.

Current service names are kept for compatibility:

```text
brewassistant.brewday_audit_start
brewassistant.brewday_audit_stop
brewassistant.brewday_audit_clear
brewassistant.brewday_audit_snapshot
```

Main sensor:

```text
sensor.brewassistant_brewday_event_log_summary
```

Event Log uses normalized runtime, so both Brewfather Brew Tracker and Manual Brewday can provide stage, step and target context.

Important new diagnostic families:

```text
mash_in_gate_*
rcl_active_hot_side_recovery_*
rapt_brewzilla_*_age_seconds
ba_owned_* utilization/reassert fields
```

`last_target` prefers runtime target, but can fall back to requested/applied/device target values for action events where the runtime target was unavailable in older stored events.

---

## Current timing guidance

Observed water/system-test guidance after the latest supervised runs:

```text
Heat-strike time in Brewfather: about 30 min for the current small-test setup
Ramp 66→72°C: 9 min is a better current test value than 5 min
```

Treat these as recipe/test-profile hints, not backend constants.

Future equipment learning should compare planned vs actual timing by segment and present advisory Brewfather timing suggestions without automatically changing Brewfather or live control behavior.

---

## Remaining validation

Recommended next checks:

```text
✅ Heat-strike still uses clean gate/safety/pump model
✅ Event Log autostarts from active runtime
✅ RCL recovery exposes diagnostics and does not change target/heat/pump
✅ Mash-In Started cannot revert mash_in_complete
⏳ Full boil ramp + 10 min boil validation
⏳ Real-mash thermal validation, separate from Water only learning
```
