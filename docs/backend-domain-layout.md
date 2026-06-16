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
├── brand/
│   ├── icon.png
│   └── logo.png
├── carbonation.py
├── brewday/
├── brewzilla/
├── carbonation_backend/
├── climate_backend/
├── cooling/
├── fermentation/
├── kegerator/
├── shared/
└── translations/
```

## Package responsibilities

```text
brewday/
  Brewday runtime, Manual Brewday runtime, stage engine, event log and addition alerts.

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

kegerator/
  Kegerator guard, fan/compressor inference and fan-auto backend.
  The climate integration owns the cooling target and compressor behavior.
  The fan backend manages circulation fan decisions and diagnostics.

shared/
  Shared utilities such as temperature statistics.
```

## Kegerator responsibility split

The kegerator backend is intentionally narrow:

```text
climate.kegerator_kylskap
  cooling target and compressor behavior

kegerator/guard.py
  safety/watchdog diagnostics and climate restart restore guard

kegerator/fan_control.py
  compressor inference from sensor.kegerator_power
  fan-auto runtime diagnostics
  fan mode handling: Off / Always on / Afterrun
  fan circulation decisions

switch.kegerator_fan
  circulation fan entity used by the fan backend
```

This keeps compressor-cycle responsibility in the climate layer rather than in fan automation.

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

## Brand assets

Home Assistant integration brand images live in:

```text
custom_components/brewassistant/brand/icon.png
custom_components/brewassistant/brand/logo.png
```
