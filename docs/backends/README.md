# BrewAssistant Backend Documentation

Status: active development / documentation index  
Last synced: 2026-09-05

The canonical short-form documentation now lives beside each backend under `custom_components/brewassistant/<backend>/README.md`. These code-local READMEs describe the currently implemented ownership/control contract.

This `docs/backends/` directory remains useful for deeper architecture notes, historical roadmaps and field-test evidence.

## Canonical current backend READMEs

| Area | Current README |
| --- | --- |
| Integration/backend map | [`../../custom_components/brewassistant/README.md`](../../custom_components/brewassistant/README.md) |
| Brewday Runtime / Manual / Flight Recorder | [`../../custom_components/brewassistant/brewday/README.md`](../../custom_components/brewassistant/brewday/README.md) |
| BrewZilla hot side | [`../../custom_components/brewassistant/brewzilla/README.md`](../../custom_components/brewassistant/brewzilla/README.md) |
| Cooling | [`../../custom_components/brewassistant/cooling/README.md`](../../custom_components/brewassistant/cooling/README.md) |
| Fermentation Tracking | [`../../custom_components/brewassistant/fermentation_tracking/README.md`](../../custom_components/brewassistant/fermentation_tracking/README.md) |
| Fermentation Chamber | [`../../custom_components/brewassistant/fermentation_chamber/README.md`](../../custom_components/brewassistant/fermentation_chamber/README.md) |
| Fermentation compatibility layer | [`../../custom_components/brewassistant/fermentation/README.md`](../../custom_components/brewassistant/fermentation/README.md) |
| Carbonation | [`../../custom_components/brewassistant/carbonation_backend/README.md`](../../custom_components/brewassistant/carbonation_backend/README.md) |
| Kegerator Climate Supervisor | [`../../custom_components/brewassistant/climate_backend/README.md`](../../custom_components/brewassistant/climate_backend/README.md) |
| Kegerator / fan / legacy guard | [`../../custom_components/brewassistant/kegerator/README.md`](../../custom_components/brewassistant/kegerator/README.md) |
| Module/capability registry | [`../../custom_components/brewassistant/modules/README.md`](../../custom_components/brewassistant/modules/README.md) |
| Shared utilities | [`../../custom_components/brewassistant/shared/README.md`](../../custom_components/brewassistant/shared/README.md) |

## Longer reference documents

| Document | Role |
| --- | --- |
| [`brewzilla-backend.md`](./brewzilla-backend.md) | Detailed BrewZilla design/test baseline. Read together with the current code-local README because the wrapper/authority chain continues to evolve. |
| [`../brewzilla-control-profile.md`](../brewzilla-control-profile.md) | BrewZilla heat/pump tuning details and control-profile history. |
| [`../brewzilla-equipment-learning.md`](../brewzilla-equipment-learning.md) | Passive equipment-learning design/history. |
| [`cooling-backend.md`](./cooling-backend.md) | Cooling v2 architecture/roadmap. Its original “implementation pending” sections are historical; current implementation status is documented in `cooling/README.md`. |
| [`fermentation-tracking.md`](./fermentation-tracking.md) | Fermentation Tracking MVP detail and examples. |

## Documentation pattern

A backend README should answer:

```text
What does this backend own?
What does it explicitly not own?
Which runtime/sensor sources does it read?
Which physical entities/services can it write?
Which safety/confirmation boundary applies?
What is persisted vs in-memory?
Which public entities/services expose it?
Which files are authoritative?
Which compatibility layers or known gaps exist?
What must not be changed casually?
```

## Source-of-truth order

When documentation disagrees during active development, use this order:

```text
current executable code
  -> code-local backend README
  -> current architecture/index docs
  -> older roadmap/test/history docs
```

Then fix the drift rather than preserving two competing descriptions.

## Event-log first workflow

For hot-side testing, Brewday Flight Recorder evidence remains the preferred diagnostic truth. Documentation should identify the state/guard/action fields that prove expected behavior instead of relying only on dashboard appearance.
