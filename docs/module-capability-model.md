# BrewAssistant Module & Capability Model

This document turns the target architecture into a practical module and capability model.

The purpose is to make BrewAssistant installable and expandable without creating entities, actions or dashboards for hardware/modules the user has not enabled.

~~~text
Core idea:
- Core and base workflow are always available.
- Optional modules are enabled explicitly.
- Source providers expose data.
- Hardware adapters normalize device-specific entities.
- Capabilities decide what can be read, recommended or controlled.
- Control policy is scoped per capability.
~~~

---

## Policy values

~~~text
disabled       Capability is not enabled or not available.
read_only      Observe and display state, but never apply an action.
confirm        Prepare/suggest an action, but require operator confirmation.
direct         Apply the action directly when safety checks pass.
guidance_only  Calculate/recommend, but no device action exists.
~~~

Recommended beta defaults:

~~~text
Heater control                  confirm
Pump control                    confirm
Kegerator fan-auto              direct
Fermentation chamber target     read_only or confirm
Carbonation pressure guidance   guidance_only
Notifications                   read_only until configured
~~~

---

## Module matrix

| Module | Default | Type | Primary role |
| --- | --- | --- | --- |
| Core | enabled | base | Version, module registry, diagnostics, next action. |
| Brewday Runtime | enabled | base | Manual/Brewfather-normalized brewday process. |
| Fermentation Tracking | enabled | base | Fermentation lifecycle/status tracking. |
| Carbonation Guidance | enabled | base/guidance | CO2 volumes, temperature and pressure recommendations. |
| Source Health / Diagnostics | enabled | base | Source availability, stale data, registry health. |
| BrewZilla | disabled | hardware adapter | Hot-side adapter for BrewZilla/RAPT hardware. |
| Grainfather | disabled | hardware adapter | Future hot-side adapter. |
| Kegerator / Serving | disabled | module/adapter | Serving fridge, cooling state and fan-auto. |
| Fermentation Chamber Control | disabled | module/adapter | Active chamber temperature management. |
| BrewCreator / Fercubator | disabled | source/adapter | Future chamber adapter through HA integration. |
| Counterflow Chiller | disabled | module | Cooling and sanitation workflow support. |
| Notifications | disabled | module | Mobile/persistent notifications. |
| Advanced Diagnostics | disabled | module | Detailed debug cards and source introspection. |

---

## Base modules

### Core

Default: enabled.

Responsibilities:

~~~text
- expose BrewAssistant version
- expose enabled/available module status
- expose next_action / source health summary
- own module registry and capability registry
- provide shared helpers for policy checks
~~~

Suggested entities:

~~~text
sensor.brewassistant_core_version
sensor.brewassistant_next_action
sensor.brewassistant_module_summary
sensor.brewassistant_capability_summary
sensor.brewassistant_source_health
~~~

Capabilities:

~~~text
read_core_status          read_only
read_module_status        read_only
read_capability_status    read_only
~~~

### Brewday Runtime

Default: enabled.

Responsibilities:

~~~text
- manual brewday runtime
- Brewfather-derived runtime resolver when available
- normalized stage/step/status/progress
- source selection/fallback
- handoff context to fermentation tracking
~~~

Required sources:

~~~text
None. Manual runtime must work without external integrations.
~~~

Optional sources:

~~~text
Brewfather Home Assistant integration
Generic recipe/runtime entities
~~~

Capabilities:

~~~text
read_brewday_runtime      read_only
start_manual_brewday      confirm
pause_manual_brewday      confirm
finish_manual_brewday     confirm
reset_manual_brewday      confirm
handoff_to_fermentation   confirm
~~~

Important rule:

~~~text
Brewday Runtime must not depend on BrewZilla.
BrewZilla, Grainfather or other hot-side systems should consume normalized runtime state through adapters.
~~~

### Fermentation Tracking

Default: enabled.

Responsibilities:

~~~text
- track fermentation lifecycle
- read gravity/temperature when available
- show batch/fermentation/cold-crash status
- provide handoff from brewday to fermentation
- avoid active chamber control unless chamber-control module is enabled
~~~

Capabilities:

~~~text
read_fermentation_status  read_only
read_gravity              read_only
read_liquid_temperature   read_only
mark_fermentation_started confirm
mark_cold_crash_started   confirm
mark_packaged             confirm
~~~

Important rule:

~~~text
Fermentation Tracking belongs in the base workflow.
Active chamber control does not.
~~~

### Carbonation Guidance

Default: enabled as guidance.

Responsibilities:

~~~text
- carbonation method selection
- target volumes
- start volumes
- temperature source
- recommended pressure calculation
- session status if enabled
~~~

Capabilities:

~~~text
calculate_pressure          guidance_only
track_carbonation_session   read_only
set_carbonation_inputs      direct
complete_carbonation        confirm
~~~

Important rule:

~~~text
Carbonation guidance should work without a kegerator.
Kegerator can improve the temperature source when available.
~~~

---

## Optional hardware/modules

### BrewZilla adapter

Default: disabled.

Type: hot-side hardware adapter.

Responsibilities:

~~~text
- normalize BrewZilla/RAPT telemetry
- expose wort/kettle/mash temperatures
- expose target temperature and power
- support heater/pump actions according to capability policy
- provide abort capability
- consume Brewday Runtime stage/target data
~~~

Capabilities:

~~~text
read_hot_side_temperature   read_only
read_hot_side_power         read_only
set_target_temperature      confirm
control_heater              confirm
control_pump                confirm
abort_hot_side              direct
~~~

Important rule:

~~~text
BrewZilla is the first hot-side adapter, not the BrewAssistant core.
~~~

### Grainfather adapter

Default: disabled.

Type: future hot-side hardware adapter.

Initial support should be read-only/supervised until the source integration and hardware behavior are understood.

Capabilities:

~~~text
read_hot_side_temperature   read_only
read_hot_side_power         read_only if available
set_target_temperature      disabled/read_only until validated
control_heater              disabled/read_only until validated
control_pump                disabled/read_only until validated
abort_hot_side              disabled until validated
~~~

### Kegerator / Serving

Default: disabled.

Responsibilities:

~~~text
- read serving/cold storage climate state
- infer compressor activity from power
- manage circulation fan-auto when enabled
- support serving/storage target context
~~~

Capabilities:

~~~text
read_serving_temperature    read_only
read_compressor_state       read_only
control_fan_auto            direct
set_serving_target          confirm
set_storage_target          confirm
~~~

Important rule:

~~~text
Kegerator fan-auto may be direct because it only controls the circulation fan.
Compressor/cooling target behavior remains owned by the HA climate/thermostat layer unless explicitly supported later.
~~~

### Fermentation Chamber Control

Default: disabled.

Responsibilities:

~~~text
- active chamber temperature management
- target/window calculation
- heat/cool recommendations
- optional target/mode apply through chamber adapter
~~~

Capabilities:

~~~text
read_chamber_temperature    read_only
read_liquid_temperature     read_only
calculate_chamber_target    guidance_only
set_chamber_target          read_only/confirm
set_chamber_mode            read_only/confirm
turn_chamber_off            confirm
~~~

Important rule:

~~~text
This module is separate from Fermentation Tracking.
A user may track fermentation without allowing BrewAssistant to control chamber behavior.
~~~

### BrewCreator / Fercubator adapter

Default: disabled.

Type: future fermentation chamber adapter.

Capabilities:

~~~text
read_chamber_temperature    read_only
read_chamber_target         read_only
read_chamber_mode           read_only
set_chamber_target          disabled/read_only until validated
set_chamber_mode            disabled/read_only until validated
turn_chamber_off            disabled/read_only until validated
~~~

Fercubator support is a later project and should start read-only.

### Counterflow Chiller

Default: disabled.

Capabilities:

~~~text
read_cooling_status        read_only
calculate_pitch_eta        guidance_only
mark_cfc_ready             confirm
control_pump_for_cfc       confirm
~~~

### Notifications

Default: disabled.

Capabilities:

~~~text
send_mobile_notification       direct when configured
send_persistent_notification   direct when configured
send_warning                   direct when configured
~~~

Important rule:

~~~text
Notifications should be module-aware and should not alert for disabled modules.
~~~

### Diagnostics

Default: basic enabled, advanced disabled.

Capabilities:

~~~text
read_source_health      read_only
read_registry_health    read_only
read_debug_context      read_only
~~~

Important rule:

~~~text
Diagnostics should be useful without becoming an anxiety dashboard.
Large cleanup backlogs should be summarized, not listed by default.
~~~

---

## UI visibility rules

Dashboards should follow module and capability state.

~~~text
Show Core/Source Health by default.
Show Brewday by default.
Show Fermentation Tracking by default.
Show Carbonation guidance by default if useful.
Show BrewZilla only when enabled or when BrewZilla telemetry exists.
Show Kegerator only when enabled or kegerator source entities exist.
Show Fermentation Chamber Control only when enabled.
Show advanced diagnostics only when explicitly enabled.
~~~

Special cases:

~~~text
BrewZilla disconnected + 0 W = idle/neutral, not error.
Brewfather unavailable/inactive = idle/neutral unless it is the selected active runtime source.
Fermentation chamber off = off, not necessarily problem.
Large legacy registry backlog = cleanup backlog, not runtime failure.
~~~

---

## First backend implementation target

The first implementation should be small.

Suggested first backend objects:

~~~text
ModuleManifest
CapabilityManifest
ModuleStatus
CapabilityStatus
SourceStatus
~~~

Suggested first sensors:

~~~text
sensor.brewassistant_module_summary
sensor.brewassistant_source_health
sensor.brewassistant_capability_summary
binary_sensor.brewassistant_module_brewzilla_available
binary_sensor.brewassistant_module_kegerator_available
binary_sensor.brewassistant_module_fermentation_chamber_available
~~~

Suggested first rule:

~~~text
A module can be:
- disabled
- enabled_missing_sources
- enabled_ready
- active
- blocked
~~~

This should be implemented before a full config/options flow.
