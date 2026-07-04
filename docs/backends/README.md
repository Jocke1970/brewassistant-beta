# BrewAssistant Backend Documentation

Status: active development / documentation index  
Last synced: 2026-07-04

This folder documents the purpose, ownership and control logic of BrewAssistant backend modules.

The goal is to make it clear what each backend is responsible for, what it is not responsible for, what safety boundaries it respects, and which event-log fields are useful when debugging.

## Documentation pattern

Each backend document should answer:

```text
What problem does this backend solve?
Which Home Assistant entities or runtime sources does it read?
Which entities/services can it write to?
Which safety guards can block it?
Which event-log fields prove it worked?
Which dashboard cards depend on it?
What should not be changed casually?
```

## Current backend docs

| Backend area | Status | Document |
| --- | --- | --- |
| BrewZilla control and Brewday Advice | Active test baseline | [`brewzilla-backend.md`](./brewzilla-backend.md) |
| BrewZilla control profile details | Active test notes | [`../brewzilla-control-profile.md`](../brewzilla-control-profile.md) |
| Brewday Runtime resolver | TODO | `brewday-runtime.md` |
| Brewday Event Log | TODO | `event-log.md` |
| Fermentation control | TODO | `fermentation.md` |
| Kegerator / serving guard | TODO | `kegerator.md` |
| Carbonation runtime | TODO | `carbonation.md` |
| Notifications | TODO | `notifications.md` |

## Backend doc rules

Backend docs should describe intent and safety behavior, not just restate code.

Prefer this:

```text
The paused mash-hold maintenance backend allows limited hold-temperature correction while Brewfather reports a paused hold, but only when the target is already synced and no higher safety guard is active.
```

Avoid this as the only explanation:

```text
Function X calls function Y.
```

## Event-log first workflow

When testing hot-side automation, event logs are the source of truth.

For each backend doc, include the event-log markers that prove expected behavior, for example:

```yaml
apply_result: direct_applied
actions:
  - set_target:42.0
  - set_heat_utilization:30.0
  - set_pump_utilization:70.0
```

This keeps debugging grounded in real BrewAssistant behavior instead of dashboard impressions alone.
