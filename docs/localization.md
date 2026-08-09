# Localization

BrewAssistant uses English as the canonical internal language and Home Assistant translations for user-facing presentation.

## Design rule

```text
Backend identifiers and machine values = stable English
Home Assistant UI labels              = localized presentation
```

The localization layer must never change or become a dependency of BrewAssistant control logic.

## Canonical language

English is the source of truth for BrewAssistant internals and the default UI language.

Keep these stable and in English:

- Python identifiers
- entity IDs
- unique IDs
- suggested object IDs
- attribute keys
- internal states and enum/machine values
- service/action IDs
- runtime keys
- backend policy keys

Swedish is currently the first optional UI localization.

Home Assistant custom-integration translations live in:

```text
custom_components/brewassistant/translations/en.json
custom_components/brewassistant/translations/sv.json
```

Both files should expose the same translation-key structure. `en.json` is canonical; `sv.json` mirrors it with Swedish presentation text.

## Entity naming pattern

For translatable Home Assistant entity names, BrewAssistant uses the entity translation model:

```python
_attr_has_entity_name = True
_attr_translation_key = "stable_backend_key"
```

The entity should not use a hard-coded `_attr_name` when its display name is supplied by translations.

Example:

```python
self._attr_unique_id = "brewassistant_button_brewzilla_mash_in_complete"
self._attr_translation_key = "brewzilla_mash_in_complete"
```

English UI:

```text
BrewAssistant Mash-In Complete
```

Swedish UI:

```text
BrewAssistant Inmäskning klar
```

The underlying entity identity remains unchanged.

## Verified Home Assistant behavior

The localization path was validated end-to-end in August 2026 with a temporary BrewAssistant translation-test button.

Observed behavior:

1. With Home Assistant system language set to English, the new entity displayed `BrewAssistant Translation test`.
2. After changing the Home Assistant system language to Swedish and recreating/reloading the entity, it displayed `BrewAssistant Översättningstest`.
3. Existing BrewAssistant button entity IDs remained unchanged while their display names were localized.

The temporary test entity is not part of the permanent integration surface and was removed after validation.

### Entity registry and dashboard caveats

Home Assistant may preserve a previously registered entity name. A translation change therefore does not guarantee that an old registry entry immediately receives a new display name.

Dashboard YAML can also override the integration-provided name. For translation-aware cards, prefer:

```yaml
entity: button.brewassistant_mash_in_complete
```

instead of:

```yaml
entity: button.brewassistant_mash_in_complete
name: Mash-In Complete
```

Hard-coded dashboard `name:` values are a separate presentation layer and must be reviewed independently.

## Translation ownership by function

Each backend/function should own a clear translation-key namespace even though Home Assistant receives one complete file per language.

Examples:

```text
brewzilla_*
brewday_*
fermentation_*
kegerator_*
carbonation_*
counterflow_chiller_*
climate_*
source_*
runtime_*
```

This keeps translation maintenance aligned with BrewAssistant's modular backend structure without splitting the Home Assistant language files into unsupported per-backend files.

## Current coverage

Status after the August 2026 localization pass:

| UI surface | Status |
| --- | --- |
| Config/options flow | Existing English/Swedish translations |
| Button entity names | Migrated and validated |
| Switch entity names | Migrated; Home Assistant validation pending |
| Number entity names | Migrated; Home Assistant validation pending |
| Sensor entity names | Partial/legacy coverage; newer dynamic sensors still need review |
| Binary-sensor entity names | Partial/legacy coverage; newer dynamic entities still need review |
| Select entity names | Pending |
| Select options / text states | Pending controlled migration |
| Services/actions descriptions | Pending |
| Dashboard hard-coded text | Separate frontend cleanup |

## Migration safety rules

Presentation-only localization work must not change:

- entity IDs
- unique IDs
- restore behavior
- control policies
- runtime keys
- numeric values or limits
- switch states
- hardware actions
- automation-facing machine values

Select options and text states require extra care because existing automations, restored states and backend comparisons may currently depend on English display strings. They should be migrated separately to stable snake_case machine values with compatibility handling where required.

## Remaining work

```text
[ ] Validate translated switch names in Swedish Home Assistant
[ ] Validate translated number names in Swedish Home Assistant
[ ] Inventory all remaining hard-coded entity display names
[ ] Migrate remaining sensor names to translation_key where appropriate
[ ] Migrate remaining binary-sensor names to translation_key where appropriate
[ ] Migrate select entity names
[ ] Design safe migration for select options and translatable text states
[ ] Translate service/action names, descriptions and fields
[ ] Add en/sv translation-key parity validation
[ ] Add Hassfest/localization validation to CI where practical
[ ] Review dashboard YAML for hard-coded presentation text
```
