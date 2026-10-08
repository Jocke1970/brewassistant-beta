# Fermentation equipment/provider selection

Status: **Phase 1–3 backend and provider-aware reusable dashboard cards implemented on `dev`; outbound provider-aware telemetry remains pending**  
Created: 2026-10-08  
Scope: `fermentation_tracking`, `fermentation_chamber`, `grainfather_fermenter`, fermentation UI and outbound fermentation telemetry.

## Decision

BrewAssistant must treat **fermentation strategy** and **fermentation equipment** as two independent choices.

They answer different questions:

```text
Fermentation strategy
  -> How does BrewAssistant decide the desired beer-temperature target?
     - recipe_schedule
     - sg_control

Fermentation equipment / provider
  -> Which physical fermentation system receives/implements that target?
     - fermentation_chamber
     - grainfather_gf30
```

The UI must not call the second choice "fermentation method" because that would collide semantically with SG-vs-day control. Preferred Swedish label:

```text
Jäsutrustning
```

Preferred internal concept:

```text
fermentation_provider
```

## Planned provider IDs

Use stable machine-readable IDs:

```text
fermentation_chamber
grainfather_gf30
```

Planned Home Assistant control surface:

```text
select.brewassistant_fermentation_provider
```

Suggested UI labels:

```text
Temperaturkontrollerat jässkåp
Grainfather GF30
```

The exact entity ID may be adjusted during implementation if a migration or naming conflict requires it, but the provider IDs above are the architecture contract.

## Persistence and scope

Provider selection belongs to the **active fermentation session/batch**, not to a temporary dashboard-only global.

Persist at minimum:

```text
batch/session identity
selected fermentation_provider
selected fermentation strategy/mode
provider selection timestamp
operator/source that changed the selection
```

Backward-compatible migration:

- an existing fermentation session with no stored provider must default to `fermentation_chamber`;
- GF30 must be explicit opt-in;
- migration must not silently enable any new GF30 write path;
- changing provider during an active batch requires explicit operator action and must not reset SG-stage latches, recipe schedule position or cold-crash readiness.

### Pre-start selection behavior

The operator may select jäsutrustning before starting a new fermentation session. If the current runtime is inactive and contains an explicit provider choice, `fermentation_start` preserves that choice when the start payload does not contain its own provider. A still-active previous session is never inherited implicitly. An explicit provider in the start payload always wins.

This prevents the UI sequence `select GF30 → start fermentation` from silently reverting to the chamber default.

## Ownership boundary

`fermentation_tracking` owns the **process**:

- observations;
- SG/day mode;
- fermentation progression;
- desired beer-temperature target;
- stability/readiness;
- cold-crash readiness/proposal.

The selected provider owns only the **physical adaptation** of that target.

```text
                       fermentation_tracking
                               |
                  desired beer temperature
                               |
                    fermentation_provider
                    /                    \
                   /                      \
      fermentation_chamber          grainfather_gf30
            |                              |
     chamber-air adapter             GF30 target adapter
            |                              |
 climate.fermentation_chamber      Grainfather controller
```

A provider selection must never change how `recipe_schedule` or `sg_control` determines the process target.

## Exclusive provider rule

Only the selected provider may:

- create a pending supervised temperature-target action;
- expose itself as the active physical target owner;
- participate in provider-specific apply/readback state;
- present provider-specific control buttons in the active fermentation UI.

The non-selected provider remains observable where useful for diagnostics, but it must be **control-ineligible** for that batch.

No "both" mode in the first implementation.

If provider identity is missing, invalid or ambiguous:

```text
provider_control_allowed = false
provider_status = selection_required / invalid_selection
```

Never fan one fermentation target out to both chamber and GF30.

## Common normalized provider contract

The fermentation UI and outbound consumers should not need to know the physical implementation for basic status.

Expose a normalized provider snapshot with concepts such as:

```text
provider_id
provider_label
provider_selected
provider_ready
provider_status
beer_temperature_c
beer_temperature_source
beer_temperature_age_s
desired_beer_target_c
physical_target_c
physical_target_source
target_delta_c
heating_state
cooling_state
temperature_control_state
supervised_apply_state
safe_to_propose_target
reason
```

Values that do not exist for a provider remain `unknown`/absent; do not invent synthetic hardware states.

Provider-specific diagnostics remain available under their own backend sensors/attributes.

## Fermentation chamber provider

When `fermentation_provider = fermentation_chamber`:

### Primary UI data

Show the existing chamber-relevant surface, including:

- selected strategy/mode;
- active process target from `fermentation_tracking`;
- normalized beer/liquid temperature;
- chamber air temperature;
- effective chamber-air recommendation;
- air/liquid delta;
- climate demand/mode;
- current `climate.fermentation_chamber` target;
- heat/cool status when verified;
- heat-mat/fan/compressor diagnostics where available;
- generic Supervised Apply state;
- cold-crash readiness/confirmation state.

### Control path

```text
fermentation_tracking
  -> fermentation_chamber recommendation
  -> pending generic Supervised Apply
  -> climate.fermentation_chamber
```

The existing chamber clamps and readiness rules remain authoritative.

GF30 target proposal/apply controls must be hidden/disabled for the active batch.

## Grainfather GF30 provider

When `fermentation_provider = grainfather_gf30`:

### Primary UI data

Show the GF30-relevant surface, including:

- selected strategy/mode;
- active process target from `fermentation_tracking`;
- RAPT Pill temperature;
- GF30 internal/controller temperature;
- Pill ↔ GF30 delta;
- dual-sensor/safe-point status;
- Grainfather controller target and target readback;
- GF30 cooling-command/state;
- supervised GF30 target proposal/apply/readback state;
- coolant temperature;
- freezer-air temperature;
- coolant `generic_thermostat` target/state;
- passive thermal-learning rate/confidence where available;
- cold-crash readiness/confirmation state.

### Pump boundary

GF30 owns its local cooling-pump logic.

```text
GF30 cooling state
  -> cooling commanded / pump expected active

physical coolant flow
  -> not proven unless separately measured
```

BrewAssistant must not add a parallel GF30 pump-control path.

### Coolant/freezer boundary

The DIY coolant loop remains separate:

```text
generic_thermostat
  -> owns freezer ON/OFF
  -> regulates coolant/reservoir temperature
```

BrewAssistant may observe it and may later propose a supervised coolant-target change within physically validated bounds. It must not directly switch the freezer.

The current GF30 supervised controller-target adapter remains the only allowed GF30 actuator path unless the architecture is explicitly extended and field-validated.

## Conditional UI contract

The fermentation dashboard must be provider-aware.

Do **not** build one giant card where half the rows show `Unavailable`.

Recommended structure:

```text
Common fermentation header
  - batch/recipe
  - fermentation strategy
  - fermentation provider
  - SG
  - current process target
  - stage/progress/readiness

Conditional provider body
  if fermentation_chamber:
      chamber card/body
  if grainfather_gf30:
      GF30 card/body

Common footer
  - cold-crash readiness
  - warnings/holds
  - outbound Brewfather logging status
```

### Chamber body

Hide GF30-only values such as:

- GF30 internal temperature;
- GF30 controller target;
- GF30 safe-point;
- Grainfather cooling command;
- coolant/freezer learning widgets.

### GF30 body

Hide chamber-only values such as:

- chamber-air recommendation;
- chamber climate target;
- chamber fan/heat-mat controls;
- chamber-specific air/liquid compensation.

Provider-specific values may still exist as backend entities for diagnostics/history. The dashboard condition controls presentation, not entity existence.

## Provider selector behavior

Changing `fermentation_provider` during an active fermentation must be treated as a significant operator action.

Implemented change boundary:

1. changing the provider through the selector is itself an explicit operator action;
2. any provider-owned pending supervised action from the old provider is cleared immediately;
3. the fermentation strategy, SG stage latch and process target are not changed;
4. the new provider starts from its live readiness/monitor state;
5. no physical target is replayed automatically;
6. a fresh provider-specific Supervised Apply proposal/confirmation is still required before a physical write can occur.

The dashboard may later add an extra confirmation dialog for UX clarity, but safety does not depend on that presentation layer.

Do not replay an old pending target action into the new provider.

Provider switching must be fail-passive:

```text
old provider -> control ineligible
new provider -> monitor/readiness first
new provider -> supervised action only after fresh proposal + confirmation
```

## Relationship to SG/day selection

The two dimensions form four valid combinations:

| Strategy | Provider | Valid |
| --- | --- | --- |
| `recipe_schedule` | `fermentation_chamber` | yes |
| `recipe_schedule` | `grainfather_gf30` | yes |
| `sg_control` | `fermentation_chamber` | yes, after SG runtime is implemented |
| `sg_control` | `grainfather_gf30` | yes, after SG runtime is implemented |

There must be no special SG algorithm for GF30 and no special recipe-schedule algorithm for the chamber. Both providers consume the same normalized desired beer target.

## Brewfather Custom Stream relationship

Outbound Brewfather fermentation logging should follow the selected provider through a normalized telemetry contract rather than hard-coded hardware entity IDs.

Common intended mapping:

```text
temp           = normalized beer temperature
gravity        = normalized fermentation SG
temp_target    = active BrewAssistant process target
gravity_target = expected FG when known
```

Provider-specific optional mapping:

```text
fermentation_chamber:
  aux_temp = chamber/fridge temperature if semantically appropriate

grainfather_gf30:
  aux_temp = coolant/reservoir temperature if deliberately configured
```

GF30 internal beer temperature must not be mislabeled as Brewfather `aux_temp`/Fridge Temp merely to expose a second beer-temperature channel.

The Brewfather integration remains the owner of logging ID, POST/rate limit and Custom Stream transport. BrewAssistant supplies normalized telemetry/provider context.

## Failure and stale-data behavior

Provider selection does not weaken source/freshness checks.

If the selected provider loses required telemetry:

- hold the last confirmed process target;
- block new provider-specific physical proposals when readiness is not satisfied;
- show the specific stale/missing source;
- do not silently switch to the other provider;
- do not silently switch fermentation strategy;
- do not start cold crash.

The unselected provider must never become an automatic fallback controller.

## Implementation plan for next development session

### Phase 1 — runtime/provider selection — IMPLEMENTED ON `dev`

1. Stable provider constants/model implemented.
2. Provider is persisted in the fermentation runtime.
3. `select.brewassistant_fermentation_provider` implemented with human-readable options and stable provider IDs in runtime/attributes.
4. Existing stored sessions with no provider migrate fail-passive to `fermentation_chamber`.
5. Tracking snapshot and `sensor.brewassistant_fermentation_provider` expose the selected provider.

### Phase 2 — arbitration — IMPLEMENTED ON `dev`

6. Chamber supervised proposals are gated on `fermentation_chamber`.
7. GF30 proposal **and confirmed execution** are gated on `grainfather_gf30`.
8. Provider switch/start/reset clears provider-owned stale pending actions.
9. Regression contract covers persistence, selector mapping and exclusive arbitration.

### Phase 3 — normalized provider snapshot — IMPLEMENTED READ-ONLY ON `dev`

10. Common provider-status snapshot implemented.
11. Chamber is normalized from already-published HA supervisor state.
12. GF30 is normalized from already-published target-adapter state.
13. The common snapshot exposes provider status/readiness, process target, physical target/delta and supervised state without creating pending actions as a sensor-read side effect.

### Phase 4 — UI — IMPLEMENTED AS REUSABLE CARDS ON `dev`

14. `fermentation_provider*.yaml` provides the common Jäsutrustning selector/status header.
15. Existing chamber and GF30 cards are provider-conditional bodies.
16. Chamber controls are hidden for GF30; GF30 controls are hidden for chamber.
17. Common process status remains available through the provider/tracking surfaces.

Dashboard routing uses `sensor.brewassistant_fermentation_provider` machine IDs rather than translated select labels. The cards remain standalone reusable building blocks according to the dashboard composition policy.

### Phase 5 — outbound telemetry

18. Make Brewfather Custom Stream consume normalized fermentation telemetry/provider context.
19. Verify provider switch does not produce semantically incorrect `aux_temp` data.
20. Add end-to-end tests for both providers × both strategy modes.

## Acceptance tests

Minimum before promotion:

- existing session migration selects chamber without activating new control;
- new batch can explicitly select chamber or GF30;
- strategy change does not change provider;
- provider change does not change strategy;
- chamber selected -> GF30 cannot create/execute provider target action;
- GF30 selected -> chamber cannot create/execute provider target action;
- provider change clears old provider-owned pending action;
- restart preserves provider;
- stale selected-provider telemetry fails passive;
- no automatic fallback to the other provider;
- cold crash remains separately confirmed;
- UI renders only the selected provider body;
- Brewfather logging uses normalized common values and semantically correct optional provider temperature.

## Do not change casually

1. Fermentation strategy and fermentation equipment are independent dimensions.
2. `fermentation_tracking` owns the process target; providers only adapt it to hardware.
3. Exactly one provider is control-eligible per fermentation session.
4. The non-selected provider is never an automatic fallback controller.
5. Provider switching cannot replay stale pending actions.
6. GF30 owns its pump; coolant `generic_thermostat` owns freezer ON/OFF.
7. Conditional UI must reflect the selected provider rather than expose unrelated unavailable controls.
8. Brewfather Custom Stream must preserve field semantics and must not mislabel GF30 internal beer temperature as Fridge Temp.
