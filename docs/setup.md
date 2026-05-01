# Setup

This guide describes a recommended BrewAssistant v4 installation in Home Assistant.

---

## 1. Enable Home Assistant packages

In `configuration.yaml`, make sure packages are enabled:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Create the folder if it does not already exist:

```text
/config/packages/
```

---

## 2. Copy package files

Copy the BrewAssistant package files into `/config/packages/`.

Recommended core files:

```text
/config/packages/brewassistant_helpers.yaml
/config/packages/brewassistant_runtime.yaml
/config/packages/brewassistant_workflow.yaml
/config/packages/brewassistant_chamber.yaml
/config/packages/brewassistant_notifications.yaml
/config/packages/brewassistant_manual_mode.yaml
```

Optional/future files:

```text
/config/packages/brewassistant_hot_side_workflow.yaml
/config/packages/brewassistant_brewzilla.yaml
/config/packages/brewassistant_shopper.yaml
```

---

## 3. Restart Home Assistant

After adding or changing package files:

1. Check configuration.
2. Restart Home Assistant.
3. Confirm that helpers and template sensors are created.

---

## 4. Add dashboard cards

Dashboard YAML should be kept separately from backend package logic.

Recommended folder:

```text
/dashboards/
```

Suggested dashboard files:

```text
dashboards/fermentation.yaml
dashboards/manual-mode.yaml
dashboards/chamber.yaml
dashboards/kegerator.yaml
dashboards/brewzilla.yaml
```

Cards may use custom Lovelace cards such as:

- `custom:button-card`
- `custom:mushroom-*`
- `custom:vertical-stack-in-card`
- `custom:stack-in-card`
- `custom:bar-card`
- `custom:apexcharts-card`
- `custom:expander-card`

Install required cards through HACS before using the dashboards.

---

## 5. Recommended integrations

BrewAssistant v4 can work with different levels of automation.

### Basic/manual mode

No external brewing integration is required.

Useful entities:

- Manual batch name.
- Manual SG readings.
- Manual target FG.
- Batch active/packaged toggles.

### Fermentation automation

Useful integrations/entities:

- RAPT Pill or other gravity/temperature sensor.
- Fermentation chamber climate entity.
- Fridge/kegerator temperature sensor.
- Heating mat switch.
- Cooling/fridge switch.

### Brewfather-assisted mode

Useful Brewfather-derived data:

- Recipe name.
- Batch status.
- Fermentation start.
- Target temperature.
- Fermentation steps.
- OG/FG values.

### Future hot-side mode

Potential integrations:

- BrewZilla RAPT.
- RAPT Cloud.
- Brewfather BrewTracker or brew-day data.

---

## 6. Verify core entities

After restart, confirm that the main sensors/helpers exist.

Examples:

```text
sensor.recipe_runtime_name
sensor.recipe_runtime_status
sensor.recipe_runtime_primary_temp
sensor.recipe_runtime_cold_crash_temp
sensor.brew_process_status
sensor.brew_process_next_step
input_boolean.manual_batch_active
input_text.manual_batch_name
```

Exact names may vary during migration. See `entities.md` and `legacy-migration.md`.

---

## 7. Restart-safe workflow state

If using restart-persistent workflow state, install and configure a persistence method such as the Home Assistant Saver integration.

Recommended persisted values:

- Current brewing phase.
- Workflow status.
- Batch active state.
- Manual batch data.
- Manual SG readings.

---

## 8. Safety checks

Before relying on automation:

- Confirm all entity names.
- Confirm climate setpoints are correct.
- Confirm cooling and heating switches behave as expected.
- Confirm pressure equipment is used within rated limits.
- Confirm notifications are enabled only after testing.

---

## 9. Updating

When updating BrewAssistant:

1. Back up current package files.
2. Apply backend package changes.
3. Apply matching dashboard card changes.
4. Restart Home Assistant.
5. Check logs for template errors.
6. Verify dashboards no longer reference removed entities.

