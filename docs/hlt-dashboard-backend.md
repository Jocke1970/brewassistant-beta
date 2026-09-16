# HLT dashboard backend contract (SIM-1)

Status: **read-only, simulator-driven telemetry; not a physical HLT controller**. This document specifies the future Swedish/English dashboard's inputs, not a Lovelace implementation.

## Power priorities and observation

BrewZilla has absolute priority. BA never reduces BrewZilla's heater utilization to make room for HLT. The simulation models HLT borrowing observed headroom only after fresh target/temperature/cruise evidence. A later ramp or loss of evidence yields the *virtual* heater. A 30-second sample cannot prevent BrewZilla's autonomous thermostat from switching between samples; the configured 2500 W scenario is NOT a commissioned circuit rating or a real electrical interlock.

All new entities are `sensor.brewassistant_<key>`; suggested IDs are provided, but HA's entity registry may suffix names. The preferred primary entities for UI are:

| Entity | Meaning |
| --- | --- |
| `sensor.brewassistant_hlt_status` | `IDLE`, `WAITING_FOR_POWER`, `HEATING`, `YIELDING`, `READY`, or runtime diagnostic status. Attributes include simulation-only flag, readback, timing quality and BZ cruise/ramp observation. |
| `sensor.brewassistant_hlt_reason` | Reason for last simulated decision. |
| `sensor.brewassistant_hlt_power_priority` | Always `brewzilla`. This is the fixed priority policy, **not** a metered recipient. |
| `sensor.brewassistant_hlt_power_owner` | `brewzilla_only` / `brewzilla_with_virtual_hlt`; simulated opportunity status, **not** physical actuation ownership. |
| `sensor.brewassistant_hlt_actual_energy_recipient` | From *both* fresh BZ and HLT wattmeters: `brewzilla`, `hlt`, `brewzilla_and_hlt`, `neither`, or `unknown`. Unknown ≠ zero. |
| `sensor.brewassistant_hlt_virtual_energy_recipient` | Virtual HLT is on/off only; this is NOT actual delivery. |
| `sensor.brewassistant_hlt_brewzilla_power_observed` | Fresh observed BrewZilla watts. |
| `sensor.brewassistant_hlt_power_observed` | Fresh observed HLT watts; unavailable if no HLT power meter. |
| `sensor.brewassistant_hlt_power_virtual` | Hypothetical active HLT watts; returns 0 while yielding, even when a virtual reservation is still pending. |
| `sensor.brewassistant_hlt_total_power_observed` | Sum of BOTH real wattmeters; unavailable if either is missing. |
| `sensor.brewassistant_hlt_total_power_virtual_scenario` | Observed BZ plus simulated HLT; not actual load. |
| `sensor.brewassistant_hlt_budget_scenario` | Configured simulation budget in W, not a verified circuit limit. |
| `sensor.brewassistant_hlt_headroom_observed` | Scenario budget minus both actual readings; may be negative; unavailable if either meter is unknown. Not an authorization to switch hardware. |

## HLT temperature

| Entity | Meaning |
| --- | --- |
| `sensor.brewassistant_hlt_temperature` | Currently selected HLT model value (can use a fresh real sensor reading). Always pair with source. |
| `sensor.brewassistant_hlt_temperature_measured` | Real HLT temperature only when a fresh HLT thermometer is available. |
| `sensor.brewassistant_hlt_temperature_estimated` | Thermal-model estimate or thermostat-calibrated estimate, **not a measurement**. |
| `sensor.brewassistant_hlt_temperature_source` | `measured`, `estimated`, or `thermostat_calibrated_estimate`. |
| `sensor.brewassistant_hlt_target_temperature` | Simulation scenario target. |
| `sensor.brewassistant_hlt_volume` | Normalized sparge volume; 0 means explicit no-sparge. |

No temperature probe? The model uses estimated heating energy and the assumed starting temperature. Thermostat calibration needs a separately known cutoff temperature; OFF on a power switch alone is not evidence of thermostat cutoff.

## Session time and energy (all estimates except the wall-clock interval)

| Entity | Meaning |
| --- | --- |
| `sensor.brewassistant_hlt_total_session_seconds` | Wall-clock seconds since first active HLT request; freezes on first disabled stage. Includes waiting and yielding. |
| `sensor.brewassistant_hlt_virtual_heating_seconds` | Simulated HLT on-time, integrated from the previous virtual state in samples up to 90 seconds apart. |
| `sensor.brewassistant_hlt_observed_heating_estimate_seconds` | Time estimated only when HLT power >=20 W **and** switch is ON at both ends of an interval; unavailable until evidence spans an interval. |
| `sensor.brewassistant_hlt_waiting_seconds` | Time in simulated `WAITING_FOR_POWER`. |
| `sensor.brewassistant_hlt_yielding_seconds` | Time in simulated `YIELDING`. |
| `sensor.brewassistant_hlt_unknown_sample_seconds` | Gaps over 90 s, excluded from heat-time/Wh accumulation. |
| `sensor.brewassistant_hlt_brewzilla_energy_estimate_wh` | Trapezoidal estimate from two consecutive observed BZ power readings; unavailable before first valid interval. |
| `sensor.brewassistant_hlt_energy_estimate_wh` | Analogous estimate from observed HLT wattmeter, **not** simulation and not a certified energy meter. |
| `sensor.brewassistant_hlt_yield_count` / `sensor.brewassistant_hlt_reclaim_count` | Virtual off requests / BZ-priority reclaims. |
| `sensor.brewassistant_hlt_timing_quality` | `sample_estimate_not_metered`. |
| `sensor.brewassistant_hlt_trace_path` | Absolute path to the current JSONL file for uploading. |

All counters live in memory and reset after HA/integration restart, even if Brewday Audit resumes the same session. The JSONL trace itself remains on disk. Restoring counters from trace history is a separate follow-up; do not claim uninterrupted post-restart totals.

## Lifecycle and sources

The HLT runtime is already registered as a separate simulation-only 30-second HA timer and the sensors use BA's normal 30-second coordinator refresh. The UI may therefore lag a simulation sample. Actual HLT switch/power and optional thermometer entity IDs are *provisional defaults* (`switch.sparge_heater`, `sensor.sparge_heater_power`); confirm/make them configurable in a public options flow before field installation. `sensor.brewzilla_power` must likewise be verified against installed hardware.

A JSONL file under `/config/brewassistant/logs/hlt-sim-<hash>.jsonl` is written only while Brewday Audit is active and a non-negative normalized sparge volume is known. Each routine row is at most once per 30 seconds, with extra transition rows. The separate Brewday Event Log receives state/priority changes rather than every sample. No HLT dashboard card has been added yet.

Do not merge as a real power-sharing controller. Physical mode needs independently commissioned circuit/ratings, fast fail-off load shedding, physical HLT OFF readback, dry-fire protection, manual overrides and validated supervised execution; none are provided by these telemetry sensors.
