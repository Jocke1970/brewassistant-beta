# Shared backend utilities

Status: active support code  
Code snapshot documented: 2026-09-05

`shared` contains reusable BrewAssistant helpers that do not own a brewing process or physical actuator.

The current substantive helper is `temperature_stats.py`, which provides rolling temperature context for kegerator air, fermentation chamber air and fermentation liquid.

## Rolling temperature statistics

The helper keeps recent samples in memory and exposes smoothing/trend context such as:

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
oldest/newest sample
```

Current limits:

```text
maximum window: 30 min
minimum sample spacing: 20 s
trend requires at least 120 s between first/last sample
```

Trend labels are simple:

```text
<= -0.1 °C/h -> cooling
>= +0.1 °C/h -> warming
otherwise     -> stable
insufficient data -> collecting
```

## Source-aware sampling

The helper can attach per-sensor source selection and sampling guards. In particular, fermentation samples can be cleared/not sampled when their source is semantically invalid for the current fermentation scope instead of carrying stale rolling context into a different process state.

The current data is stored in `hass.data` only; rolling history is not persisted across Home Assistant restart.

## Consumers

Rolling statistics are consumed by domains such as:

- kegerator fan control (air trend/average context);
- fermentation chamber recommendation logic (legacy average/trend fallback);
- dashboard diagnostics.

A shared utility must not become the owner of those consumers' control decisions.

## Rules for new shared code

Put code here only when it is genuinely domain-neutral and reused by multiple BrewAssistant areas.

Do **not** move a safety decision, ownership rule or state machine here simply to reduce imports. Those belong in the backend that owns the behavior.

## Do not change casually

1. Rolling values are advisory context and currently volatile/in-memory.
2. Sampling guards are part of semantic source hygiene; do not keep stale samples merely to make charts look continuous.
3. Consumers must remain responsible for their own safety and control boundaries.
