# BrewAssistant Clean Baseline

This document describes the expected clean Home Assistant install baseline for the current BrewAssistant beta.

BrewAssistant should have one active Home Assistant custom integration:

```text
custom_components/brewassistant/
```

Rules:

```text
- No backup folders under /config/custom_components/
- No old BrewAssistant copies under /config/custom_components/
- No dashboard experiment files as source of truth
- No stale entity IDs in backend logic when Home Assistant may prefix entities
- Keep runtime logic simple and observable
- Prefer one clear implementation over parallel fallback/test implementations
- Use BrewAssistant button entities for operator actions
- Preserve BrewZilla local regulation when RCL telemetry is stale/disconnected and a valid target is already applied
```

Expected Home Assistant custom_components layout:

```text
/config/custom_components/brewassistant
```

Backups belong outside custom_components, for example:

```text
/config/brewassistant_backups/
```

---

## Current post-#112 baseline goals

```text
✅ HACS custom repository install works
✅ Integration loads without backup integrations
✅ Kegerator climate is restored to cool after startup
✅ Kegerator fan mode is controlled by one select and one afterrun number
✅ BrewAssistant backend tolerates HA entity prefixes but does not require them
✅ Active local HA entity registry has no bryggeriet_ BrewAssistant prefix
✅ Current brewday_event_log sensors exist and are active
✅ Brewday Event Log can autostart from active normalized Brewday Runtime
✅ BrewZilla clean heat-strike uses mash/BLE gate + wort/internal safety cap
✅ BrewZilla local regulation is preserved during RCL stale/disconnected recovery
✅ BrewZilla mash-in gate pending binary sensor exists
✅ BrewZilla Mash-In Started / Complete buttons are one-way through complete state
✅ BrewZilla Mash-In Complete button entity exists
✅ BrewZilla Start Mash Circulation button entity exists
✅ Dashboard cards use button.press for operator actions
```

---

## Current smoke-test entities

After update and Home Assistant restart, verify these in Developer Tools → States:

```text
sensor.brewassistant_core_version
sensor.brewassistant_module_summary
sensor.brewassistant_brewday_event_log_summary
sensor.brewassistant_brewday_event_log_event_count
sensor.brewassistant_brewday_runtime_summary
sensor.brewassistant_brewzilla_control_reason
sensor.brewassistant_brewzilla_requested_target
sensor.brewassistant_brewzilla_applied_target
sensor.brewassistant_brewzilla_can_apply_target
sensor.brewassistant_brewzilla_safety_state
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_brewzilla_mash_in_started
button.brewassistant_brewzilla_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
```

Important orchestration attributes to inspect during hot-side tests:

```text
clean_heat_strike_active
clean_heat_strike_gate_temperature
clean_heat_strike_gate_delta_to_target
clean_heat_strike_safety_temperature
clean_heat_strike_safety_delta_to_target
clean_heat_strike_gate_heat_utilization
clean_heat_strike_safety_heat_cap
clean_heat_strike_pump_reason
mash_in_gate_state
mash_in_gate_pending
mash_in_gate_latched
rcl_active_hot_side_recovery_active
rcl_active_hot_side_recovery_reason
rcl_active_hot_side_recovery_update_requested
rcl_active_hot_side_recovery_reload_requested
rcl_active_hot_side_recovery_local_regulation_preserved
rapt_critical_refresh_recommended
```

The `rcl_active_hot_side_recovery_*` attributes are expected only when RCL/BrewZilla telemetry is stale or disconnected during an active hot-side runtime.

---

## Hot-side supervised verification

Current recommended regression sequence:

```text
1. Water only / system test context.
2. Start Brewfather Brew Tracker or Manual Brewday.
3. Verify Brewday Event Log autostarts within watchdog interval.
4. Heat-strike to ~71.8°C.
5. Press Mash-In Started.
6. Resume Brewfather / let BA auto-complete Mash-In Complete.
7. Hold 66°C.
8. Ramp 66→72°C, currently 9 min test value.
9. Hold 72°C.
10. Ramp / hold toward 77°C.
11. Separate follow-up: ramp to boil + 10 min boil validation.
```

Expected behavior:

```text
✅ Heat-strike target remains the real strike target, not a boosted target
✅ Mash/BLE/control probe decides readiness
✅ Wort/internal/kettle temp caps heat near overshoot
✅ Pump rises for heat-strike or mash/wort delta mixing
✅ Mash-In Started releases strike target and keeps pump paused
✅ Brewfather resume auto-completes mash-in and starts circulation
✅ Late/stale Mash-In Started after complete is ignored
✅ RCL recovery may refresh/reload telemetry but must not alter target/heat/pump
✅ ABORT still forces safe state
```

---

## Local legacy cleanup validation

Validated local cleanup should show:

```text
Prefixed BrewAssistant entities: none expected
Old audit summary: inactive/unknown or removed
Old audit event count: inactive/unknown or removed
Current Event Log summary: present
Current Event Log event count: present
Core version: current installed BrewAssistant version
Module summary: present
```

Historical local snapshots may reference older core versions such as 1.2.0. Treat those as past validation data, not the current beta target.

---

## Operator action policy

```text
UI → button.press → button.brewassistant_* → Python backend
```

Avoid creating duplicate workaround services for the same physical operator action. One action path keeps event logging, safety review and future cleanup manageable.

---

## Documentation policy

Docs should describe the currently merged behavior on `main` plus clearly marked future work. When a docs update follows backend changes, keep it docs-only unless a real code defect is discovered during the sync.

Current docs that should stay aligned with hot-side behavior:

```text
docs/brewday-brewzilla.md
docs/brewday-audit.md
docs/brewzilla-equipment-learning.md
docs/CLEAN_BASELINE.md
```

---

## Notes

This clean baseline is about the active Home Assistant install. Historical backup files, old docs or disabled package snippets may still exist outside the active entity model, but they are not the active runtime source of truth.
