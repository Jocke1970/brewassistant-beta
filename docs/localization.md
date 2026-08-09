# Localization

BrewAssistant uses English as the canonical internal language and Home Assistant translations for user-facing presentation.

## Design rule

```text
Backend identifiers and machine values = stable English
Home Assistant UI labels              = localized presentation
Dashboard *.yaml                      = canonical English UI
Dashboard *_sv.yaml                   = Swedish presentation mirror
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

### Entity registry caveat

Home Assistant may preserve a previously registered entity name. A translation change therefore does not guarantee that an old registry entry immediately receives a new display name.

## Dashboard localization

Home Assistant entity translations do not automatically translate BrewAssistant's own Lovelace presentation: headings, button-card JavaScript, markdown, confirmation dialogs, metric labels and explicit `name:` fields are dashboard-owned text.

BrewAssistant therefore keeps a parallel Swedish presentation track:

```text
dashboard/cards/foo.yaml     = canonical English card
dashboard/cards/foo_sv.yaml  = Swedish presentation mirror
```

The current baseline includes Swedish mirrors for all 24 canonical dashboard cards plus the sanity dashboard.

A Swedish mirror may translate:

- card and section headings
- explicit `name:` values
- labels and subtitles
- confirmation dialogs
- markdown text
- human-readable metric labels
- human-readable rendering of backend states

It must not translate or change:

- entity IDs
- service/action IDs
- condition values
- state comparisons used by logic
- attribute keys
- numeric thresholds
- target values
- hardware-control paths

For example, a Swedish card may *display* backend state `Ready to serve` as `Redo att servera`, while continuing to compare the machine value against exactly `Ready to serve`.

Likewise:

```javascript
if (status === 'Carbonating') {
  headline = 'Kolsyrar';
}
```

is valid because the backend state remains English and only presentation is localized.

### Dashboard parity guard

`tests/test_dashboard_language_parity.py` protects the language split in CI.

It verifies that:

- every canonical dashboard card has a `_sv.yaml` mirror
- there are no orphan Swedish mirrors
- the sanity dashboard has a Swedish mirror
- Swedish cards do not introduce entity IDs that are absent from the canonical card
- Swedish cards call the same Home Assistant services/actions as the canonical card

The first CI run of this guard immediately found three canonical BrewZilla UI files that were missing from the older documented baseline: `brewzilla_ble_status.yaml`, `brewzilla_ble_indicator.yaml` and `brewzilla_dual_temperature_gauge.yaml`. All three now have Swedish mirrors as part of the 24-card baseline.

### Dashboard naming caveat

Dashboard YAML can override integration-provided translated entity names. Where the entity's translated standard name is sufficient, prefer:

```yaml
entity: button.brewassistant_mash_in_complete
```

instead of:

```yaml
entity: button.brewassistant_mash_in_complete
name: Mash-In Complete
```

When BrewAssistant intentionally needs a custom cockpit label, explicit `name:` is acceptable and should be localized in the `_sv.yaml` mirror.

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
| Dashboard hard-coded presentation | Swedish mirrors implemented for all 24 canonical cards plus sanity; CI parity guard active; HA visual validation pending |

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

Dashboard localization follows the same safety principle: translate what the operator reads, never what the backend evaluates.

## Remaining work

```text
[ ] Validate translated switch names in Swedish Home Assistant
[ ] Validate translated number names in Swedish Home Assistant
[ ] Visually validate the full *_sv.yaml dashboard baseline in Home Assistant
[ ] Inventory all remaining hard-coded entity display names
[ ] Migrate remaining sensor names to translation_key where appropriate
[ ] Migrate remaining binary-sensor names to translation_key where appropriate
[ ] Migrate select entity names
[ ] Design safe migration for select options and translatable text states
[ ] Translate service/action names, descriptions and fields
[ ] Add en/sv translation-key parity validation
[x] Add dashboard EN/SV filename and machine-reference parity validation
[ ] Add Hassfest/localization validation to CI where practical
[ ] Keep canonical EN and Swedish dashboard mirrors synchronized as UI evolves
```
