# Project Structure

BrewAssistant v4 is structured around a Home Assistant custom integration with optional dashboard/card YAML.

The main goal is to keep brewing decisions, runtime interpretation, calculations and safety checks in Python, while dashboards focus on presentation and explicit user actions.

---

## Current repository direction

```text
brewassistant/
├── README.md
├── custom_components/
│   └── brewassistant/
│       ├── __init__.py
│       ├── const.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── switch.py
│       ├── number.py
│       ├── select.py
│       ├── brewday_runtime_core.py
│       ├── brewday_runtime.py
│       ├── brewday_runtime_sensor.py
│       ├── brewday_stage_engine.py
│       ├── brewday_stage_sensor.py
│       ├── brewday_refresh.py
│       ├── brewzilla_sensor.py
│       ├── brewzilla_temperature.py
│       ├── brewzilla_learning.py
│       ├── brewzilla_learning_sensor.py
│       ├── brewzilla_orchestration.py
│       ├── brewzilla_orchestration_sensor.py
│       ├── climate_supervisor.py
│       ├── kegerator_guard.py        # deprecated / parked
│       ├── manual_brewday_runtime.py
│       ├── manual_brewday_adapter.py
│       ├── manual_brewday_store.py
│       ├── wort_cooling.py
│       ├── wort_cooling_sensor.py
│       ├── carbonation.py
│       └── carbonation_runtime.py
├── dashboards/
│   ├── brewzilla-cockpit.yaml        # optional Lovelace operator card
│   ├── fermentation-cockpit.yaml     # optional Lovelace fermentation card
│   └── optional dashboard/card examples
└── docs/
    ├── setup.md
    ├── structure.md
    ├── entities.md
    ├── state-machine.md
    ├── manual-mode.md
    ├── dashboard.md
    ├── brewzilla-temperature-sources.md
    ├── climate-supervisor.md
    ├── brewfather.md
    ├── legacy-migration.md
    └── roadmap.md
```

Legacy `packages/*.yaml` may still exist in older local Home Assistant installs, but they should not be the source of truth for new BrewAssistant logic.

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
- Expose dashboard-safe sensors.
- Expose explicit services.
- Keep safety/orchestration checks outside the dashboard.
- Avoid hidden workflow logic in Lovelace cards.

---

### `climate_supervisor.py`

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

### `kegerator_guard.py`

Kegerator Guard was an experimental direct `switch.kegerator` controller.

It is now deprecated / parked.

Current rule:

```text
switch.brewassistant_kegerator_guard_enabled = off
```

Do not build new UI or workflows around Kegerator Guard. Climate Supervisor is the replacement path.

---

### `brewday_runtime_*`

Brewday Runtime normalizes planned/runtime brewday data.

Sources may include:

- Brewfather Brew Tracker.
- Python Manual Brewday runtime.
- Future local/manual plans.

The runtime layer should answer:

- What source is active?
- Is the brewday idle, prepared, running, live, paused or completed?
- What is the current stage/step?
- What is the next step?
- How much time remains?
- How old is the last Brewfather snapshot?

`brewday_runtime_core.py` resolves Brewfather Brew Tracker or None. Python Manual Brewday is handled through `manual_brewday_runtime.py` and `manual_brewday_adapter.py`, then selected by `brewday_runtime.py` when active.

Manual Brewday supports clean restart semantics after a completed state:

```text
Finish → Start
= new run from Setup / Prepare equipment

Finish → Reset → Prepare/Start
= clean new Manual Brewday session
```

---

### `manual_brewday_*`

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

### `brewday_stage_engine.py`

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

### `brewzilla_temperature.py`

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

### `brewzilla_learning.py` and `brewzilla_learning_sensor.py`

BrewZilla Learning is advisory/diagnostic.

Responsibilities:

- Observe BrewZilla heat behavior and temperature trends.
- Use resolved mash temperature during ramp/mash-hold context.
- Use internal wort/kettle temperature during boil/cooling/kettle context.
- Expose learning temperatures, sources, trend and context sensors.
- Avoid making unattended/autopilot decisions.

Learning should use the same temperature resolver that the dashboard displays, so operator-facing UI and advisory calculations stay aligned.

---

### `wort_cooling.py`

Counterflow Wort Cooling models the post-boil chilling process.

Responsibilities:

- Stay in standby until the Stage Engine enters cooling/pitch stage.
- Track reference temperature from BrewZilla/kettle or optional output sensor.
- Compare wort temperature to pitch target.
- Require BrewZilla pump when wort is above target.
- Require heater off during cooling.
- Estimate cooling rate and ETA when trend data exists.
- Expose pitch-ready state.

This module is read-only guidance. It does not control cooling water flow and does not automatically control BrewZilla hardware.

---

### `carbonation_runtime.py` and `carbonation.py`

Carbonation now has Python-owned runtime/session state.

Responsibilities:

- Hold active/paused/reset carbonation runtime state in `hass.data` and persistent HA storage.
- Track method, target volumes, start volumes, actual pressure and start time.
- Resolve carbonation temperature from cooler/kegerator temperature, currently `sensor.kyl_temperatur_4`, with fallback to liquid temperature.
- Calculate recommended pressure from target volumes and current temperature.
- Calculate equilibrium volumes from actual pressure and current temperature.
- Estimate current carbonation volumes over time toward equilibrium.

`carbonation.py` remains a compatibility wrapper around the runtime snapshot builder.

---

### `number.py` and `select.py`

These platforms expose Python-owned local controls.

Current carbonation controls:

```text
number.brewassistant_carbonation_pressure_bar
number.brewassistant_carbonation_target_volumes
number.brewassistant_carbonation_start_volumes
select.brewassistant_carbonation_method
```

Current BrewZilla temperature control:

```text
select.brewassistant_brewzilla_mash_temperature_source
```

These are integration entities, not old helper-backed workflow state.

---

### Fermentation coordinator scope guard

The coordinator exposes fermentation/process sensors while Timed Fermentation Runtime is still future work.

Current guard behavior:

```text
No active fermentation/batch context
→ process: Idle
→ stage: none
→ temperature status: Standby
→ severity/problem: ok
```

A stale cold-crash helper cannot keep Fermentation Cockpit in warning state by itself. Cold crash only counts when there is an active fermentation/batch context.

Dashboard implication:

```text
Idle fermentation context
→ compact Fermentation Cockpit top section
→ heavy climate/debug panels behind expanders or hidden conditionals
```

---

### BrewZilla runtime and orchestration modules

BrewZilla runtime normalizes hardware telemetry.

BrewZilla orchestration safety modules decide whether an explicit user-requested action may run.

Current safety switch pattern:

```text
switch.brewassistant_brewzilla_orchestration_enabled
switch.brewassistant_brewzilla_apply_target_temp
switch.brewassistant_brewzilla_allow_heater_control
switch.brewassistant_brewzilla_allow_pump_control
switch.brewassistant_brewzilla_allow_boil_mode
switch.brewassistant_brewzilla_safe_mode
```

Important rule:

```text
Dashboard buttons may request actions.
Python safety decides whether actions are allowed.
```

---

### Dashboard responsibilities

Dashboard cards should:

- Display current state.
- Provide explicit buttons for user actions.
- Show status, warnings and next steps.
- Expose operator selects/buttons where appropriate.
- Avoid duplicating backend workflow logic.

A card may contain display-only formatting, but the real process state should come from Python sensors/attributes.

Current dashboard milestones/examples:

```text
Climate Supervisor Card v1.0
Counterflow Cooling Cockpit
Carbonation Cockpit v3.1
Fermentation Cockpit v3.1 compact idle card
BrewZilla Cockpit v3.7 mash/wort temperature card
Brewday Card operator cockpit
Brewday Audit Card dashboard example
Brewfather RAW Timeline debug card
```

Optional dashboard examples live under `dashboards/` when available. They are not the source of truth for process logic.

---

## YAML policy

Current policy:

```text
YAML may render.
Python should decide.
```

Allowed YAML use:

- Lovelace/dashboard layout.
- Card styling.
- Display-only formatting.
- Explicit operator actions that call Python services/entities.
- Temporary local testing.

Avoid new YAML use for:

- Process state machines.
- Stage detection.
- Brewday timing logic.
- BrewZilla safety logic.
- Target/source selection logic.
- Hidden automations that duplicate Python services.

`services.yaml` inside the custom integration is allowed and required by Home Assistant as service metadata. It is not workflow logic.

---

## Naming conventions

Recommended v4 naming direction:

```text
brewassistant_*                 Python-owned normalized entities
brewassistant_brewday_*         Brewday Runtime and Stage Engine
brewassistant_brewzilla_*       BrewZilla runtime/orchestration/temperature
brewassistant_wort_*            Wort cooling and pitch-readiness
brewassistant_carbonation_*     Carbonation calculations/runtime
brewassistant_fermentation_*    Future fermentation runtime
brewassistant_climate_*         Climate Supervisor / dynamic air-target logic
brewassistant_source_*          Source diagnostics
```

Legacy names:

```text
fwk_*                           old Fresh Wort Kit specific namespace
brew_process_*                  older process namespace
brew_batch_*                    older batch namespace
brew_recipe_*                   older recipe/runtime namespace
input_boolean/input_number      old workflow helpers where not explicitly provided by integration platforms
```

New development should avoid adding new `fwk_*` entities.

### Numeric suffixes

Avoid Home Assistant-generated numeric suffixes such as `_2`, `_3`, etc. in BrewAssistant source code, normalized entities and documentation.

Numeric suffixes are only acceptable when the number is part of the actual brewing concept, for example:

```text
brew_gravity_check_day_2_done
brew_step_2_status
brew_mash_step_2_temperature
```

If old YAML/template entities block canonical Python entity IDs locally, rename the old entities with a `_yaml` suffix and let Python keep the canonical entity ID.

---

## Design rule

If a piece of logic affects brewing decisions, place it in Python.

If it only affects how something looks, place it in the dashboard card.
