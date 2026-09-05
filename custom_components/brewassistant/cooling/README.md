# Cooling backend

Status: Cooling Runtime v2 partially implemented / active development  
Code snapshot documented: 2026-09-05

`cooling` owns BrewAssistant's post-boil wort-cooling runtime and advice model. It is cooling-centric rather than CFC-centric and supports counterflow, immersion and fully manual cooling paths.

The current code implements method-aware runtime state, temperature-source resolution, target handling, sanitation-state detection and cooling advice/trend/ETA. Automatic cooling-water actuation is **not active yet**.

## Supported methods

```text
Counterflow chiller
Immersion chiller
Manual cooling
```

Defaults:

```text
method: Counterflow chiller
target: 18 °C
manual temperature: 20 °C
sanitation window: 15 min
ready tolerance: ±1 °C
```

Cooling target is constrained to 8–30 °C in whole-degree steps by the runtime settings update path. Sanitation time is constrained to 10–25 minutes.

## Ownership boundary

Cooling owns:

- cooling method and runtime state;
- cooling target;
- method-aware process-temperature interpretation;
- CFC/immersion sanitation context;
- cooling delta, trend, rate, ETA and target readiness;
- post-BOIL interpretation of the shared external process sensor.

Cooling does **not** own:

- BrewZilla heater control;
- BrewZilla target temperature for mash/boil;
- BrewZilla wort-pump start/stop;
- BrewZilla pump utilization;
- Brewday stage progression.

The BrewZilla wort pump is explicitly operator-owned during Cooling.

## External process-sensor handoff

Fixed cross-backend contract:

```text
Hot side owns external process probe through Pre-boil
BOIL starts -> hot side releases the probe
Cooling owns/interprets it through Chill/Transfer
```

For counterflow cooling the probe is the CFC outlet/wort-out process temperature. BrewZilla internal temperature must not silently substitute for it.

Current CFC sensor candidates include:

```text
sensor.rapt_ble_thermometer_temperature
sensor.rapt_ble_thermometer_temp
sensor.counterflow_output_temperature
sensor.wort_output_temperature
```

## Method-aware temperature resolution

### Counterflow chiller

```text
process temperature = configured/known CFC outlet sensor candidate
```

If no outlet temperature is available, the runtime keeps the process temperature unavailable and advice can report `no_outlet_temperature`.

### Immersion chiller

```text
process temperature = BrewZilla internal wort temperature
fallback = BrewAssistant manual cooling-temperature input
```

### Manual cooling

```text
process temperature = manual cooling-temperature input
```

## Runtime states currently produced

`cooling_runtime.py` maps Brewday stage context into:

```text
IDLE
PREPARE
SANITIZE
CHILLING
TRANSFER
COMPLETE
```

A `READY` state exists in the earlier architecture/roadmap vocabulary and `cooling_advice.py` can describe it, but the current runtime mapper does not yet emit `READY`. Do not document READY as implemented lifecycle behavior until that transition exists in code.

For CFC/immersion, BOIL enters PREPARE and enters SANITIZE when remaining boil time is within the configured sanitation window.

## Sanitation

Both CFC and immersion workflows require sanitation context.

### CFC

During SANITIZE the backend can require operator wort circulation and explicitly advises that cooling water remain off. It reads the BrewZilla pump state but does not write it.

### Immersion

The same sanitation window applies, but no wort-pump requirement is introduced by Cooling.

The current runtime infers SANITIZE from boil stage + remaining time. It does not yet persist a complete elapsed sanitation lifecycle proving the full minimum time was achieved.

## Cooling advice and trend

`cooling_advice.py` keeps in-memory temperature samples and calculates:

- process-temperature delta to target;
- positive cooling rate in °C/h;
- ETA when cooling is meaningfully progressing;
- target readiness within ±1 °C;
- operator-facing status/advice.

Trend behavior currently uses:

```text
minimum sample spacing: 60 s
maximum pair interval: 7200 s
minimum meaningful cooling rate: 0.2 °C/h
```

Typical statuses include:

```text
standby
prepare
sanitizing
wort_pump_required
no_outlet_temperature
no_process_temperature
no_target
cooling_needed
cooling
approaching_target
on_target
below_target
transfer_ready
```

`pitch_ready` is currently a compatibility alias for `target_ready`.

## CFC compatibility adapter

`counterflow_chiller.py` remains for existing CFC switch/number/button entities while Cooling Runtime v2 owns the lifecycle.

Important compatibility behavior:

- legacy pump-utilization setting is retained as readback/config compatibility only;
- no BrewZilla pump utilization is written;
- `async_counterflow_chiller_ready()` marks advisory readiness only and performs no pump action;
- sanitation-minutes changes are synchronized into Cooling Runtime v2 settings.

## Current persistence

Cooling Runtime v2 settings and trend state currently live in `hass.data` only. They are not persisted through Home Assistant Storage by `cooling_runtime.py`/`cooling_advice.py`.

This means Home Assistant restart persistence should not be assumed for method/target/manual-temperature/samples unless another entity/config layer restores them.

## Sensor surface

Canonical Cooling v2 sensors include:

```text
sensor.brewassistant_cooling_state
sensor.brewassistant_cooling_method
sensor.brewassistant_cooling_status
sensor.brewassistant_cooling_advice
sensor.brewassistant_cooling_summary
sensor.brewassistant_cooling_process_temperature
sensor.brewassistant_cooling_target_temperature
sensor.brewassistant_cooling_delta
sensor.brewassistant_cooling_rate
sensor.brewassistant_cooling_eta_minutes
sensor.brewassistant_cooling_target_ready
sensor.brewassistant_cooling_process_temperature_source
```

`wort_cooling_sensor.py` also keeps legacy `brewassistant_wort_*` sensor IDs so dashboards/automations can migrate without a flag day.

## Known implementation gaps

Compared with the full Cooling v2 architecture, the current code still lacks or only partially implements:

- automatic cooling-water switch control;
- persisted Cooling runtime/session state;
- a complete sanitation elapsed/completed contract;
- an emitted READY lifecycle state;
- explicit completion/reset ownership release beyond stage-derived runtime behavior;
- configurable arbitrary CFC outlet entity selection beyond the current candidates/config surface.

## Do not change casually

1. Cooling must never start/stop/regulate the BrewZilla wort pump.
2. CFC outlet temperature and kettle/internal temperature are not interchangeable.
3. Immersion cooling legitimately uses kettle temperature; CFC cooling does not.
4. Cooling target is independent of BrewZilla hot-side target.
5. Both CFC and immersion sanitation belong in the Cooling lifecycle.
6. Manual cooling must remain a first-class path.
7. Clearly distinguish implemented behavior from roadmap behavior.
