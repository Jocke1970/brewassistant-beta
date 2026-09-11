# BrewAssistant Python backend layout

Status: active development  
Code/documentation snapshot: 2026-09-11

This directory contains the Home Assistant integration entry points plus the Python-owned BrewAssistant backend domains.

The code-local `README.md` files are the first place to check when changing backend ownership or control boundaries. Longer documents under `docs/` provide design history, test notes and deeper background, but may describe an earlier implementation state.

## Directory map

| Directory | Role | Control level |
| --- | --- | --- |
| [`brewday/`](./brewday/) | Normalized Brewday Runtime, Manual Brewday, stage interpretation, physical timing and flight recorder | Runtime/state ownership; no generic hardware control |
| [`brewzilla/`](./brewzilla/) | BrewZilla/RAPT hot-side adapter and physical control/safety chain | Hardware control with phase authority, guards and ABORT |
| [`cooling/`](./cooling/) | Cooling Runtime v2, CFC/immersion/manual cooling and cooling advice | Read/advice today; BrewZilla wort pump is operator-owned |
| [`fermentation_tracking/`](./fermentation_tracking/) | Independent SG/temperature observations, calculations, readiness and process-level beer target recommendation | Read/track/strategy only; hardware-agnostic |
| [`fermentation_chamber/`](./fermentation_chamber/) | Current fermentation physical provider: chamber-air target translation and supervised climate target bridge | Recommendation + Supervised Apply target write |
| [`fermentation/`](./fermentation/) | Compatibility imports for the separated fermentation backends | Compatibility only |
| [`carbonation_backend/`](./carbonation_backend/) | Persistent carbonation session and pressure/volume guidance | Read/guidance only |
| [`climate_backend/`](./climate_backend/) | Kegerator Climate Supervisor | Direct climate-target adjustment when enabled/in scope |
| [`kegerator/`](./kegerator/) | Serving-fridge guard, fan control/model and serving presets | Policy-mediated fan/legacy guard actions |
| [`modules/`](./modules/) | Capability/module manifests and registry | Metadata only |
| [`shared/`](./shared/) | Cross-domain helpers, currently rolling temperature statistics | Read-only support |
| `brand/` | Home Assistant integration artwork | Assets only |
| `translations/` | Home Assistant strings (`en`, `sv`) | Presentation only |

## Root files

The Home Assistant platform entry files stay at the integration root:

```text
sensor.py
binary_sensor.py
switch.py
button.py
select.py
number.py
```

They should primarily register/route entities into backend code rather than become new backend domains.

Other important root services:

- `__init__.py` wires startup, runtime loading, service registration and the current kegerator restart restore helper.
- `coordinator.py` provides normalized integration data used by several read-only domains.
- `control_policy.py` is the common action-policy layer used by selected backends such as the kegerator.
- `supervised_apply.py` owns the generic pending/confirm/reject flow used by backends such as `fermentation_chamber` and generic BrewZilla positive actions.
- `configured_entities.py` and `const.py` centralize configured source entities and constants.
- `source_health.py`, `smart_recommendations.py`, `next_action.py`, `workflow.py` and `runtime.py` are core/support surfaces rather than standalone hardware backends.

## Ownership rules that cross directories

### Brewday -> BrewZilla

`brewday` owns normalized process intent. `brewzilla` converts trusted hot-side intent into BrewZilla/RAPT control decisions. Brewday Runtime must remain usable without BrewZilla.

### External process-temperature handoff

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  owner: hot-side Brewday/BrewZilla path

Boil starts
  hot-side releases external process probe

Chill -> Transfer
  owner: Cooling
  role: CFC wort-out/process temperature when counterflow cooling is selected
```

The BrewZilla internal temperature remains the kettle/safety temperature and must not silently replace an owned CFC outlet sensor.

### Fermentation strategy -> physical provider -> local regulator

The fermentation architecture is deliberately split into three levels:

```text
fermentation_tracking
  observations / readiness / desired beer target
        |
        v
selected physical provider
  translate desired beer target for downstream controller
        |
        v
local controller
  owns actual heat/cool regulation
```

Today `fermentation_chamber` is the implemented physical provider. It translates the desired beer/liquid temperature into a chamber-air target and places target changes behind Supervised Apply. After that target is accepted, the downstream Home Assistant climate controller owns actual heater/cooler regulation.

Future fermentation hardware providers, such as a Grainfather fermenter provider, should follow the same contract rather than adding another thermostat loop inside BrewAssistant. Only one physical provider may have write authority for a fermentation session.

The legacy `fermentation/` package only preserves old imports/registrations and must not become the owner of new strategy, provider selection or hardware logic.

See [`../../docs/backends/fermentation-control.md`](../../docs/backends/fermentation-control.md) for the generic provider contract and future-provider rules.

### Kegerator split

The Home Assistant climate integration owns normal compressor regulation. `climate_backend` adjusts the climate target when its supervisor is enabled and carbonation/serving scope is active. `kegerator/fan_control.py` owns only the circulation fan. `kegerator/guard.py` is a separate legacy/policy-mediated compressor guard and restart watchdog and should not be confused with the Climate Supervisor.

## Documentation rule

When backend behavior changes, update the README in the owning directory in the same PR. Document:

1. responsibility and explicit non-responsibilities;
2. source data and owned state;
3. physical writes, if any;
4. safety/confirmation boundaries;
5. persistence or in-memory state;
6. important public entities/services;
7. compatibility layers and known implementation gaps.
