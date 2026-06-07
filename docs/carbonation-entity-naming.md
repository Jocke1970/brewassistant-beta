# Carbonation entity naming

BrewAssistant carbonation runtime currently exposes existing Home Assistant control entities without the `_control` suffix in Joachim's installation:

- `select.brewassistant_carbonation_method`
- `number.brewassistant_carbonation_target_volumes`
- `number.brewassistant_carbonation_start_volumes`
- `number.brewassistant_carbonation_pressure_bar`

The backend suggested object IDs should align with these stable entity IDs while keeping the internal unique IDs/keys unchanged.
