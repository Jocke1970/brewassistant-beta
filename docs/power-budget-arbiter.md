# Shared Power Budget Arbiter — planning specification

Status: planned / architecture only  
Planning baseline: 2026-09-15

The Power Budget Arbiter is a planned BrewAssistant coordination layer for multiple controllable electrical consumers that share a constrained circuit. Its first concrete use case is BrewZilla + HLT (sparge-water heater).

The arbiter is not a brewing state machine and should not own mash, sparge or recipe logic. It only decides which already-requested electrical loads may run at the same time and coordinates safe transfer of capacity between them.

## Problem statement

A naive implementation would let the HLT observe BrewZilla's current wattage/utilization and switch on whenever the measured total appears to fit under the circuit limit.

That is unsafe because measured power is only a snapshot. BrewZilla may request a much higher heat utilization immediately afterward. If both devices can change independently, the combined load can exceed the protected-circuit budget before Home Assistant can react.

The solution is explicit allocation rather than observation-only sharing.

## Core principle

```text
No consumer receives power merely because another consumer currently looks quiet.

Each consumer publishes demand.
The arbiter grants a bounded allocation.
Physical control paths may only apply demand inside that allocation.
```

For BrewZilla + HLT, BrewZilla remains the higher-priority process consumer. The HLT opportunistically uses genuinely available capacity and must yield before BrewZilla is allowed to reclaim watts that would otherwise make the combination unsafe.

## Ownership boundary

```text
BrewZilla backend
  decides desired heat utilization for brewing
  publishes requested electrical demand
  applies only the utilization permitted by the arbiter

HLT backend
  decides whether sparge water needs heat
  publishes HLT heater demand
  energizes only while a grant exists

Power Budget Arbiter
  owns grants, reservations, reclaim ordering and shared-circuit accounting

Brewday Runtime
  provides process-stage context
  does not perform electrical arbitration
```

The arbiter must not become a backdoor BrewZilla controller. It may constrain or sequence electrical permission, but BrewZilla remains responsible for its process decisions and safety chain.

## Configured circuit model

Proposed shared profile:

```text
profile_id
nominal_voltage_v              optional informational/calculation input
circuit_limit_w                required effective maximum, or derived from A/V
safety_margin_w                required conservative reserve
usable_budget_w                circuit_limit_w - safety_margin_w
optional circuit power sensor  verification/diagnostics only unless explicitly trusted
```

The implementation should prefer a directly configured conservative `usable_budget_w` over clever assumptions.

No code should silently assume that a Swedish installation is always 230 V / 10 A / 16 A. The protected circuit and wiring are commissioning inputs.

## Consumer descriptor

Each participating consumer should expose a normalized descriptor/demand, for example:

```text
consumer_id
mode: binary | variable
rated_power_w
requested_power_w
minimum_useful_power_w
priority
preemptible: bool
release_confirmation
request_reason
request_timestamp
```

Examples:

```text
BrewZilla
  mode = variable
  requested_power_w = desired_heat_utilization * configured_heater_power_w
  priority = hot_side_primary

HLT
  mode = binary
  requested_power_w = configured_hlt_heater_power_w
  priority = hot_side_secondary
  preemptible = true
```

The power mapping for BrewZilla must be calibrated/documented rather than assuming the reported heat-utilization percentage is an exact wattmeter.

## Reservation vs measured power

The arbiter should distinguish:

```text
requested/reserved power
  what a consumer is allowed to draw or is about to draw

observed power
  what a sensor currently reports
```

Safety permission is based primarily on conservative reservation, not a low instantaneous measurement.

Measured power is valuable for:

- confirming that a binary HLT actually turned off;
- detecting unexpected draw;
- learning/calibration;
- dashboard diagnostics;
- fault detection.

Measured power alone must not create permission to start another large load.

## Priority model

Proposed initial order:

```text
1. hard safety / ABORT / safe-down actions
2. BrewZilla high-priority process demand
3. BrewZilla normal process demand
4. HLT sparge-water heating
5. future non-critical opportunistic loads
```

Safety actions are not normal consumers. An OFF/safe-down action must never be blocked because the arbiter says a device has no power grant.

## Grant model

A grant should contain enough context for diagnostics and stale-lease prevention:

```text
grant_id
consumer_id
granted_power_w
grant_created_at
grant_expires_at
circuit_profile_id
reason
arbiter_generation
```

Consumers should renew active grants periodically. A stale grant after restart or coordinator failure must not remain implicit authority.

Exact TTL values belong to implementation/testing, not this architecture document.

## Starting the HLT

For a binary HLT:

```text
1. HLT publishes full rated-power demand.
2. Arbiter evaluates BrewZilla's current requested/reserved demand and circuit budget.
3. If full HLT demand fits with safety margin, arbiter grants the HLT lease.
4. HLT commands ON.
5. Optional power/readback confirms expected activation.
6. Grant remains valid only while the combined reservation remains safe.
```

If the full binary heater demand does not fit, the correct answer is `DENIED / WAITING_FOR_POWER`, not a partial grant that a binary switch cannot honor.

## BrewZilla reclaim handshake

This is the critical race-prevention mechanism.

Example situation:

```text
usable circuit budget: B
HLT currently active: H watts
BrewZilla currently granted/requesting: Z1 watts
Z1 + H <= B

BrewZilla now wants Z2 watts
Z2 + H > B
```

The arbiter must not simply give BrewZilla `Z2` while HLT is still physically on.

Required sequence:

```text
STATE: HLT_GRANTED

BrewZilla requests higher demand
  -> arbiter enters RECLAIMING_FOR_BREWZILLA
  -> revoke HLT grant
  -> command/notify HLT to stop
  -> temporarily keep BrewZilla allocation at a safe value

HLT OFF confirmed
  by trusted switch state, power readback, or conservative release delay

  -> mark HLT reservation released
  -> grant BrewZilla higher requested allocation
  -> return to normal allocation state
```

BrewZilla is still the priority consumer. The short sequencing delay exists only to avoid simultaneous unsafe draw.

## What BrewZilla should consume from the arbiter

The BrewZilla backend should conceptually calculate:

```text
desired_heat_utilization
  -> desired_brewzilla_power_w
  -> arbiter allocation
  -> allowed_heat_utilization_cap
  -> existing BrewZilla ownership/safety/physical write chain
```

The arbiter should not directly call `number.set_value` on BrewZilla heat utilization. Keeping the final physical write in the BrewZilla backend preserves its existing ownership, ABORT, Manual and supervised-control architecture.

A planned integration point can be expressed as:

```text
allowed_heat_utilization = min(desired_heat_utilization, electrical_cap)
```

During an HLT reclaim transition, `electrical_cap` remains at the last safe level until the HLT capacity has actually been released.

## What HLT should consume from the arbiter

The HLT backend gets a simpler binary result for an on/off heater:

```text
need_heat = true
AND valid power grant
AND HLT local safety permits
  -> heater may be ON

otherwise
  -> heater OFF
```

A future modulated HLT may consume a watt/percentage allocation directly, but the MVP should not invent variable control for binary hardware.

## Arbiter state model

Proposed states:

```text
IDLE
  no shared high-load grants

BZ_ONLY
  BrewZilla has allocation; HLT denied/not requesting

SHARED
  BrewZilla + HLT allocations fit concurrently

RECLAIMING_FOR_BZ
  HLT grant revoked; waiting for electrical release before raising BZ allocation

VERIFYING_HLT_START
  optional state while validating HLT activation/readback

DEGRADED
  accounting/readback inconsistency; no new opportunistic HLT grants

FAULT
  unsafe/inconsistent state requiring operator attention
```

The exact implementation may use data-driven grants rather than an enum, but the externally visible diagnostics should communicate equivalent semantics.

## Conservative degradation rules

### Unknown BrewZilla requested demand

Do not issue a new HLT grant if the arbiter cannot establish a conservative BrewZilla reservation during an active hot-side phase.

### HLT state/readback uncertain

Treat HLT watts as still reserved until OFF is confirmed or a conservative release policy has elapsed.

### Circuit sensor unavailable

If the core accounting is configuration/reservation-based, loss of an optional circuit wattmeter does not necessarily break existing safe allocations. It should, however, degrade diagnostics and may block new grants if that sensor was explicitly configured as required evidence.

### Arbiter restart

All leases are invalidated. Consumers reacquire permission.

The HLT must default to no positive authority. BrewZilla's separate fail-passive/local-controller behavior remains owned by the BrewZilla backend and must not be casually replaced by the arbiter.

## Interaction with Manual Brew ownership

Manual control creates an important case: an operator may choose BrewZilla utilization directly.

The architecture must still prevent the HLT from assuming watts that Manual Brew can consume without coordination.

Possible implementation rule:

```text
if BrewZilla heat channel is operator-owned:
  reserve configured/manual maximum or actual operator-requested utilization
  HLT only receives the residual conservative budget
```

The exact behavior should be designed alongside the existing Manual Brew ownership contract before direct HLT control is enabled.

The arbiter must never rewrite operator-owned BrewZilla channels merely to keep the HLT running. HLT is the load that yields.

## Interaction with supervised apply

Electrical allocation and permission to perform a positive device write are separate concepts.

```text
power grant
  means the circuit can safely support the action

authority/confirmation
  means BrewAssistant is allowed to perform the action
```

Both conditions are required where the consumer's control policy demands confirmation.

The arbiter must not turn a guidance-only or monitor-only module into direct control simply because power is available.

## Proposed diagnostics/entities

Names are provisional.

```text
sensor.brewassistant_power_budget_state
sensor.brewassistant_power_budget_usable_w
sensor.brewassistant_power_budget_reserved_w
sensor.brewassistant_power_budget_available_w
sensor.brewassistant_power_budget_margin_w
sensor.brewassistant_power_budget_brewzilla_request_w
sensor.brewassistant_power_budget_brewzilla_grant_w
sensor.brewassistant_power_budget_hlt_request_w
sensor.brewassistant_power_budget_hlt_grant_w
sensor.brewassistant_power_budget_reason
binary_sensor.brewassistant_power_budget_degraded
binary_sensor.brewassistant_power_budget_fault
```

Useful attributes:

```text
active grants
lease ids/ages
circuit profile
consumer priorities
release verification state
last reclaim reason
last denied request
observed vs reserved power
```

## Flight Recorder events

Proposed events:

```text
power_budget_request
power_budget_grant
power_budget_deny
power_budget_revoke
power_budget_reclaim_started
power_budget_consumer_released
power_budget_reclaim_completed
power_budget_degraded
power_budget_fault
```

Every event should include enough data to answer:

```text
Who asked for watts?
How many?
What was the usable circuit budget?
What other reservation existed?
Why was it granted/denied/revoked?
Was the physical release confirmed before reallocation?
```

## Example sequence: mash heating HLT opportunistically

```text
BrewZilla desired = 700 W
HLT demand       = 1800 W
usable budget    = 3300 W

700 + 1800 <= 3300
  -> BZ grant 700 W
  -> HLT grant 1800 W
  -> SHARED
```

Later:

```text
BrewZilla desired rises to 2200 W
HLT remains 1800 W
usable budget 3300 W

2200 + 1800 > 3300
  -> revoke HLT
  -> wait HLT OFF / release confirmation
  -> grant BrewZilla 2200 W
```

The numbers above are examples only and must not become defaults.

## Example sequence: HLT cannot fit

```text
BrewZilla desired = 1700 W
HLT binary demand = 1800 W
usable budget     = 3300 W

1700 + 1800 > 3300
  -> HLT denied
  -> BrewZilla unaffected
  -> HLT state WAITING_FOR_POWER
```

This is preferable to repeatedly toggling BrewZilla down just to satisfy HLT. BrewZilla process demand has priority.

## Optional future scheduling intelligence

Once safe arbitration is proven, HLT heating can become smarter without changing the electrical contract.

Examples:

- estimate energy required from water volume and delta-T;
- learn effective HLT heating rate;
- calculate latest safe start time before sparge;
- exploit longer low-power mash intervals first;
- minimize unnecessary target holding losses.

This intelligence belongs in the HLT backend. The arbiter should continue to answer only whether requested power may be used now.

## MVP implementation order

### PBA-0 — commissioning data

- shared protected circuit confirmed;
- usable watt budget configured;
- BrewZilla rated/maximum heater power documented;
- HLT rated power documented;
- safety margin selected;
- optional power sensors identified.

### PBA-1 — observe only

- calculate requests/reservations/grants as diagnostics;
- no physical constraints or HLT control;
- Flight Recorder comparison against real BrewZilla power behavior.

### PBA-2 — HLT grant simulation

- show when a binary HLT would have been allowed;
- simulate reclaim transitions;
- verify no calculated overlap exceeds budget.

### PBA-3 — supervised HLT grant

- HLT requires actual grant to turn on;
- reclaim handshake enforced;
- BrewZilla allocation integration added at the existing orchestration boundary;
- field-test under controlled conditions.

### PBA-4 — direct operation

- enable direct HLT control only after observed/simulated accounting and supervised reclaim are proven.

## Acceptance criteria

1. The sum of active granted/reserved controllable loads never exceeds configured usable budget.
2. A binary load is granted either its full reserved watts or zero.
3. Low instantaneous measured wattage alone never authorizes a new large load.
4. BrewZilla can reclaim capacity from HLT without a transient simultaneous over-allocation.
5. Reallocation waits for HLT electrical release evidence or a conservative release policy.
6. BrewZilla process/Manual/safety logic remains owned by the BrewZilla backend.
7. HLT always yields before the arbiter sacrifices BrewZilla process demand merely to keep HLT active.
8. ABORT/OFF/safe-down actions are never blocked by grant accounting.
9. All leases are invalid after arbiter restart and must be reacquired.
10. Flight Recorder can reconstruct every important allocation/reclaim decision.

## Do not implement as

Avoid these shortcuts:

```text
if sensor.brewzilla_power < X: turn_on(hlt)

if number.brewzilla_heat_utilization < 50%: turn_on(hlt)

turn_on(hlt); if total_power_too_high: turn_off(hlt)
```

All three react after the fact or depend on a snapshot that another controller can invalidate immediately.

The intended architecture is proactive reservation + coordinated handoff.
