# Fermentation compatibility package

Status: compatibility layer only  
Code snapshot documented: 2026-09-05

`fermentation/` is **not** the canonical fermentation backend anymore.

The original fermentation code has been split into two independent domains:

```text
../fermentation_tracking/
  fermentation observations, SG/temperature normalization,
  progress, ABV, stability and readiness

../fermentation_chamber/
  chamber-air target recommendation and supervised climate bridge
```

Files in this directory preserve legacy imports and registration paths so the root Home Assistant platform code and existing callers can migrate without breaking immediately.

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

- observation/calculation/source-policy work -> `fermentation_tracking/`;
- chamber air-target/climate-control work -> `fermentation_chamber/`.

This package may contain thin compatibility aliases until old import paths are fully retired.

## Removal criteria

The package can only be removed after all of these are true:

1. root platform modules no longer import legacy `fermentation.*` paths;
2. no tests or external integrations rely on those import paths;
3. entity registration has moved cleanly to the two canonical packages;
4. a migration/release note exists for any externally imported Python symbols.

## Do not change casually

1. Do not create a third source of fermentation truth here.
2. Keep wrappers thin and obvious.
3. Compatibility code must not change control ownership or calculations while forwarding calls.
