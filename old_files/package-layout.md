# BrewAssistant – Package Layout

## Recommended Home Assistant Package Files

```text
/config/packages/brewassistant_helpers.yaml
/config/packages/brewassistant_runtime.yaml
/config/packages/brewassistant_workflow.yaml
/config/packages/brewassistant_notifications.yaml
/config/packages/brewassistant_chamber.yaml
/config/packages/brewassistant_smart_automation_v2.yaml
```

## Recommended Dashboard Files

```text
/config/dashboards/brewassistant_main_card_dark_v1.yaml
/config/dashboards/brewassistant_chamber_card_v1_2_semiauto.yaml
/config/dashboards/brewassistant_kegerator_card_v1_1_premium.yaml
```

## Suggested GitHub Structure

```text
brewassistant/
├── README.md
├── docs/
│   ├── structure.md
│   ├── roadmap.md
│   ├── state-machine.md
│   ├── integration-strategy.md
│   ├── entity-map.md
│   ├── ui-spec.md
│   └── package-layout.md
├── packages/
│   ├── brewassistant_helpers.yaml
│   ├── brewassistant_runtime.yaml
│   ├── brewassistant_workflow.yaml
│   ├── brewassistant_notifications.yaml
│   ├── brewassistant_chamber.yaml
│   └── brewassistant_smart_automation_v2.yaml
├── dashboards/
│   ├── brewassistant_main_card_dark_v1.yaml
│   ├── brewassistant_chamber_card_v1_2_semiauto.yaml
│   └── brewassistant_kegerator_card_v1_1_premium.yaml
└── assets/
    └── screenshots/
```

## Notes

The current setup is still customized to one installation. Future work should separate:

- generic template package
- local entity mapping
- example configuration
