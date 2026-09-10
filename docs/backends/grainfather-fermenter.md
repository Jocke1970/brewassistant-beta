# Grainfather Fermenter / GF30 roadmap

Status: prepared / parked until live hardware is available  
Last synced: 2026-09-10  
Initial hardware target: Grainfather GF30 Conical Fermenter  
Upstream Home Assistant integration: `fidley/grainfather_integration`

This document records where BrewAssistant currently stands and the intended route from read-only discovery to safe temperature-target control.

The code-local contract remains authoritative for current behavior:

[`../../custom_components/brewassistant/grainfather_fermenter/README.md`](../../custom_components/brewassistant/grainfather_fermenter/README.md)

## 1. Architectural decision

GF30 support is a fermentation-hardware concern, not a hot-side brewing-system concern.

BrewAssistant therefore keeps these concepts separate:

```text
grainfather
  reserved module/capability slot
  future hot-side adapter for Grainfather brewing systems
  examples: G30/G40-class equipment

grainfather_fermenter/
  fermentation-hardware adapter
  initial target: GF30 Conical Fermenter
```

The existing `grainfather` module must not be repurposed for GF30.

## 2. Current implementation state

Phase 1 exists as a deliberately dormant/read-only scaffold on the GF30 feature branch.

Implemented now:

- dynamic discovery of Grainfather fermentation devices using upstream `grainfather_entity_type` attributes;
- grouping of temperature/gravity telemetry by Grainfather `device_id`;
- controller-link, brew-session and `last_heard` normalization;
- brew-session matching through `linked_brew_session_id`;
- detection of the upstream `grainfather.adjust_current_step_temperature` service;
- conservative candidate selection when one controller-linked device is visible;
- fail-closed behavior when multiple controller-linked devices are present;
- explicit `model_verified: false` while no reliable upstream field proves that a discovered controller is specifically a GF30;
- a readiness calculation for a future supervised temperature-target bridge;
- regression tests that keep this backend separate from the reserved Grainfather hot-side module.

Not implemented now:

- no Home Assistant service call from the GF30 backend;
- no direct heater control;
- no direct cooling/glycol/compressor/valve control;
- no automatic temperature target write;
- no provider-selection entity yet;
- no assumption about GF30-specific entity IDs;
- no assumption that a friendly name containing `GF30` proves model identity;
- no claim that a gravity sensor is physically built into the GF30.

This is intentional. Without live hardware, these boundaries prevent the preparation work from hard-coding guesses that later become technical debt.

## 3. Ownership model

Fermentation process truth remains independent of the physical temperature-control hardware.

```text
fermentation_tracking
  owns observations, SG/temperature source resolution,
  progress/stability/readiness and target recommendation

physical target provider
  translates an approved target to one physical controller

physical controller
  owns actual heater/cooling regulation
```

For the current chamber:

```text
fermentation_tracking
  -> fermentation_chamber
  -> climate.fermentation_chamber
```

For the future GF30 path:

```text
fermentation_tracking
  -> grainfather_fermenter
  -> Grainfather profile target
  -> GF30 controller
```

The two provider paths are alternatives. They must never compete for the same fermentation.

## 4. Expected future control boundary

The most promising upstream write surface currently identified is:

```text
grainfather.adjust_current_step_temperature
```

The intended first writable flow is:

```text
BrewAssistant recommendation
        |
        v
Supervised Apply pending action
        |
   user confirms
        |
        v
registered Grainfather fermenter executor
        |
        v
grainfather.adjust_current_step_temperature
        |
        v
Grainfather cloud/controller
        |
        v
GF30 owns physical heating/cooling regulation
```

This preserves BrewAssistant's confirmation boundary while leaving physical regulation to the Grainfather controller.

The Grainfather service itself cannot consume BrewAssistant's one-shot execution grant, so the future implementation should use a registered explicit Supervised Apply executor rather than relying on an unguarded generic service-call path.

## 5. Physical-provider selection

Before target writes are introduced, BrewAssistant needs an explicit physical fermentation target provider.

Conceptually:

```text
Monitor only
Current fermentation chamber
Grainfather fermenter
```

Exact entity/UI naming is intentionally deferred until implementation, but the behavior requirement is fixed:

- only one provider may own physical temperature-target application;
- `fermentation_tracking` remains independent of provider choice;
- switching provider must not cause both old and new controllers to receive writes;
- unavailable/ambiguous hardware must fail passive rather than silently fall back to another writable provider.

## 6. Live GF30 validation gate

A physical GF30 is required before control work continues.

First live installation should capture and verify:

1. actual Home Assistant entity IDs, attributes and device relationships exposed by `fidley/grainfather_integration`;
2. whether the controller is represented with `is_controller_linked: true`;
3. whether any stable upstream field can identify the model as GF30;
4. brew-session linkage behavior before, during and after fermentation;
5. temperature update cadence and `last_heard` freshness behavior;
6. what gravity telemetry represents when present and whether it originates from a separate collaborating device;
7. availability and parameter behavior of `grainfather.adjust_current_step_temperature`;
8. write-to-readback latency and failure modes;
9. behavior if Grainfather cloud/API is unavailable;
10. target handling during ramps, diacetyl rest and cold crash;
11. controller behavior with heating only versus attached cooling accessories;
12. whether changing the active step target has any unintended profile/session side effects.

No writable BrewAssistant bridge should be merged merely because the upstream service exists. Service semantics and readback must be proven against the real controller.

## 7. Roadmap

### Phase 1 — Read-only preparation

Status: **implemented on feature branch**.

Deliverables:

- backend package;
- discovery/normalization snapshot;
- fail-passive candidate selection;
- upstream service capability detection;
- architecture documentation;
- static regression tests.

Exit condition: preparation is documented and can remain parked safely without hardware.

### Phase 2 — Live hardware characterization

Status: **blocked on physical GF30**.

Deliverables:

- capture real HA state/attribute examples;
- verify controller/session matching;
- verify freshness/readback characteristics;
- identify stable GF30 model evidence if available;
- document cooling-accessory behavior actually observed.

Exit condition: BrewAssistant can unambiguously identify the intended controller and trust its telemetry/readback sufficiently for supervised target testing.

### Phase 3 — Provider selection

Status: planned.

Deliverables:

- explicit fermentation physical-provider selector;
- monitor-only option;
- hard mutual exclusion between current chamber and Grainfather fermenter write paths;
- passive behavior for unavailable/ambiguous selected provider.

Exit condition: target ownership cannot be ambiguous.

### Phase 4 — Supervised Apply target bridge

Status: planned after Phase 2/3.

Deliverables:

- registered Grainfather fermenter Supervised Apply executor;
- pending action showing current target, proposed target and selected controller/session context;
- explicit confirmation before each target change;
- service call to the verified Grainfather target surface;
- post-write readback check;
- useful failure/audit state when the cloud/service does not confirm the target.

Exit condition: repeated supervised target changes work predictably without bypassing BrewAssistant's confirmation boundary.

### Phase 5 — Field-test hardening

Status: future.

Validate with real fermentations across:

- initial fermentation setpoint;
- temperature ramps;
- diacetyl rest;
- cold crash where supported;
- Home Assistant restart;
- Grainfather cloud outage/recovery;
- stale telemetry;
- session changes;
- provider switching while idle.

Add guards from observed failure modes rather than speculative ones.

### Phase 6 — Optional automation

Status: deliberately undecided.

Automatic target application is not required for the GF30 backend to be successful. Supervised Apply may remain the preferred operating mode.

Only consider more automatic control after repeated field evidence shows that:

- target writes are idempotent/reliable;
- readback is trustworthy;
- provider ownership is unambiguous;
- cloud outages fail safely;
- BrewAssistant's fermentation recommendation logic is sufficiently stable for unattended application.

## 8. Parking point

Until the GF30 physically exists, the correct development posture is:

```text
KEEP:
- read-only discovery scaffold
- architecture separation
- documentation and tests

DO NOT ADD YET:
- guessed GF30 entity IDs
- model-name heuristics as proof
- physical actuator assumptions
- automatic target writes
- direct heater/cooling control
```

When hardware arrives, resume from **Phase 2 — Live hardware characterization**, not by redesigning the backend from scratch.

## 9. Files of interest

Current feature implementation:

```text
custom_components/brewassistant/grainfather_fermenter/__init__.py
custom_components/brewassistant/grainfather_fermenter/adapter.py
custom_components/brewassistant/grainfather_fermenter/README.md
tests/test_grainfather_fermenter_backend.py
```

Architecture/index documentation:

```text
custom_components/brewassistant/README.md
docs/backend-domain-layout.md
docs/backends/README.md
docs/backends/grainfather-fermenter.md
```

When GF30 work resumes, update the code-local README first for behavioral contract changes, then sync this roadmap when milestone status changes.
