# HLT dashboard/backend contract (SIM-1)

**Status 2026-09-19:** [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212) is merged to the shared `dev` branch. The backend, 31 read-only HA telemetry keys, and standalone EN/SV Lovelace card examples exist. **Simulation only: no physical HLT switching, no BrewZilla throttling, no release to `beta` or `main`.** The 2026-09-19 test covered an earlier installed build; later step-policy fixes still need HA field validation. See the [dated field-test / Brewday handoff](hlt-sim1-field-validation-2026-09-19.md) and [operator-card guide](hlt-dashboard-card.md).

## Power priority, inputs and decisions

BrewZilla has absolute priority and is **never capped for HLT**. An HLT virtual opportunity requires a positive normalized sparge volume, eligible preparation stage, known BZ heat utilization, fresh BZ watts and internal temperature, agreement between device/runtime targets, observed cruise at target, absence of an explicit ramp step, and enough *scenario* headroom for the whole HLT heater. A low momentary BZ wattage alone is not permission. A ramp, loss of evidence or increased BZ load yields the virtual HLT at the next sample. Reservations may remain during a **virtual** OFF delay; any scenario overlap must be reported rather than concealing it by clipping measured BZ watts.

- Eligible stages are currently explicitly enumerated: `Setup`, `Heat strike`, `Heat strike water`, `Mash`, `Mash in`, `Mash out`, `Sparge`. An unknown/new/terminal stage fails closed. Step text indicating a ramp, including `Ramp to 72°C`, vetoes cruise. This is not yet a verified, source-independent sparge-intent contract for all Brewfather/Manual/RAPT step names.
- Stable Home Assistant numeric *settings* (`number.brewzilla_target_temperature`, `number.brewzilla_heat_utilization`) must not be rejected merely because their values are unchanged longer than 180 seconds. Unknown/unavailable settings fail closed. Physical watts/temperature **do** require fresh samples; the target comparison tolerance is 0.5 °C.
- `sensor.brewzilla_power` is the verified field-test wattmeter candidate: with BZ connected, physical heating followed about 2,323–2,356 W. Earlier approximately 15.8 W belonged to the beer fridge on that outlet, not a BZ idle reading. Recheck identity if the wiring changes.
- `sparge_water_l` comes from normalized BrewZilla Batch Context; it is separate from mash/strike water. `0` means No Sparge and should leave HLT idle; an unknown/negative volume cannot start simulation.
- `2500 W` is a **scenario default**, not a commissioned circuit rating; `power_budget_verified` stays `false`. No HLT sensor, card or JSONL field authorizes physical power allocation. HA's 30-second sampling cannot ensure electrical load shedding.

All integrated HLT sensor names use the suggested pattern `sensor.brewassistant_<key>`; HA's entity registry may append suffixes. Primary UI signals:

| Entity | Meaning |
| --- | --- |
| `sensor.brewassistant_hlt_status` | `IDLE`, `WAITING_FOR_POWER`, `HEATING`, `YIELDING`, `READY`, or runtime diagnostics. Attributes include simulation-only, readback/timing quality and observed BZ cruise/ramp. |
| `sensor.brewassistant_hlt_reason` | Last simulated decision reason, e.g. ramp/not cruising vs missing data. |
| `sensor.brewassistant_hlt_power_priority` | Fixed policy `brewzilla`; not a measured recipient. |
| `sensor.brewassistant_hlt_power_owner` | `brewzilla_only` / `brewzilla_with_virtual_hlt`; hypothetical opportunity, never physical authority. |
| `sensor.brewassistant_hlt_actual_energy_recipient` | Requires fresh BZ and physical HLT wattmeters: `brewzilla`, `hlt`, `brewzilla_and_hlt`, `neither`, `unknown`. Unknown ≠ zero. |
| `sensor.brewassistant_hlt_virtual_energy_recipient` | Virtual allocation category. `none` must display `Ingen` / `None`, **not** `Okänt` / `Unknown`. |
| `sensor.brewassistant_hlt_brewzilla_power_observed` | Fresh measured BZ W. |
| `sensor.brewassistant_hlt_power_observed` | Fresh measured physical HLT W; unknown if no meter. |
| `sensor.brewassistant_hlt_power_virtual` | Active virtual HLT watts; 0 while yielding even if virtual reservation is pending. |
| `sensor.brewassistant_hlt_total_power_observed` | Sum of BOTH physical meters; unknown if either meter missing. |
| `sensor.brewassistant_hlt_total_power_virtual_scenario` | Observed BZ W + hypothetical HLT load/reservation, not a measured circuit total. |
| `sensor.brewassistant_hlt_budget_scenario` | Simulation W only; **not** approved circuit capacity. |
| `sensor.brewassistant_hlt_headroom_observed` | Scenario budget minus both actual readings, possibly negative; unknown if a meter is absent. Not permission to energize HLT. |

## HLT temperature and provenance

| Entity | Meaning |
| --- | --- |
| `sensor.brewassistant_hlt_temperature` | Selected measured/estimated HLT temperature. Always pair with source. |
| `sensor.brewassistant_hlt_temperature_measured` | Real probe only if fresh physical HLT thermometer exists. |
| `sensor.brewassistant_hlt_temperature_estimated` | Thermal-model or thermostat-calibrated **estimate**; not a measurement. |
| `sensor.brewassistant_hlt_temperature_source` | `measured`, `estimated`, `thermostat_calibrated_estimate`. |
| `sensor.brewassistant_hlt_target_temperature` | Scenario target (default 78 °C). |
| `sensor.brewassistant_hlt_volume` | Effective normalized sparge water in L, not water already in BZ. |

Without a temperature probe, the model integrates virtual heating energy and losses from a configured starting temperature. Thermostat calibration requires a separately known cutoff temperature and evidenced heating→OFF transition; a manual OFF command is not evidence of thermostat cutoff. The approximation does not model real stratification, heater immersion or boiling comprehensively.

## Time and estimated energy

| Entity | Meaning |
| --- | --- |
| `sensor.brewassistant_hlt_total_session_seconds` | Wall time from first active HLT request, including waiting/yielding; freezes on first disabled stage. |
| `sensor.brewassistant_hlt_virtual_heating_seconds` | Integrated *simulated* ON-time from sampled virtual states up to 90 s apart. |
| `sensor.brewassistant_hlt_observed_heating_estimate_seconds` | Physical heating time estimate only if actual HLT W >=20 **and** switch ON at both interval endpoints. Unknown without evidence. |
| `sensor.brewassistant_hlt_waiting_seconds` | Time waiting for a hypothetical BZ-priority grant. |
| `sensor.brewassistant_hlt_yielding_seconds` | Time yielding hypothetical HLT allocation. |
| `sensor.brewassistant_hlt_unknown_sample_seconds` | Gaps >90 s excluded from heating time and Wh. |
| `sensor.brewassistant_hlt_brewzilla_energy_estimate_wh` | Approximate trapezoidal integration of two BZ watt samples. |
| `sensor.brewassistant_hlt_energy_estimate_wh` | Approximate integration from physical HLT meter, not virtual W. |
| `sensor.brewassistant_hlt_yield_count` / `sensor.brewassistant_hlt_reclaim_count` | Virtual off requests / BZ-priority reclaims. |
| `sensor.brewassistant_hlt_timing_quality` | `sample_estimate_not_metered`. |
| `sensor.brewassistant_hlt_trace_path` | Server-side absolute path to current JSONL flight recorder. |

All timer/Wh counters are currently memory-only and reset at HA/integration restart, even if Audit resumes the same session. JSONL history remains on disk; recovery of timers from trace is not implemented.

## Lifecycle, logging and UI

HLT uses a separate unloadable simulation-only timer every **30 s** registered with BA startup; HA sensor presentation uses BA's ordinary coordinator refresh and may lag a tick. Provisional physical HLT entity defaults (`switch.sparge_heater`, `sensor.sparge_heater_power`, optional temperature entity) require verification/configuration before hardware commissioning. No actual HLT wattmeter or switch was available in the first field test, so physical consumption and OFF readback must remain unknown, not 0/confirmed.

A JSONL log under `/config/brewassistant/logs/hlt-sim-<session-hash>.jsonl` is written while Brewday Audit is active and normalized sparge volume is known. Routine rows are limited to 30 s, plus meaningful transition/conflict rows. Rows separate observed BZ power from virtual HLT power and estimated from measured temperature; Flight Recorder/Audit gets meaningful transitions rather than every tick. The file path is exposed by `sensor.brewassistant_hlt_trace_path`; it is not a download URL.

Standalone high-contrast read-only cards **already exist** in `dashboard/cards/hlt_power_dashboard.yaml` and `dashboard/cards/hlt_power_dashboard_sv.yaml`; they are manual examples and not automatically installed. They do not have actuator or confirmation controls. Installing Python changes requires a controlled HA restart; changing only the YAML card does not. The previously pinned feature snapshot `977136c5` must not overwrite an updated parallel `dev` integration.

## Validation and hardware gate

PR #212 passed CI, HACS validation and Hassfest before merge; the combined `dev` merge `746633c` passed them too. The 2026-09-19 installed test verified BZ wattmeter correlation, positive sparge volume propagation, conservative waiting and JSONL diagnostics, **not** the post-test target/ramp/stage fixes in installed HA. The trace also captured transient virtual overlap and a false virtual grant on `Ramp to 72°C`; see [dated evidence](hlt-sim1-field-validation-2026-09-19.md). Retest ramp step names, live readbacks, stage transitions, virtual cruise→yield, temperature/ETA, restart and logs before any promotion.

Before physical HLT power sharing: independent fast fail-OFF load shedding/interlock, verified real HLT OFF feedback, confirmed circuit ratings/installation, dry-fire protection, explicit supervised commissioning and manual override. None is provided by SIM-1, and BrewZilla must **never** be limited to grant HLT capacity.
