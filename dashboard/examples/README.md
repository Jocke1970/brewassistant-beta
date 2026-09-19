# BrewAssistant dashboard composition examples

BrewAssistant does not require one monolithic Brewday card. The files in `dashboard/cards/` are reusable building blocks that can be copied into a Home Assistant dashboard and arranged to suit the installation.

## RAPT Profile example

A compact RAPT-based Brewday view can be assembled from:

```text
cards/brewassistant_brewday.yaml
cards/rapt_profile_runtime.yaml
cards/brewzilla_mash_in_controls.yaml
cards/brewday_physical_timing.yaml
cards/brewday_operator_actions.yaml
cards/brewday_details.yaml
```

Use the matching `_sv.yaml` files for Swedish presentation.

## Brewfather / BrewTracker example

A BrewTracker-based view can use:

```text
cards/brewassistant_brewday.yaml
cards/brewtracker_runtime.yaml
cards/brewzilla_mash_in_controls.yaml
cards/brewday_physical_timing.yaml
cards/brewday_operator_actions.yaml
cards/brewday_details.yaml
```

Optional cards such as `brewassistant_brewday_runtime_flow`, `brewassistant_brewday_event_log`, BrewZilla hardware/control cards, Brewing Advice and Safety/RCL can be placed wherever they make sense for the user's dashboard.

## Rule

A personal vertical stack may combine these cards, but the combined stack is only a layout choice. General functionality must remain available in the standalone cards and must not depend on a private dashboard composition.
