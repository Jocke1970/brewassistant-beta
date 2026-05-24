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
│       ├── brewday_runtime_core.py
│       ├── brewday_runtime.py
│       ├── brewday_runtime_sensor.py
│       ├── brewday_stage_engine.py
│       ├── brewday_stage_sensor.py
│       ├── brewday_refresh.py
│       ├── brewzilla_sensor.py
│       ├── brewzilla_orchestration.py
│       ├── brewzilla_orchestration_sensor.py
│       ├── manual_brewday_runtime.py
│       ├── manual_brewday_adapter.py
│       ├── manual_brewday_store.py
│       ├── wort_cooling.py
│       ├── wort_cooling_sensor.py
│       └── carbonation.py
├── dashboards/
│   └── optional dashboard/card examples
└── docs/
    ├── setup.md
    ├── structure.md
    ├── entities.md
    ├── state-machine.md
    ├── manual-mode.md
    ├── dashboard.md
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
- Track counterflow wort cooling state.
- Calculate carbonation recommendations and estimates.
- Expose dashboard-safe sensors.
- Expose explicit services.
- Keep safety/orchestration checks outside the dashboard.
- Avoid hidden workflow logic in Lovelace cards.

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

---

### `manual_brewday_*`

Manual Brewday Runtime is Python-owned.

Responsibilities:

- Hold a Manual BIAB-style brewday plan.
- Track active stage and active step.
- Expose a normalized runtime snapshot.
- Support prepare/start/pause/next/finish/reset.
- Support shortcut services for Mash, Boil, Whirlpool and Cooling.

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

Example:

```text
Current: Whirlpool / hop stand
Next: Chill wort
→ Stage Engine stays in Whirlpool
→ Cooling Cockpit remains standby
```

The Stage Engine is read-only.

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

### `carbonation.py`

Carbonation currently provides read-only carbonation calculations and dashboard sensors.

Current status:

```text
Carbonation Cockpit UI exists.
carbonation.py still uses helper-style entities for process state and input values.
```

Planned direction:

```text
Python-owned Carbonation Runtime/session
explicit start/update/pause/reset services
optional pressure and temperature source mapping
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
- Avoid duplicating backend workflow logic.

A card may contain display-only formatting, but the real process state should come from Python sensors.

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
- Temporary local testing.

Avoid new YAML use for:

- Process state machines.
- Stage detection.
- Brewday timing logic.
- BrewZilla safety logic.
- Target selection logic.
- Hidden automations that duplicate Python services.

`services.yaml` inside the custom integration is allowed and required by Home Assistant as service metadata. It is not workflow logic.

---

## Naming conventions

Recommended v4 naming direction:

```text
brewassistant_*                 Python-owned normalized entities
brewassistant_brewday_*         Brewday Runtime and Stage Engine
brewassistant_brewzilla_*       BrewZilla runtime/orchestration
brewassistant_wort_*            Wort cooling and pitch-readiness
brewassistant_carbonation_*     Carbonation calculations
brewassistant_fermentation_*    Future fermentation runtime
brewassistant_source_*          Source diagnostics
```

Legacy names:

```text
fwk_*                           old Fresh Wort Kit specific namespace
brew_process_*                  older process namespace
brew_batch_*                    older batch namespace
brew_recipe_*                   older recipe/runtime namespace
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
