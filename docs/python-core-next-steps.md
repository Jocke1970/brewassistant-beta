# BrewAssistant Python Core Next Steps

This document prepares the next implementation path after v0.9.

The guiding rule remains:

```text
Read-only first. Recommendations before control. Control only after validation.
```

---

## Completed validation

### v0.5 Options Flow / Pill stale

```text
[x] Base core sensors still work
[x] Process mirror still works
[x] Smart recommendations still work
[x] Pill stale signals work
[x] Options flow appears under BrewAssistant -> Configure
[x] Saving options reloads the integration cleanly
[x] No new numbered entities remain unresolved
```

Validation notes:

```text
Base core: OK
Process mirror: OK
Smart recommendations: OK
Pill stale: OK
Options flow: OK after OptionsFlowWithConfigEntry compatibility patch
Options save/reload: OK
```

### v0.6 Source Health + Entity Diagnostics

```text
[x] Source health summary sensor works
[x] Source health level sensor works
[x] Configured source entity sensors work
[x] Source availability binary sensors work
[x] Current setup reports 6/6 sources available
[x] Liquid temperature source resolves to sensor.yellow_pill_temperature
[x] Gravity source resolves to sensor.yellow_pill_gravity
```

Validation notes:

```text
Source health: OK · 6/6 sources available
Source health level: ok
Liquid source: sensor.yellow_pill_temperature · OK
Gravity source: sensor.yellow_pill_gravity · OK
```

### v0.7 Debug Card v2

```text
[x] Core section added
[x] Process section added
[x] Smart recommendation section added
[x] Pill health section added
[x] Source health section added
[x] Configured entity diagnostics added
```

Validation notes:

```text
Dashboard card upgraded and accepted for continued use.
```

### v0.8 Next Recommended Action

```text
[x] Next recommended action sensor works
[x] Category attribute works
[x] Priority attribute works
[x] Reason attribute works
[x] Icon attribute works
[x] Current cold crash scenario resolves to Cooling + fan recommended
```

Validation notes:

```text
Action: Cooling + fan recommended
Category: smart_fermentation
Priority: info
Reason: Cooling would help · Fan assist recommended for cooling
Icon: mdi:fan-chevron-up
```

### v0.9 Brewfather Runtime Normalization

```text
[x] Runtime recipe name sensor works
[x] Runtime status sensor works
[x] Runtime primary target temperature sensor works
[x] Runtime cold crash target temperature sensor works
[x] Runtime target FG sensor works
[x] Runtime source status sensor works
[x] Runtime Brewfather availability binary sensor works
[ ] Runtime source options appear under BrewAssistant -> Configure
[ ] Saving runtime options reloads cleanly
```

Validation notes:

```text
Recipe name: FWK Creative Extra Light - Summer IPL v3 (NovaLager)
Runtime status: Fermenting
Primary target: 15.0 °C
Cold crash target: 2.0 °C
Target FG: 0.99
Source status: OK · 5/5 runtime sources available
Brewfather available: on
```

---

## v1.0 candidate: Read-only Core Stable

v1.0 should mean:

```text
[x] Base temperature/target/gravity normalization is stable
[x] Process mirror is stable
[x] Smart recommendations are stable
[x] Source diagnostics are stable
[x] Debug card is useful
[x] Options flow works
[x] Next recommended action works
[x] Runtime normalization works
[x] No hardware control in Python Core yet
```

At that point, dashboards can rely primarily on Python Core for display/state decisions.

---

## Later: smart fermentation control

Do not move hardware control until read-only recommendations have been tested over multiple real fermentation/cold-crash scenarios.

Future safe-control steps:

```text
[ ] expose enable switch
[ ] expose mode select
[ ] expose tuning numbers
[ ] expose services for applying targets
[ ] add safety checks
[ ] add manual override
[ ] add emergency off path
[ ] then consider climate/switch/fan actions
```

---

## Notes from v0.4-v0.9 lessons

- Entity registry can keep old object IDs even after code changes.
- New entity names may become `brewassistant_2`, `brewassistant_3`, etc. if Home Assistant cannot derive a unique/stable object ID.
- Always check real entities by iterating `states.sensor` / `states.binary_sensor`, not only by calling `states('entity_id')`.
- `states('missing.entity')` returns `unknown`, which can be misleading.
- For new sensors, stable `suggested_object_id` and explicit names matter.
- Source health diagnostics should be checked before debugging temperature, gravity or target logic.
- Next recommended action should prioritize source health and Pill health before normal process suggestions.
- Runtime normalization is read-only and should tolerate missing optional sources.
