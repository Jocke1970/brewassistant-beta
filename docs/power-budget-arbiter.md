# Shared Power Budget Arbiter — planning specification

Status: planned / simulation-first architecture  
Planning baseline: 2026-09-15

The Power Budget Arbiter is BrewAssistant's planned coordination layer for controllable electrical loads that share a constrained circuit. Its first use case is BrewZilla + HLT.

The first implementation target is **full dry-run simulation**, not a passive monitor-only layer. The arbiter should execute the real grant/deny/revoke/reclaim algorithm against real BrewZilla/Brewday inputs and a virtual HLT, while suppressing any physical BrewZilla cap or HLT heater write.

## Core principle

```text
Consumers publish requested electrical demand.
The arbiter grants bounded capacity.
A secondary load must release capacity before the primary load reclaims it.
Measured low wattage alone never creates permission.
```

BrewZilla is the primary brewing load. HLT is opportunistic and preemptible.

## Ownership boundary

```text
BrewZilla backend
  computes desired BrewZilla heat utilization / demand
  owns final physical BZ writes

HLT backend
  decides whether sparge water needs heat
  owns virtual/real HLT state and heater demand

Power Budget Arbiter
  owns reservations, grants, revocations and reclaim ordering

Brewday Runtime
  provides normalized process context
```

The arbiter must not become a second BrewZilla controller.

## Simulation rule

During simulation:

```text
real BrewZilla demand/state -> arbiter input
virtual HLT demand          -> arbiter input
arbiter decisions           -> executed logically
HLT heater action           -> virtual only
BZ cap/reclaim result        -> WOULD_* diagnostics only
physical BrewZilla writes   -> unchanged
```

This lets the full safety logic be analyzed without HLT hardware and without interfering with a live BrewZilla brew.

## Circuit model

Proposed profile:

```text
profile_id
circuit_limit_w
safety_margin_w
usable_budget_w = circuit_limit_w - safety_margin_w
optional observed circuit power
```

No voltage, breaker size or country-specific assumption should be hard-coded.

## Consumer model

Each consumer exposes:

```text
consumer_id
mode: binary | variable
rated_power_w
requested_power_w
minimum_useful_power_w
priority
preemptible
release_delay/readback policy
request_reason
request_timestamp
```

Initial consumers:

```text
BrewZilla
  mode = variable
  priority = primary_hot_side

HLT
  mode = binary
  priority = secondary_hot_side
  preemptible = true
```

The BrewZilla heat-utilization-to-watts mapping must be calibrated or conservatively configured rather than treated as an exact wattmeter.

## Reservation vs observation

The arbiter distinguishes:

```text
requested/reserved power
  what a consumer may draw

observed power
  what sensors currently report
```

Safety decisions use conservative reservations. Observed watts are useful for calibration, verification and later physical release confirmation.

A low observed BrewZilla wattage is never by itself permission to energize HLT.

## Priority

Initial order:

```text
1. ABORT / OFF / risk-reducing actions
2. BrewZilla process demand
3. HLT heating
4. future opportunistic loads
```

HLT yields before BrewZilla process demand is sacrificed merely to keep HLT running.

## Grant model

A logical grant should include:

```text
grant_id
consumer_id
granted_power_w
created_at
expires_at
circuit_profile_id
reason
arbiter_generation
```

Restart invalidates all grants.

## Starting virtual HLT

For a binary HLT:

```text
1. HLT requests full rated heater watts.
2. Arbiter evaluates BZ reservation + HLT demand against usable budget.
3. If it fits, HLT receives full grant.
4. Virtual heater becomes ON.
5. Virtual thermal model integrates granted energy.
6. If it does not fit, HLT receives zero and waits.
```

There is no partial grant for a binary heater.

## BrewZilla reclaim handshake

Suppose:

```text
usable budget = B
HLT active     = H
BZ current     = Z1
BZ wants       = Z2

Z1 + H <= B
Z2 + H > B
```

The required logical sequence is:

```text
SHARED
  -> BZ higher request detected
  -> RECLAIMING_FOR_BZ
  -> revoke HLT grant
  -> HLT -> YIELDING
  -> virtual heater OFF
  -> wait configured virtual release delay
  -> release HLT reservation
  -> calculate higher BZ grant
  -> BZ_ONLY
```

During simulation the new BZ grant is recorded as `would_grant_w` / `would_cap_utilization`; it is **not physically applied**.

This is how we test the race-prevention mechanism safely.

## Arbiter state model

```text
IDLE
BZ_ONLY
SHARED
RECLAIMING_FOR_BZ
VERIFYING_HLT_START
DEGRADED
FAULT
```

An implementation may internally be data-driven, but equivalent diagnostics must be visible.

## BrewZilla outputs in simulation

Proposed values:

```text
bz_requested_w
bz_current_assumed_reservation_w
bz_would_grant_w
bz_would_cap_utilization_pct
bz_reclaim_pending
bz_reclaim_reason
```

These values must not feed physical BrewZilla writes while simulation mode is active.

## HLT outputs in simulation

```text
hlt_requested_w
hlt_granted_w
hlt_virtual_heater_on
hlt_release_pending
hlt_wait_reason
```

These feed the virtual HLT thermal model only.

## Degradation rules

### Unknown BZ demand

During an active hot-side phase, unknown/conservatively unbounded BrewZilla demand blocks a **new** HLT grant.

### HLT release uncertainty

Treat HLT watts as reserved until simulated/physical release confirmation completes.

### Restart

Invalidate grants and generation IDs. Virtual state may be restored only as process context; old leases do not survive.

### Manual Brew

If the BZ heat channel is operator-owned, reserve conservatively from the known/requested operator setting or a configured maximum. HLT receives only safe residual capacity.

The arbiter never rewrites operator-owned BZ settings to preserve HLT operation.

## Flight Recorder events

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

Simulation events must include:

```text
brewday stage
usable budget
BZ requested / would-grant watts
HLT requested / granted watts
active reservations
virtual HLT state/temp
reason
lease/reclaim identifiers
```

## Example

```text
usable budget = 3300 W
BZ request    = 700 W
HLT demand    = 1800 W

700 + 1800 <= 3300
  -> BZ would_grant 700 W
  -> HLT grant 1800 W
  -> SHARED
```

Later:

```text
BZ request rises to 2200 W
HLT still reserves 1800 W

2200 + 1800 > 3300
  -> revoke HLT
  -> virtual HLT OFF
  -> wait release delay
  -> release 1800 W
  -> BZ would_grant 2200 W
```

Numbers are examples only.

## Simulation development order

### SIM-0 — inputs

- usable circuit budget;
- safety margin;
- BrewZilla maximum/rated heater power;
- BZ utilization-to-watts mapping;
- virtual HLT rated watts;
- virtual release delay.

### SIM-1 — full arbiter logic

- request/grant/deny;
- lease lifetime;
- full binary HLT reservation;
- SHARED state;
- revoke/yield/release/reclaim;
- `would_cap` BZ calculations;
- no physical writes.

### SIM-2 — automated scenarios

Test at minimum:

```text
HLT fits during mash
HLT does not fit
BZ sudden ramp while HLT active
multiple BZ demand changes during HLT release delay
unknown/stale BZ demand
lease expiry
restart generation change
Manual Brew heat ownership
no-sparge
```

Invariant checks should run on every step:

```text
sum(granted reservations) <= usable_budget_w
binary HLT grant in {0, rated_power_w}
BZ reclaim cannot consume HLT-reserved watts before release
simulation cannot call physical HLT/BZ write services
```

### SIM-3 — live/replay brew analysis

Run against real BrewZilla traces to answer:

- how long are useful power windows during mash?;
- how often would HLT be preempted?;
- how much energy can HLT accumulate before sparge?;
- what safety margin causes unnecessary missed opportunities?;
- does predictive latest-start scheduling improve behavior?

### HW-1 — future physical binding

Only after the simulation invariants and brew-trace behavior are convincing should real HLT writes and real BrewZilla electrical caps be connected.

## Acceptance criteria before physical arbitration

1. Full grant/revoke/reclaim logic executes in simulation.
2. Simulation never calls physical HLT or BrewZilla control services.
3. Sum of simulated grants never exceeds usable budget.
4. Binary HLT receives full rated watts or zero.
5. Low instantaneous measured BZ wattage alone never authorizes HLT.
6. BZ reclaim waits for HLT release.
7. Restart invalidates grants.
8. Manual ownership is represented conservatively.
9. Flight Recorder reconstructs every decision.
10. Virtual HLT thermal results can be correlated with the available BZ power windows.

## Do not implement as

```text
if sensor.brewzilla_power < X: HLT_ON
if brewzilla_heat_utilization < Y: HLT_ON
HLT_ON then turn it off if total power becomes too high
```

The intended architecture is proactive reservation and coordinated handoff, fully exercisable in simulation before hardware exists.
