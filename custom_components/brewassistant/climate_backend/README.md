# Kegerator Climate Supervisor backend

Status: active  
Code snapshot documented: 2026-09-05

`climate_backend` currently contains the kegerator Climate Supervisor. It adjusts the target of `climate.kegerator_kylskap` while carbonation/serving supervision is enabled and in scope.

The supervisor owns **target selection**, not compressor switching. Normal hysteresis, compressor timing and refrigeration behavior remain the responsibility of the Home Assistant climate integration.

## Scope

The supervisor is active only when both are true:

```text
Climate Supervisor enabled
AND
carbonation/serving scope active
```

Carbonation scope is inferred from `sensor.brewassistant_carbonation_status` and its `active` attribute. Recognized active states include Carbonating, Conditioning and Ready to serve.

When enabled but carbonation is not active, the supervisor stays in standby.

## Inputs

Main inputs:

```text
configured kegerator air-temperature entity
climate.kegerator_kylskap
sensor.brewassistant_carbonation_status
sensor.brewassistant_carbonation_temperature
kegerator serving-temperature preset
```

The base target comes from the selected kegerator temperature preset, with 4.0 °C as the fallback.

## Dynamic target logic

The current controller nudges the climate target around the base target according to kegerator air-temperature delta:

| Air delta from base | Target adjustment |
| --- | ---: |
| >= +2.0 °C | -0.6 °C |
| >= +1.0 °C | -0.4 °C |
| >= +0.5 °C | -0.2 °C |
| <= -0.7 °C | +0.4 °C |
| <= -0.3 °C | +0.2 °C |
| otherwise | base target |

The resulting target is clamped to 1.0–12.0 °C.

Evaluation/apply cadence is currently 30 seconds, with a 0.05 °C target-change epsilon.

## Control behavior

When an adjustment is required, `async_apply_climate_supervisor()` can directly call Home Assistant climate services:

```text
climate.set_hvac_mode -> cool      (if controller is off)
climate.set_temperature            (effective target)
```

If the legacy `switch.brewassistant_kegerator_guard_enabled` is active, the Climate Supervisor turns it off before applying its own climate-target strategy.

This backend does **not** currently use the generic `supervised_apply.py` pending-confirmation flow. That is an intentional difference from the fermentation chamber supervisor and must be visible in UI/architecture discussions.

## Runtime state

Supervisor runtime/diagnostic state is stored in `hass.data["brewassistant"]`, including:

- enabled runtime flag;
- captured/base target;
- last action;
- last evaluation timestamp.

There is no Home Assistant `Store` persistence in `climate_supervisor.py` today.

## Snapshot output

The supervisor exposes/uses fields such as:

```text
enabled
mode
status
action
control_action
reason
base_target_temperature
effective_air_target
air_temperature
air_delta
cooling_demand
controller_state
controller_target_temperature
target_delta
carbonation_active
last_control_action
last_evaluation
```

## Relationship to `kegerator/`

These are separate responsibilities:

```text
climate_backend/climate_supervisor.py
  selects/applies kegerator climate target

kegerator/fan_control.py
  controls only the circulation fan

kegerator/guard.py
  separate legacy/policy-mediated physical switch guard + restart watchdog

Home Assistant climate integration
  normal compressor regulation
```

Do not merge these responsibilities simply because they all observe kegerator temperature.

## Do not change casually

1. The Climate Supervisor controls the climate target, not compressor duty directly.
2. Keep the direct-apply behavior explicit; do not describe it as Supervised Apply unless implementation changes.
3. Avoid running the legacy kegerator guard as a competing controller while the Climate Supervisor owns the strategy.
4. Target clamping and source-unavailable behavior are safety/operability boundaries, not merely UI details.
