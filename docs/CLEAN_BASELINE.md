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

## Current beta.7 baseline goals

```text
✅ HACS custom repository install works
✅ Integration loads without backup integrations
✅ Kegerator climate is restored to cool after startup
✅ Kegerator fan mode is controlled by one select and one afterrun number
✅ BrewAssistant backend tolerates HA entity prefixes but does not require them
✅ Active local HA entity registry has no bryggeriet_ BrewAssistant prefix
✅ Current brewday_event_log sensors exist and are active
✅ BrewZilla mash-in gate pending binary sensor exists
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
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_brewzilla_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
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

Historical local snapshots may reference older core versions such as 1.2.0. Treat those as past validation data, not the current beta.7 target.

---

## Operator action policy

```text
UI → button.press → button.brewassistant_* → Python backend
```

Avoid creating duplicate workaround services for the same physical operator action. One action path keeps event logging, safety review and future cleanup manageable.

---

## Notes

This clean baseline is about the active Home Assistant install. Historical backup files, old docs or disabled package snippets may still exist outside the active entity model, but they are not the active runtime source of truth.
