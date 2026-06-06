# Manual Brewday Runtime

Manual Brewday is the Python-owned fallback/runtime source for brewdays that are not driven by Brewfather Brew Tracker.

It is intended for supervised BrewZilla/BIAB-style brewday operation where BrewAssistant owns the runtime state, while the operator remains in control of physical actions.

## Runtime chain

```text
Manual Brewday services
→ Manual Brewday store/runtime
→ Normalized Brewday Runtime
→ Stage Engine
→ BrewZilla Runtime
→ BrewZilla Orchestration
→ Dashboard/operator controls
```

Manual Brewday is selected by the normalized Brewday Runtime layer when it is active. BrewZilla Orchestration must read the normalized runtime layer, not only the Brewfather/core runtime.

## Validated behavior

```text
✅ Manual Brewday prepare/start/pause/next/reset/finish services
✅ Manual Brewday jump services for Mash, Boil, Whirlpool/Hopstand and Cooling
✅ Manual Brewday source selected by normalized Brewday Runtime
✅ Stage Engine reads Manual Brewday stage/step
✅ BrewZilla requested target resolves from Manual Brewday runtime
✅ BrewZilla Orchestration can monitor Manual Brewday target
✅ Orchestration blocks safely when BrewZilla is disconnected
✅ Connected BrewZilla returns orchestration mode monitor
```

## Services

```text
brewassistant.manual_brewday_prepare
brewassistant.manual_brewday_start
brewassistant.manual_brewday_pause
brewassistant.manual_brewday_next
brewassistant.manual_brewday_start_mash
brewassistant.manual_brewday_start_boil
brewassistant.manual_brewday_start_whirlpool
brewassistant.manual_brewday_start_cooling
brewassistant.manual_brewday_finish
brewassistant.manual_brewday_reset
```

BrewZilla target apply remains owned by BrewZilla Orchestration:

```text
brewassistant.apply_brewzilla_target
```

## Safety model

Manual Brewday does not directly own heater, pump or boil-mode control.

Hardware control remains scoped through BrewZilla Orchestration and the section-specific control policy.

The intended model is:

```text
Runtime decides what should happen.
Stage Engine interprets what is happening.
Orchestration decides whether an action is allowed.
Dashboard exposes explicit operator actions.
```

## Important rules

```text
- RAPT Pill is not a hot-side brew temperature source.
- Hot-side temperature comes from BrewZilla and optional RAPT BLE/external thermometer.
- BrewZilla disconnected must block orchestration actions.
- Apply/confirm/direct behavior must remain section-scoped.
- Legacy input_* helpers from old packages are not source-of-truth for the Python runtime.
```

## Current operator UI

The current Manual Brewday dashboard card exposes compact service buttons for:

```text
Prepare
Start / Resume
Pause
Next
Jump Mash
Jump Boil
Jump Hopstand
Jump Chill
Apply BZ Target
Finish
Reset
```

Temperature display should be rounded to one decimal in dashboard cards.
