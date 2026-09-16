# HLT backend — SIM-1 core

Status: **simulation and JSONL writer implemented; HA runtime registration and physical control NOT implemented**.

This package contains a pure-Python state machine (`simulation.py`), HA input adapter (`ha_adapter.py`) and uploadable JSONL file writer (`trace.py`). None writes physical heater or BrewZilla entities. The writer must be called by the future integrated simulation runtime; installing this PR alone does not start logging.

## Inputs

- `sensor.brewzilla_power` measured power (default; confirm the actual live entity before use).
- `number.brewzilla_heat_utilization` is observed as a proxy, NOT yet an authoritative BA-owned requested-power channel.
- `switch.sparge_heater`, `sensor.sparge_heater_power` are provisional and configurable in `EntityConfig`.
- Optional fresh HLT temperature sensor. When absent, the model integrates energy and labels its temperature *estimated*.
- The caller supplies normalized Brewday sparge-required intent explicitly. Never assume sparge is required when the value is unknown.

## Thermal model

`temperature += (heater_w * efficiency - heat_loss_w) * dt / (volume_l * 4186)`.

The model starts from a configured/assumed temperature. The HA adapter detects thermostat transitions only while the physical switch remains ON and power transitions from heating to low draw. Calibration requires a separately configured thermostat cutoff temperature. Switch OFF alone is not thermostat cutoff. The model does not represent stratification, boiling or hardware hysteresis completely.

The virtual HLT switch is independent of the real heater: simulated ON/OFF events never reach it.

## Power contract

Usable watts = commissioned circuit limit minus margin. Default **2500 W is a simulation scenario**, not a verified installation limit. The binary HLT reserves its full rated watts. BZ demand is estimated from desired utilization and configured rated heater power plus idle, then raised when observed draw is higher. Missing/stale BZ signals prevent new HLT grants.

`brewzilla_unconstrained=True` defaults to reserving BZ full maximum. Setting false is only hypothetical replay until BZ's physical write chain enforces an actual power cap. `power_budget_verified` is false in unconstrained mode. Virtual release delay is NEVER evidence that real hardware is off.

## Uploadable HLT trace file

`trace.py` provides `async_record_hlt_trace(hass, session_id, inputs, result, ...)`. When the future runtime calls it, it appends a JSON object per line (JSONL), using HA's executor to avoid blocking the event loop. Each brewday session receives a separate filename based on a stable hash of its session ID; no recipe name or arbitrary user string is placed into the path.

Location (in a conventional Home Assistant installation):

```text
/config/brewassistant/logs/hlt-sim-<session-hash>.jsonl
```

Sample rate is at most one routine row per 30 seconds, with extra immediate rows for state changes, virtual ON/OFF, reclaim, thermostat calibration and budget-conflict events. Rows record timestamp, Brewday stage/step (when provided), observed BrewZilla power, observed HLT power/switch/temp (when available), model temperature and source, thermostat status, simulated reservations, proposed BZ cap, configured watt budget and full transition event names. Explicit `simulation=true` and `physical_writes=false` flags prevent replay from masquerading as a physical field test.

The JSONL file is independent of `sensor.brewassistant_brewday_event_log_summary` and its 250-event retention limit. The upload workflow is to copy the corresponding JSONL file from Home Assistant using File editor / Samba / SSH and upload it to the chat; no user tokens or private Home Assistant configuration are included by this writer.

**Current integration boundary:** The trace writer is tested as a standalone module but is NOT YET CALLED from coordinator or an HLT runtime. Therefore there will be **no HLT log file merely from installing PR #212**. The next code change must register an HLT simulation runner, derive a real Brewday session ID, call the writer after each simulator tick, expose its actual file path, and add significant HLT events to Brewday Audit without copying every 30-second sample into the HA entity attributes.

## Testing

`tests/test_hlt_simulation.py` contains simulator contract cases. `tests/test_hlt_trace.py` checks JSONL output, immediate transitions, 30-second sampling, separate sessions/path safety, and rejected invalid timestamps. Both must run in repository CI along with subsequent coordinator/audit integration tests before promotion.

## Promotion and commissioning

Feature branch → `dev` → `beta` → `main`. This draft PR is an incomplete SIM-1 foundation. No physical grants, BZ utilization caps, HLT ON commands or real-world circuit protection are implemented. Physical deployment requires hardware readback/independent protections, installation-specific ratings and supervised field validation.
