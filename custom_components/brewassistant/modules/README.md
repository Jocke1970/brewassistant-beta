# Module and capability registry

Status: active metadata foundation  
Code snapshot documented: 2026-09-05

`modules` describes BrewAssistant capabilities and intended module boundaries. It is a metadata/registry layer, not a process or hardware backend.

The registry is useful for keeping the architecture modular: Brewday Runtime and Fermentation Tracking are base workflow capabilities, while hardware such as BrewZilla or optional serving/chamber features are adapters/modules layered on top.

## Files

| File | Purpose |
| --- | --- |
| `manifest.py` | Data models/enums for module type, capability type and policy |
| `registry.py` | Known module manifests and capability declarations |
| `module_summary_sensor.py` | Home Assistant summary/presentation of registry state |

## Module types

The manifest model distinguishes concepts such as:

- base modules;
- hardware adapters;
- optional modules;
- diagnostics.

Capabilities also carry a policy such as read-only, guidance-only, confirmation-required, direct or disabled.

These declarations describe architectural intent/capability exposure. They are not a substitute for runtime safety enforcement in the owning backend.

## Current registry highlights

Base/default foundations include:

```text
core
brewday_runtime
fermentation_tracking
carbonation_guidance
diagnostics
```

Optional/hardware concepts include:

```text
brewzilla
kegerator
fermentation_chamber_control
counterflow_chiller
notifications
```

The registry also reserves future adapter concepts such as Grainfather and BrewCreator/Fercubator.

## Important architectural notes encoded in the registry

- Brewday Runtime must not depend on BrewZilla.
- BrewZilla is a hardware adapter, not the BrewAssistant core.
- Fermentation Tracking is a base workflow; chamber control is optional and separate.
- Kegerator compressor/cooling is intended to remain owned by the HA climate layer in the modern architecture.
- Future hardware adapters should start conservatively/read-only where appropriate.

## Known drift risk

The module registry is an architectural declaration and can lag behind concrete backend evolution. For example, older capability text may still mention a CFC pump-control capability even though current Cooling Runtime v2 explicitly makes the BrewZilla wort pump operator-owned and non-writable by Cooling.

When registry capability wording conflicts with an active backend's code-local README and implementation, treat the backend implementation as current behavior and update the registry in a dedicated code change rather than silently documenting the stale declaration as fact.

## Rules for changes

1. Do not put runtime state machines or physical service calls in this package.
2. A capability policy is descriptive/registry metadata unless the owning control path explicitly enforces it.
3. Keep base workflows independent from optional hardware adapters.
4. When backend ownership changes, update both the owning backend README and the corresponding registry manifest/capability in the same implementation PR when practical.
5. Future adapters should reuse generic BrewAssistant contracts rather than copy BrewZilla-specific logic into the core.
