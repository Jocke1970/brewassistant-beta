# Dashboard baselines

This document summarizes the current BrewAssistant dashboard baseline.

Dashboard YAML is a presentation and operator-action layer. Runtime interpretation, calculations, safety guards, BrewZilla orchestration and session state belong in the Python custom integration.

---

## Current baseline directories

```text
dashboard/
  brewassistant_sanity.yaml
  cards/
```

`dashboard/brewassistant_sanity.yaml` is a compact post-update smoke-test dashboard.

`dashboard/cards/` contains reusable card snippets for the daily dashboard.

The old plural `dashboards/` directory is not the current source of truth. Use singular `dashboard/`.

---

## Current reusable cards

```text
dashboard/cards/brewassistant_hub.yaml
dashboard/cards/brewassistant_visibility_badges.yaml
dashboard/cards/brewassistant_brewday.yaml
dashboard/cards/brewassistant_brewday_bf_reload.yaml
dashboard/cards/brewassistant_brewday_event_log.yaml
dashboard/cards/brewassistant_manual_brewday.yaml
dashboard/cards/brewassistant_source_health.yaml
dashboard/cards/brewfather_feed.yaml
dashboard/cards/brewfather_recipe.yaml
dashboard/cards/brewtracker_runtime.yaml
dashboard/cards/brewzilla.yaml
dashboard/cards/brewzilla_mash_in_confirm.yaml
dashboard/cards/brewzilla_local_control.yaml
dashboard/cards/brewzilla_advice_auto.yaml
dashboard/cards/brewzilla_safety_rcl.yaml
dashboard/cards/brewzilla_learning.yaml
dashboard/cards/counterflow_chiller.yaml
dashboard/cards/carbonation.yaml
dashboard/cards/fermentation.yaml
dashboard/cards/kegerator.yaml
```

---

## BrewAssistant Hub

File: `dashboard/cards/brewassistant_hub.yaml`

Purpose: provide a compact mission-control overview above the domain cards.

Current policy:

```text
- Show the major BrewAssistant domains in one compact overview.
- Show source/feed status as supporting status, not as a fifth primary workflow.
- Keep inactive/disconnected modules visually calm.
- Prioritize active cooling, active fermentation/cold-crash, active brewday and carbonation-ready states.
```

---

## Brewday Runtime

File: `dashboard/cards/brewassistant_brewday.yaml`

Purpose: operator-facing normalized runtime card for Brewfather-driven and manual brewday state.

Current policy:

```text
- Show normalized BrewAssistant runtime state, not raw Brewfather internals by default.
- Brewfather/BrewTracker and Manual Brewday should feed the same operator mental model.
- Keep direct hardware actions explicit and supervised.
- Debug/source details belong in expanders or source health cards.
```

---

## BrewTracker Runtime

File: `dashboard/cards/brewtracker_runtime.yaml`

Purpose: show BrewTracker live state, current/next step, stage, progress, refresh and batch status.

Current policy:

```text
- Include brew_tracker_batch_status when available.
- Keep batch status visible separately from paused/running tracker state.
- Use this card for Brewfather/BrewTracker source visibility, not hidden backend logic.
```

---

## Brewday Event Log

File: `dashboard/cards/brewassistant_brewday_event_log.yaml`

Purpose: show event-log state, latest event information and explicit audit/log actions.

Current policy:

```text
- UI wording should say Event Log.
- Backend service names may still use brewday_audit_* for compatibility.
- Event count, latest event, latest step and latest target should be visible quickly.
- Clear/reset actions should require confirmation.
```

---

## BrewZilla operator baseline

Main files:

```text
dashboard/cards/brewzilla.yaml
dashboard/cards/brewzilla_mash_in_confirm.yaml
dashboard/cards/brewzilla_local_control.yaml
dashboard/cards/brewzilla_advice_auto.yaml
dashboard/cards/brewzilla_safety_rcl.yaml
dashboard/cards/brewzilla_learning.yaml
```

Purpose:

```text
BrewZilla = operator/hardware cockpit
BrewZilla Mash-In Confirm = explicit mash-in completion and circulation action
BrewZilla Local Control = what BA handed to BZ and whether lease is active
Brewday Advice = why BA selected a profile; hidden by default unless meaningful
Safety/RCL = freshness/guards/filter/abort; hidden by default unless meaningful
BrewZilla Learning = full advisory/recommendation review
```

---

## BrewZilla mash-in operator baseline

`dashboard/cards/brewzilla_mash_in_confirm.yaml` is the current beta.7 mash-in operator card.

It depends on:

```text
binary_sensor.brewassistant_brewzilla_mash_in_gate_pending
button.brewassistant_brewzilla_mash_in_complete
button.brewassistant_brewzilla_start_mash_circulation
```

Expected behavior:

```text
1. Mash-in target is reached.
2. BrewAssistant sets mash-in gate pending on.
3. The conditional Mash-in button appears.
4. Operator mashes in manually.
5. Operator presses Mash-in klar & starta cirkulation.
6. BrewAssistant confirms the gate and starts circulation using pump utilization plus pump switch.
```

The fallback `Starta mäskcirkulation` button is a visible operator action for starting mash circulation. It should stay explicit and observable.

---

## Button-action policy

Dashboard action cards should use BrewAssistant button entities for operator actions:

```text
button.press → button.brewassistant_*
```

Do not create parallel workaround services for the same physical action. A single backend action path makes event logging, safety review and future cleanup easier.

---

## Visibility policy

Daily dashboard sections can be hidden or shown with BrewAssistant visibility switches such as:

```text
switch.brewassistant_show_brewday
switch.brewassistant_show_brewzilla
switch.brewassistant_show_brewzilla_learning
switch.brewassistant_show_event_log
switch.brewassistant_show_source_health
switch.brewassistant_show_fermentation
switch.brewassistant_show_carbonation
switch.brewassistant_show_kegerator
```

Diagnostic cards may also auto-show when risk, warning, missing context, guard activity or pending operator action is present.

---

## Frontend dependencies

Install these Lovelace frontend cards through HACS before copying the dashboard examples:

```text
custom:button-card
custom:vertical-stack-in-card
custom:mushroom-*
custom:expander-card
custom:gauge-card-pro
custom:bar-card
custom:apexcharts-card
```
