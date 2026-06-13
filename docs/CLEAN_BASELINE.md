# BrewAssistant Clean Baseline

BrewAssistant should have one active Home Assistant custom integration:

custom_components/brewassistant/

Rules:

- No backup folders under /config/custom_components/
- No old BrewAssistant copies under /config/custom_components/
- No dashboard experiment files as source of truth
- No stale entity IDs in backend logic when Home Assistant may prefix entities
- Keep runtime logic simple and observable
- Prefer one clear implementation over parallel fallback/test implementations

Expected Home Assistant custom_components layout:

/config/custom_components/brewassistant

Backups belong outside custom_components, for example:

/config/brewassistant_backups/

Current baseline goals:

- HACS custom repository install works
- Integration loads without backup integrations
- Kegerator climate is restored to cool after startup
- Kegerator fan mode is controlled by one select and one afterrun number
- BrewAssistant backend tolerates HA entity prefixes but does not require them
