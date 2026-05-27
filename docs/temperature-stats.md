# Temperature Stats

Temperature Stats provides Python-owned rolling temperature context for BrewAssistant dashboards and future supervisor logic.

The module is intentionally lightweight and read-only. It keeps rolling samples in Home Assistant memory and exposes dashboard-safe sensors.

---

## Purpose

Temperature Stats exists to separate noisy instant temperatures from slower process context.

```text
instant temperature
→ useful for quick UI feedback

rolling average / trend
→ useful for dashboard interpretation and future target damping
```

The first version is designed for UI and diagnostics. It does not directly control hardware.

---

## Current sensors

```text
sensor.brewassistant_kegerator_air_temperature_average
sensor.brewassistant_fermentation_chamber_air_temperature_average
sensor.brewassistant_fermentation_liquid_temperature_average
sensor.brewassistant_fermentation_air_liquid_delta_average
```

---

## Rolling windows

Each sensor exposes the following attributes:

```text
current
average_5m
average_15m
average_30m
minimum_30m
maximum_30m
trend_c_per_hour
trend_label
sample_count
oldest_sample
newest_sample
window_minutes
primary_window_minutes
source_entity
source_status
sample_allowed
summary
```

Primary UI value:

```text
state = average_15m when available
fallback = current
```

Trend labels:

```text
collecting
cooling
warming
stable
```

---

## Kegerator air stats

Source:

```text
sensor.kyl_temperatur_4
```

Purpose:

```text
show what the kegerator air is actually doing
support Climate Supervisor diagnostics
separate compressor state from thermal inertia
```

Useful UI language:

```text
compressor ON + trend cooling → Kyler aktivt
compressor OFF + trend cooling → Efterkylning
compressor OFF + trend warming → Värms upp
stable trend → Stabil lufttemperatur
```

---

## Fermentation chamber air stats

Source:

```text
configured chamber temperature entity
```

Currently this may be the same physical source as the kegerator air sensor when the same fridge is used for serving/carbonation and fermentation.

It is still kept as a separate BrewAssistant concept because future fermentation and cold-crash logic needs chamber-air context.

---

## Fermentation liquid stats

Liquid stats are deliberately stricter than air stats.

They only sample when:

```text
real liquid source is available
AND
fermentation/cold-crash scope is active
```

They do not sample fallback chamber/kegerator air as liquid.

This avoids false dashboard states such as:

```text
Liquid avg = chamber air
Air/liquid delta = 0.0 °C
```

or stale external probe values being interpreted as an active fermentation batch.

---

## Air/liquid delta stats

Air/liquid delta is only valid when real liquid stats are valid.

```text
air_liquid_delta = chamber air - real liquid
```

It is hidden when fermentation/cold-crash is out of scope.

---

## Source status

Possible `source_status` values:

```text
sampling
fallback_not_sampled
out_of_scope_not_sampled
not_sampled
```

Meaning:

```text
sampling
→ this sensor is actively collecting valid samples

fallback_not_sampled
→ the value would come from a fallback source and is intentionally ignored

out_of_scope_not_sampled
→ a real source may exist, but no active fermentation/cold-crash context exists

not_sampled
→ generic invalid/not allowed sampling state
```

---

## Scope rule

Kegerator air and chamber air are environmental readings and may always sample.

Fermentation liquid and air/liquid delta are process readings and require active process scope.

```text
No active fermentation/cold-crash
→ liquid avg unknown
→ air/liquid delta unknown
→ diagnostics remain in attributes
```

---

## UI cards

Current dashboard card:

```text
Temperature Stats Cockpit v1.1
```

Recommended placement:

```text
Below Climate Supervisor
Above or near Kegerator raw-status cards
```

This makes the right-side dashboard stack read as:

```text
Climate Supervisor = desired dynamic target
Temperature Stats = what the air is doing
Kegerator = raw hardware/climate state
```

---

## Persistence

Current version:

```text
in-memory only
resets on Home Assistant restart
```

This is acceptable for UI/trend context. Persistence can be added later if trend continuity becomes important.

---

## Future use

Temperature Stats will be used by future supervisor logic for:

```text
target damping
cold-crash overshoot prevention
fermentation air-target recommendations
thermal inertia detection
better dashboard language around compressor state
```
