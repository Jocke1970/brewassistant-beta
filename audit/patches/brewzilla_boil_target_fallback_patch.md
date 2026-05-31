# BrewZilla boil target fallback patch

Observed during reality test:

```text
Brewday runtime: live / Boil
BrewZilla target: 78.0°C
BrewZilla orchestration: blocked
Reason: Missing or invalid Brew Tracker target
```

Problem:

Brewfather Brew Tracker may expose a boil stage without a temperature target. BrewAssistant then treats the missing target as invalid, so BrewZilla remains at the previous mash-out target, e.g. 78°C.

Expected behavior:

```text
When runtime stage/step indicates boil or heating-to-boil
and Brew Tracker target is missing
and Brewday runtime is active
then requested_target should fall back to 100.0°C
```

Suggested backend patch:

```text
Add BOIL_TARGET_FALLBACK = 100.0
Detect boil context from stage/step/next_step/raw_step_name containing boil/kok/kokgiva
If target_temperature is None during active boil context, set requested_target = 100.0
Expose attributes:
- boil_stage
- boil_target_fallback_active
- requested_target_source = boil_fallback
Set control_reason = Boil stage detected without Brew Tracker target; using 100°C boil fallback
```

Manual workaround before code patch is applied:

```text
number.brewzilla_target_temperature = 100.0
switch.brewzilla_heater = on
number.brewzilla_heat_utilization = 100 during ramp to boil
then reduce heat utilization once rolling boil is established
```
