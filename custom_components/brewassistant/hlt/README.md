# HLT SIM-1 — BrewZilla always has absolute power priority

Status: **simulation connected to BA startup through an independent 30-second timer; physical control NOT implemented**. PR targets `dev`, then `beta`, then `main` after verification.

## Operating contract

- **Never throttle or cap BrewZilla for HLT.** BZ may always use the power required for the brew.
- HLT is secondary. The virtual HLT may heat while BZ is *observed* cruising at its current target, physical/normalized targets agree, readings are fresh, and observed BZ W + full HLT heater W fit within the configured scenario budget.
- A next target/ramp, departure from target, unavailable BZ data, or insufficient observed capacity revokes the virtual HLT opportunity at the next simulation tick. Its reservation is held through a **virtual** OFF delay and then released. BZ is never capped during this delay; an observed overlap is reported as `simulation_budget_conflict`, not hidden by clipping BZ consumption. Missing target or temperature means *unknown*, not an invented ramp.
- HLT remains off for No Sparge and once its own target is reached.
- A low instantaneous BZ wattage reading alone is NOT proof that its heater cannot turn on again. This model has no physical grant authority and `power_budget_verified` is **always false**. The old `brewzilla_would_grant_w`/`brewzilla_would_cap_utilization` compatibility result properties return `None` and must never be used for actuation. The legacy `brewzilla_unconstrained` input is not a control permission.

**Physical interlock requirement:** BZ's own thermostat/RAPT control can re-energize between HA's 30-second samples. A software-only watchdog or virtual OFF timer cannot guarantee the circuit budget. Before real HLT switching, implement fail-off HLT hardware/load-shed behavior independent of polling and verify HLT actual OFF via wattmeter or trusted feedback; coordinate planned ramps by shutting HLT down ahead of ramp, without limiting BZ. Verify actual circuit/wiring, measured wattage and protection before commissioning. `2500 W` is only a default simulation scenario, NOT a verified safe load.

## Inputs and temperature

Default BZ inputs: `sensor.brewzilla_power`, `number.brewzilla_heat_utilization` (observed diagnostic only), `sensor.brewzilla_temperature`, `number.brewzilla_target_temperature` and normalized Brewday `target_temperature`. The latter three must agree within 0.5°C for a cruising observation; missing/stale data blocks the opportunity. Brewday volume comes from normalized batch context (`sparge_water_l`); unknown volume means no simulation, zero volume means No Sparge.

Provisional HLT inputs are configurable: `switch.sparge_heater`, `sensor.sparge_heater_power`, optional HLT temperature entity. Fresh HLT temperature takes precedence; otherwise simulated temperature integrates `heater_w * efficiency - heat_loss` against water volume. A thermostat heating→OFF observation can calibrate only against a separately configured known cutoff temperature. Manual switch OFF is not thermostat cutoff. Temperature must be labelled measured or estimated. Thermal model is approximate and does not model stratification/boiling comprehensively.

## File logging and Flight Recorder

While Brewday Audit is active, `async_setup_hlt_simulation()` runs a separate simulation-only timer every 30s and calls `async_record_hlt_tick()`. There are **no `hass.services` hardware writes or BZ caps in the HLT package**. An uploadable JSONL file is created per session under `/config/brewassistant/logs/hlt-sim-<session-hash>.jsonl` in standard HA installations. A normal sample is limited to one per 30 seconds, with immediate state/virtual-switch/conflict records; each row says `simulation: true`, `physical_writes: false` and separates observed BZ power from virtual HLT power and measured from estimated HLT temperature. Significant transitions are also added to the existing `sensor.brewassistant_brewday_event_log_summary` event list, without flooding its 250-event retention limit. Export the JSONL file through File Editor, Samba or SSH and upload it for analysis.

## Remaining before merge

- Verify all simulation/runner/trace tests and full repository CI; no passing CI has been established for the latest code yet.
- Expose clear diagnostic entities / current trace path in HA UI (currently stored in `hass.data['brewassistant']['hlt_trace_path']`).
- Check actual Brewday target and batch-volume sources against real BA/RAPT/Brewfather sessions; test stale/missing readbacks, target transitions, real thermostat cycling and session rotation.
- Keep this PR draft. It adds **no physical HLT operation**. Any future hardware stage requires independent interlock, physical OFF confirmation and supervised validation.
