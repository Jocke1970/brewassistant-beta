# HLT backend — SIM-1 core

Status: **simulation engine implemented; HA runtime registration and physical control NOT implemented**.

This package contains a pure-Python state machine (`simulation.py`) and a read-only HA input adapter (`ha_adapter.py`). Both support replay of BrewZilla measurements, requested utilization and a virtual HLT. No module calls `hass.services` or writes a physical entity.

## Inputs

- `sensor.brewzilla_power` measured power (default; must be checked against actual available entity; the current BZ backend has previously treated it as unverified).
- `number.brewzilla_heat_utilization` *requested or actual?* The HA adapter currently reads it as a proxy; this MUST be replaced by BA-owned desired demand before any physical sharing.
- `switch.sparge_heater`, `sensor.sparge_heater_power` (provisional IDs; configurable in `EntityConfig`).
- Optional HLT temperature entity (configurable). Fresh readings reset the model; absent readings use energy integration.
- Sparge required flag must come from normalized Brewday intent; caller provides it explicitly.

## Thermal model

`temperature += (heater_w * efficiency - heat_loss_w) * dt / (volume_l * 4186)`.

The model starts from a configured known/assumed water temperature. The adapter detects thermostat transitions only if switch is ON and power shows heat followed by no heat; a thermostat cutoff temperature MUST be independently configured before that edge can calibrate the temperature estimate. Switch OFF is not proof of thermostat cutoff. Never label an inferred value as a measured temperature; hardware stratification and hysteresis are not represented.

The virtual HLT switch is independent of the real `switch.sparge_heater`: simulated ON/OFF events never reach it.

## Power safety contract

Usable watts = configured circuit limit minus separately commissioned margin. Current default **2500 W is only a simulation scenario**, not a verified fuse rating. Set per installation. Binary HLT reserves all configured heater watts. BZ demand uses desired utilization times calibrated rated heater power plus idle power and is raised to the measured power if higher. Missing/stale BZ requested utilization or power prevents new virtual HLT grants.

`brewzilla_unconstrained=True` is the default and reserves BZ full maximum, rather than assuming live consumption represents unused guaranteed capacity. Set false ONLY for hypothetical arbitration/replay or after real BA-owned BZ cap enforcement is implemented. It does not enable control, and `power_budget_verified` remains false in unconstrained mode.

Reclaim: virtual HLT OFF request -> virtual release timer -> BZ `would_grant` can rise. Actual physical OFF needs verified readback and must never reuse this simulated timer as sufficient safety evidence.

## Important limitations / next slice

- Not wired into coordinator, HA entities, config flow, dashboard or Flight Recorder yet. Nothing runs automatically in HA after installing this commit.
- `simulation.py` retains state only in memory; no lease survives instance recreation.
- No actual BZ heat cap; all allocations are `would_grant`/`would_cap` values.
- HA adapter `thermostat_heating` describes the real switch and wattmeter for replay/calibration; it is NOT used as a physical actuator feedback grant.
- If BZ becomes unknown while a simulated HLT grant is still releasing, the engine reports `simulation_budget_conflict`; real control must resolve unknown demand and OFF confirmation before any positive action.
- A real thermostat setpoint is not known from power alone; require configured cutoff or a separately known measured calibration point.
- Real hardware requires water-level/dry-fire and independent over-temperature protection, verified breaker/circuit and measured ratings, actuation ownership, stale HA signal policy, plus full integration tests.

Promotion: feature branch -> `dev` -> `beta` -> `main`, after tests and hardware commissioning; do not bypass phases by merging this standalone core directly into main.
