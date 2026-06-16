# BrewAssistant Clean Baseline

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
```

Expected Home Assistant custom_components layout:

```text
/config/custom_components/brewassistant
```

Backups belong outside custom_components, for example:

```text
/config/brewassistant_backups/
```

## Current baseline goals

```text
✅ HACS custom repository install works
✅ Integration loads without backup integrations
✅ Kegerator climate is restored to cool after startup
✅ Kegerator fan mode is controlled by one select and one afterrun number
✅ BrewAssistant backend tolerates HA entity prefixes but does not require them
✅ Active local HA entity registry has no bryggeriet_ BrewAssistant prefix
✅ Old brewday_audit sensors are inactive/unknown
✅ Current brewday_event_log sensors exist and are active
```

## Local legacy cleanup validation

Validated in the active Home Assistant install:

```text
Prefixed BrewAssistant entities: none found
Old audit summary: unknown
Old audit event count: unknown
Current Event Log summary: empty
Current Event Log event count: 0
Core version: 1.2.0
Module summary: Base ready · 5 enabled · 7 optional disabled
```

This means the active local install is now aligned with the Python/custom-integration clean baseline. Historical backup files, old docs or disabled package snippets may still exist outside the active entity model, but they are not the active runtime source of truth.
