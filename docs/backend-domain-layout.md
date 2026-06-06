# Backend Domain Layout

BrewAssistant backend modules are grouped by responsibility under `custom_components/brewassistant/`.

Home Assistant platform files remain at the integration root. Backend/domain logic lives in subpackages.

## Current layout

```text
custom_components/brewassistant/
├── __init__.py
├── manifest.json
├── config_flow.py
├── const.py
├── coordinator.py
├── entity.py
├── sensor.py
├── binary_sensor.py
├── switch.py
├── button.py
├── select.py
├── number.py
├── services.yaml
├── carbonation.py
├── brewday/
├── brewzilla/
├── carbonation_backend/
├── climate_backend/
├── cooling/
├── fermentation/
├── shared/
└── translations/
```

## Package responsibilities

```text
brewday/
  Brewday runtime, Manual Brewday runtime, stage engine, audit and addition alerts.

brewzilla/
  BrewZilla runtime, temperature resolver, learning, energy and orchestration.

carbonation_backend/
  Python-owned carbonation runtime/session backend.

climate_backend/
  Climate Supervisor backend.

cooling/
  Counterflow/wort cooling and sanitation support.

fermentation/
  Fermentation and fermentation climate support.

shared/
  Shared utilities such as temperature statistics.
```

## Naming rule

Do not create backend packages that collide with top-level Home Assistant platform/module names.

Known avoided collisions:

```text
carbonation.py          + carbonation_backend/
climate platform/module + climate_backend/
```

This avoids Python importing a package instead of the intended top-level module.

## Platform-root rule

Keep Home Assistant platform entry files at the integration root:

```text
sensor.py
binary_sensor.py
switch.py
button.py
select.py
number.py
```

Those files should act as routers/registrars and import backend entities from the domain packages.
