# Fermentation compatibility package

Status: compatibility layer only  
Code/documentation snapshot: 2026-09-11

`fermentation/` is **not** the canonical fermentation backend anymore.

The original fermentation code has been split into two independent current domains:

```text
../fermentation_tracking/
  fermentation observations, SG/temperature normalization,
  progress, ABV, stability, readiness and process-level target recommendation

../fermentation_chamber/
  current physical fermentation provider:
  chamber-air target translation and supervised climate bridge
```

The generic fermentation control/provider contract is documented in [`../../../docs/backends/fermentation-control.md`](../../../docs/backends/fermentation-control.md).

Files in this directory preserve legacy imports and registration paths so the root Home Assistant platform code and existing callers can migrate without breaking immediately.

## Important terminology boundary

The word **fermentation** can describe BrewAssistant's overall fermentation strategy/control flow, but that does not make this legacy `fermentation/` package the owner of new business logic.

Conceptually the wider flow is:

```text
fermentation_tracking
  process observations / readiness / desired beer target
        |
        v
selected physical provider
  e.g. fermentation_chamber today
  or a future Grainfather fermenter provider
        |
        v
local controller
  owns actual heat/cool regulation
```

Any future common provider-selection/authority logic should live in an explicitly named canonical backend/support location, not silently grow inside this compatibility package.

## Current bridges

| File | Canonical implementation |
| --- | --- |
| `fermentation_runtime.py` | re-exports `fermentation_tracking.runtime` |
| `fermentation_tracking_sensor.py` | compatibility path to tracking sensors |
| `fermentation_climate_supervisor.py` | compatibility path to chamber supervisor |
| `fermentation_air_target.py` | combines/registers tracking + chamber sensor surfaces for old imports |

For example, `fermentation_runtime.py` is intentionally only:

```python
from ..fermentation_tracking.runtime import *
```

`fermentation_air_target.py` imports the real chamber air-target implementation and tracking sensor factory, then presents them through the older registration function.

## Rules for new work

Do not add new fermentation business logic here.

Choose the owning backend instead:

- observation/calculation/source-policy/process-target work -> `fermentation_tracking/`;
- chamber target translation/climate-provider work -> `fermentation_chamber/`;
- future hardware-provider work -> a separate explicitly named provider package;
- future generic provider authority/selection -> a canonical non-compatibility location defined when that executable layer is implemented.

This package may contain thin compatibility aliases until old import paths are fully retired.

## Removal criteria

The package can only be removed after all of these are true:

1. root platform modules no longer import legacy `fermentation.*` paths;
2. no tests or external integrations rely on those import paths;
3. entity registration has moved cleanly to the canonical packages;
4. a migration/release note exists for any externally imported Python symbols.

## Do not change casually

1. Do not create a third source of fermentation truth here.
2. Keep wrappers thin and obvious.
3. Compatibility code must not change control ownership or calculations while forwarding calls.
4. Do not place future provider selection or hardware-control logic in this package merely because its name is `fermentation`.
