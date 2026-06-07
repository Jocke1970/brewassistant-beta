# Project Structure

BrewAssistant is structured around a Home Assistant custom integration with optional dashboard/card YAML.

The main goal is to keep brewing decisions, runtime interpretation, calculations and safety checks in Python, while dashboards focus on presentation and explicit user actions.

---

## Current repository direction

```text
brewassistant/
├── README.md
├── custom_components/
│   └── brewassistant/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── entity.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── switch.py
│       ├── button.py
│       ├── select.py
│       ├── number.py
│       ├── services.yaml
│       ├── carbonation.py
│       ├── brewday/
│       ├── brewzilla/
│       ├── carbonation_backend/
│       ├── climate_backend/
│       ├── cooling/
│       ├── fermentation/
│       ├── kegerator/
│       ├── shared/
│       └── translations/
├── dashboards/
│   └── optional Lovelace dashboard/card examples
└── docs/
    ├── backend-domain-layout.md
    ├── manual-brewday.md
    ├── kegerator-fan-backend.md
    ├── brewzilla-temperature-sources.md
    ├── counterflow-chiller.md
    ├── legacy-package-cleanup.md
    ├── legacy-migration.md
    └── structure.md
```

Legacy `packages/*.yaml` may still exist in older local Home Assistant installs, but they should not be the source of truth for new BrewAssistant logic.

Detailed backend package responsibilities are documented in `docs/backend-domain-layout.md`.

---

## Layer responsibilities

### Python custom integration

The Python integration owns backend logic.

Responsibilities:

- Normalize source entities.
- Normalize Brewfather Brew Tracker and Manual Brewday runtime data.
- Interpret brewday stages.
- Normalize BrewZilla/RAPT hardware telemetry.
- Resolve BrewZilla mash, wort/kettle and mash-wort delta temperature roles.
- Track counterflow wort cooling state.
- Calculate carbonation recommendations and estimates.
- Own carbonation runtime/session state and explicit controls.
- Scope fermentation warnings to active fermentation/cold-crash context.
- Calculate dynamic climate targets for serving/carbonation through Climate Supervisor.
- Infer kegerator compressor/fan state and manage optional fan-auto circulation.
- Expose dashboard-safe sensors and switch diagnostics.
- Expose explicit services.
- Keep safety/orchestration checks outside the dashboard.
- Avoid hidden workflow logic in Lovelace cards.

---

### Platform files

Home Assistant platform files remain in `custom_components/brewassistant/`:

```text
sensor.py
binary_sensor.py
switch.py
button.py
select.py
number.py
```

These files should act as routers/registrars and import backend entities from the domain packages.

---

### `brewday/`

Brewday Runtime normalizes planned/runtime brewday data.

Sources may include:

- Brewfather Brew Tracker.
- Python Manual Brewday runtime.
- Future local/manual plans.

The runtime layer should answer:

- What source is active?
- Is the brewday idle, prepared, running, live, awaiting confirm, paused or completed?
- What is the current stage/step?
- What is the next step?
- How much time remains?
- How old is the last Brewfather snapshot?

`brewday/brewday_runtime_core.py` resolves Brewfather Brew Tracker or None. Python Manual Brewday is handled through `brewday/manual_brewday_runtime.py` and `brewday/manual_brewday_adapter.py`, then selected by `brewday/brewday_runtime.py` when active.

Manual Brewday supports clean restart semantics after a completed state:

```text
Finish → Start
= new run from Setup / Prepare equipment

Finish → Reset → Prepare/Start
= clean new Manual Brewday session
```

Manual Brewday Runtime is Python-owned.

Responsibilities:

- Hold a Manual BIAB-style brewday plan.
- Track active stage and active step.
- Expose a normalized runtime snapshot.
- Support prepare/start/pause/next/finish/reset.
- Support shortcut services for Mash, Boil, Whirlpool and Cooling.
- Restart safely from the beginning after completed state.

Manual Brewday services do not sync old YAML/input-helper mirrors.

---

### `brewday/brewday_stage_engine.py`

The Stage Engine interprets what is actually happening.

Inputs:

- Brewday Runtime state.
- Active Brewday Runtime stage and step.
- BrewZilla runtime state.
- BrewZilla current temperature.
- BrewZilla target temperature.
- BrewZilla power.
- BrewZilla pump/heat utilization.

Outputs:

- Current interpreted stage.
- Stage reason.
- Stage icon.
- Stage group.
- Stage priority.
- Suggested user action.
- Control hint for future explicit-action cards.
- Progress, remaining time and BrewZilla telemetry context.

Important rule:

```text
The active stage/step determines current stage.
next_step must not wake a future stage early.
```

Current explicit stage boundary:

```text
Runtime prepared / Setup / Prepare equipment
→ Stage: Prepare
→ Group: prep
→ Control hint: observe_only
```

This prevents a prepared setup step from being interpreted as Strike Water too early.

The Stage Engine is read-only.

---

### `brewzilla/`

BrewZilla modules own hot-side runtime, temperature roles, learning, energy and orchestration.

BrewZilla Orchestration must read the normalized Brewday Runtime, not only the Brewfather/core runtime, so both Brewfather and Manual Brewday can drive target intent.

Safety rules:

```text
- BrewZilla disconnected blocks orchestration actions.
- Section-specific control policy decides read-only/apply-with-confirm/direct behavior.
- Runtime target may be monitored even when no action is pending.
- RAPT Pill is not used as a hot-side brew temperature source.
```

---

### `brewzilla/brewzilla_temperature.py`

BrewZilla Temperature Resolver is Python-owned and separates process temperature roles from raw RAPT/BrewZilla source entities.

Responsibilities:

- Treat BrewZilla internal temperature as wort/kettle temperature.
- Resolve mash temperature from an operator-selected source.
- Default mash source mode to `Auto`.
- In Auto mode prefer BLE/control-device data, then fall back to internal temperature.
- Expose mash temperature, wort temperature, active mash source, active source entity and mash-wort delta.
- Keep dashboard cards from implementing their own source/fallback logic.

Main operator-facing entities:

```text
select.brewassistant_brewzilla_mash_temperature_source
sensor.brewassistant_brewzilla_mash_temperature
sensor.brewassistant_brewzilla_wort_temperature
sensor.brewassistant_brewzilla_temperature_delta_mash_wort
sensor.brewassistant_brewzilla_mash_temperature_source
sensor.brewassistant_brewzilla_mash_temperature_source_entity
```

See `docs/brewzilla-temperature-sources.md` for the full resolver policy.

---

### `climate_backend/`

Climate Supervisor is the active serving/carbonation climate control layer.

It does not switch the compressor directly.

Responsibilities:

- Determine whether carbonation/serving scope is active.
- Read kegerator air temperature from `sensor.kyl_temperatur_4`.
- Capture a base serving/carbonation target from `climate.kegerator_kylskap`.
- Calculate a dynamic effective air target from air temperature delta.
- Apply the target to `climate.kegerator_kylskap`.
- Let the climate/thermostat integration control `switch.kegerator`.
- Disable the deprecated Kegerator Guard if it is accidentally enabled.
- Expose diagnostics through `switch.brewassistant_climate_supervisor_enabled` attributes.

Current control chain:

```text
Climate Supervisor
→ climate.kegerator_kylskap target
→ thermostat hysteresis/min-cycle/cooldown
→ switch.kegerator
```

This keeps compressor-cycle responsibility in the Home Assistant climate layer, not in BrewAssistant.

---

### `kegerator/`

Kegerator modules own fan/compressor inference and optional fan-auto circulation support.

`kegerator/fan_control.py` is Python-owned and uses live kegerator entities to expose a fan-auto switch with diagnostics.

Responsibilities:

- Infer compressor activity from `sensor.kegerator_power`.
- Infer fan running state from `switch.kegerator_fan` and `sensor.kegerator_fan_power`.
- Keep fan-auto disabled by default.
- Run fan while compressor is active.
- Continue fan after compressor stop for a short afterrun period.
- Ignore impossible restart/statistics warming spikes.
- Use blocking Home Assistant service calls when applying fan on/off actions.
- Leave compressor/cooling target behavior to `climate.kegerator_kylskap`.

Main operator-facing entity:

```text
switch.brewassistant_kegerator_fan_auto_enabled
```

Home Assistant may prefix the final entity id with the integration/device area name.

See `docs/kegerator-fan-backend.md` for full thresholds and validation notes.

---

### `carbonation_backend/`

Carbonation Runtime owns carbonation session state, persistence and operator-facing calculations.

The top-level `carbonation.py` file is kept at the integration root as a Home Assistant-facing module, while the backend runtime lives in `carbonation_backend/` to avoid package/module import collisions.

---

### `cooling/`

Cooling modules own counterflow/wort-cooling runtime, CFC sanitation support, pump requirement, heater guard, ETA and pitch-readiness context.

---

### `fermentation/`

Fermentation modules own fermentation scope logic, fermentation climate helpers and related runtime/safety support.

---

### `shared/`

Shared modules contain utilities that should not be owned by a single domain, such as temperature statistics.

---

## Naming rules

Do not create backend packages that collide with top-level Home Assistant platform/module names.

Known avoided collisions:

```text
carbonation.py          + carbonation_backend/
climate platform/module + climate_backend/
```

This avoids Python importing a package instead of the intended top-level module.
