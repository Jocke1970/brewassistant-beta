# BrewAssistant Grainfather integration extension

Status: **fork active / Phase 1 implemented / realtime discovery ready**  
Last synced: **2026-10-01**  
Primary upstream: `fidley/grainfather_integration`  
BrewAssistant fork: `Jocke1970/grainfather_integration`  
Development branch: `brewassistant-grainfather`

This document defines the development plan for a BrewAssistant-oriented extension of the Home Assistant Grainfather integration.

The intent is **not** to merge old repositories wholesale. Their implementations are evidence about useful Grainfather/Particle interfaces. New code should be implemented cleanly in the current Home Assistant integration style, with async I/O, coordinator ownership, explicit read/write boundaries and regression tests.

## 1. Branch and upstream policy

Use the same model as the BrewAssistant RAPT Cloud Link work:

```text
upstream
fidley/grainfather_integration
└── main

planned fork
Jocke1970/grainfather_integration
├── main
│   └── stays as close as practical to upstream/main
│
└── brewassistant-grainfather
    └── BrewAssistant-oriented development
```

Local clone convention:

```text
origin   -> Jocke1970/grainfather_integration
upstream -> fidley/grainfather_integration
```

Naming convention for permanent BrewAssistant integration branches:

```text
brewassistant-<integration>
```

Examples:

```text
brewassistant-raptcloudlink
brewassistant-grainfather
brewassistant-brewfather
```

This convention is reserved for brewing-related integrations that belong to the BrewAssistant ecosystem.

Rules:

1. Do not develop BrewAssistant-specific changes directly on fork `main`.
2. Periodically sync fork `main` from `upstream/main`.
3. Rebase or merge the current upstream baseline into `brewassistant-grainfather` deliberately.
4. Keep generally useful changes separable enough to propose upstream independently.
5. Do not require BrewAssistant itself to understand Grainfather/Particle transport details.
6. Do not enable writable controller behavior merely because an old repository demonstrates an endpoint.

The fork and `brewassistant-grainfather` branch now exist. Fork `main` remains aligned with upstream base `f57106cb0f126b387257d47ad6a9d12e7f02b5c7` while BrewAssistant-oriented changes live only on the dedicated branch.

## 2. Evidence sources

### Current foundation — fidley/grainfather_integration

License: MIT.  
Current role: primary Home Assistant integration and architectural base.

Verified useful surfaces include:

- Grainfather Community account authentication;
- fermentation equipment discovery;
- brew-session discovery and editing;
- fermentation history;
- Home Assistant sensor/select/number/service patterns;
- current temperature and gravity exposure;
- session target/step service surfaces.

Live GF30 testing showed that the current integration obtains temperature from history when the top-level equipment record has `last_temperature: null`.

### Historical controller reference — wardsimon/gfFermentation

License: BSD-3-Clause.  
Historical role: direct Grainfather fermentation-controller access through Grainfather-issued Particle sessions.

It documents controller properties/functions including:

```text
temp
targetTemp
heatStatus
coolStatus
online
status

setTarget
controlFermenting
highActivity
setHeat
setCool
```

It also documents logical fermenting modes such as pause/resume, heat+cool, heat-only and cool-only.

These names are **research evidence**, not proof that the 2026 GF30 Wi-Fi controller still exposes the same transport.

### Historical realtime reference — mossman/grainfather_exporter

License: MIT.  
Historical role: read Grainfather conical telemetry through Grainfather-issued Particle access plus Particle event streaming.

It independently confirms realtime payload fields equivalent to:

```text
temp
target
heatStatus
coolStatus
```

and demonstrates the historical use of `highActivity` plus Particle event subscription for fresher telemetry.

## 3. Live 2026 GF30 facts already verified

The real GF30 used for BrewAssistant validation has:

- Grainfather equipment type 30;
- a linked ESP/controller identity;
- `is_controller_linked: true`;
- no legacy `particle_device_id` in the Grainfather equipment record;
- working Grainfather cloud temperature history;
- working Home Assistant temperature telemetry.

The Grainfather history endpoint has also been field-verified to include:

```text
temperature
target_temperature
```

The current upstream HA integration only exposes the former as a dedicated device temperature sensor.

Therefore the first extension does **not** depend on Particle at all: target-temperature exposure can be built from already verified Grainfather REST/history data.

## 4. Target architecture

The integration should normalize multiple Grainfather data sources behind one Home Assistant device model:

```text
Grainfather Community REST
├── equipment metadata
├── brew sessions / fermentation steps
├── history temperature
└── history target_temperature

optional controller realtime source
├── online/status
├── temperature
├── target
├── heating
└── cooling

              ↓ normalize

Home Assistant Grainfather device
├── actual temperature
├── target temperature
├── heating
├── cooling
├── online
├── controller status
├── controller linked
└── session metadata
```

Fallback policy should be explicit:

```text
actual temperature:
  realtime controller value if verified/fresh
  -> otherwise Grainfather history temperature

target temperature:
  realtime controller target if verified/fresh
  -> otherwise Grainfather history target_temperature
```

No silent cross-source fallback may turn a stale controller value into a current value.

## 5. Phase plan

### Phase 0 — fork/branch setup and evidence capture

Status: complete.

- create `Jocke1970/grainfather_integration` as a fork of `fidley/grainfather_integration`;
- keep fork `main` upstream-clean;
- create `brewassistant-grainfather`;
- record upstream base SHA before feature development;
- document external reference repositories/licenses;
- keep the GF30 cloud-link recovery note in BrewAssistant as field evidence.

Exit: clean branch topology exists and future diffs remain reviewable.

### Phase 1 — expose verified REST target temperature

Status: implemented on `Jocke1970/grainfather_integration:brewassistant-grainfather`; live HA validation still pending.

Extend the current history model/parser with `target_temperature`.

Expected work:

- add target temperature to `GrainfatherHistoryPoint`;
- retain history points that contain only target data;
- create a dedicated GF30/fermentation-device target-temperature sensor;
- use latest valid history target as read-only value;
- add tests for target-only, temperature-only and mixed history points;
- preserve existing temperature/SG behavior.

Expected HA surface:

```text
Temperature
Target temperature
Gravity
```

This phase is read-only and based entirely on live-verified 2026 Grainfather data.

### Phase 2 — determine whether the current GF30 still has Particle realtime access

Status: read-only field probe implemented; live account result pending.

Read-only test sequence:

1. authenticate normally to Grainfather Community;
2. query the historical Grainfather Particle-token surface if it still exists;
3. do not expose or persist returned access tokens;
4. if a valid Particle session is returned, enumerate only the account-authorized devices;
5. inspect read-only controller variables/events;
6. do not call controller functions in this phase.

Questions to answer:

- Does the current ESP-linked GF30 receive a Grainfather-issued Particle token?
- Does its controller appear in Particle device enumeration?
- Are `temp`, target, `heatStatus`, `coolStatus`, online/status still present?
- What is the update cadence?
- Does realtime identity correlate safely with the Grainfather equipment record?

Exit A: Particle realtime confirmed and identity mapping documented.  
Exit B: Particle path absent/obsolete; switch research to the newer app/backend transport.

### Phase 3 — modern-controller fallback research if Particle is absent

Status: conditional.

If the current GF30 is not represented through Particle:

- return to the already inspected Grainfather Android application;
- identify only the current read/status transport used by the ESP-linked controller;
- prefer Grainfather-owned authenticated APIs over device-local or credential-bypass paths;
- implement no controller write until semantics are independently field-verified.

Exit: modern controller telemetry source identified, or REST/history remains the accepted read-only source.

### Phase 4 — normalized realtime HA entities

Status: blocked on Phase 2/3.

Candidate entities:

```text
sensor.<gf30>_temperature
sensor.<gf30>_target_temperature
binary_sensor.<gf30>_heating
binary_sensor.<gf30>_cooling
binary_sensor.<gf30>_online
sensor.<gf30>_controller_status
sensor.<gf30>_last_controller_update
```

Exact entity IDs remain dynamic; BrewAssistant discovers by stable integration metadata/capability rather than hard-coding names.

Requirements:

- coordinator-owned async polling/subscription;
- clear freshness timestamps;
- explicit source/provenance where useful;
- no duplicate competing temperature truth;
- fail-passive if realtime transport is unavailable;
- REST/history fallback remains available.

### Phase 5 — BrewAssistant consumption

Status: planned after stable read-only HA surface.

BrewAssistant should consume a normalized Grainfather contract:

```text
actual_temperature
target_temperature
heating
cooling
online
controller_linked
controller_status
```

BrewAssistant must not directly authenticate to Particle or duplicate Grainfather client logic if the HA integration can provide the normalized surface.

The BrewAssistant `grainfather_fermenter` backend remains responsible for:

- provider selection;
- telemetry freshness/safe-point logic;
- Pill/internal comparison;
- thermal learning;
- Supervised Apply proposal/audit logic.

The Grainfather HA integration remains responsible for:

- Grainfather authentication;
- Grainfather/controller transport;
- normalized entities/services;
- device-specific read/write mechanics.

## 6. Writable-control roadmap

Writable control is deliberately later than telemetry.

Potential historical capabilities include:

```text
set target
pause/resume fermentation control
heat+cool
heat-only
cool-only
```

None is accepted for the 2026 GF30 until tested against the physical controller.

First writable milestone should be **target temperature only**, with:

1. explicit BrewAssistant Supervised Apply proposal;
2. user confirmation;
3. one integration-owned target operation;
4. post-write target readback;
5. timeout/failure surfaced as failure, not assumed success;
6. no direct BrewAssistant heater/cooling-pump commands.

Only after repeated physical validation should other controller modes be considered.

A Home Assistant `climate` entity may eventually be appropriate, but should not be introduced until mode/state semantics and readback are proven.

## 7. Coolant ownership remains separate

The Grainfather integration must not absorb BrewAssistant's DIY reservoir/freezer design.

Ownership remains:

```text
GF30 controller
  -> beer temperature
  -> local heater
  -> GF30 cooling-demand / circulation-pump behavior

Home Assistant generic_thermostat
  -> freezer compressor
  -> coolant reservoir target

BrewAssistant
  -> future adaptive coolant target recommendation
  -> supervised/guarded thermostat-target bridge
```

This separation prevents the Grainfather integration from becoming a second coolant/freezer controller.

## 8. Testing requirements

Minimum tests before each milestone:

### REST target phase

- parses `target_temperature`;
- preserves target-only history points;
- selects latest valid target;
- remains compatible with old payloads lacking the field;
- does not alter temperature/SG fallback behavior.

### Realtime phase

- token/session secrets never become HA state attributes or logs;
- identity mapping fails closed when ambiguous;
- stale realtime data falls back only according to documented rules;
- online/offline transitions are represented correctly;
- reconnect does not create duplicate entities/subscriptions.

### Writable target phase

- no command without explicit HA/BrewAssistant authorization path;
- target range validation;
- timeout/error handling;
- readback mismatch surfaced;
- repeated identical target is idempotent where possible;
- cloud/controller outage is fail-passive.

## 9. Upstream contribution strategy

Prefer small, generally useful upstream pull requests where practical.

Good upstream candidates:

- history `target_temperature` parsing;
- target-temperature sensor;
- generic controller online/heating/cooling telemetry if the transport is reusable;
- tests for documented Grainfather payload variants.

Likely BrewAssistant-fork-only candidates:

- BA-specific metadata/capability hints;
- assumptions that exist only to support BA provider selection;
- experimental controller surfaces not yet suitable for general upstream use.

The fork must remain usable as a Grainfather Home Assistant integration without requiring BrewAssistant.

## 10. Current next action

When work resumes:

```text
1. Run the read-only Particle capability probe against the linked GF30 account
2. Validate the new Target Temperature entity in Home Assistant against the real GF30
3. Record whether Particle exposes the current ESP-linked controller
4. Choose Particle realtime or modern-backend research based on evidence
5. Choose Particle realtime or modern-backend research based on evidence
6. Add normalized heating/cooling/online/status telemetry
7. Feed verified entities into BrewAssistant grainfather_fermenter
8. Only then start supervised target-write validation
```

Do not start with controller writes.
