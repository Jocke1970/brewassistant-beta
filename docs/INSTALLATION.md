# Installation Guide

BrewAssistant is installed as a Home Assistant custom integration.

The active repository setup is Python-first:

```text
custom_components/brewassistant/ = integration/backend logic
Dashboards                    = optional presentation layer
Legacy local packages          = not part of mainline install
```

---

## Install path

Place the integration here in Home Assistant:

```text
/config/custom_components/brewassistant/
```

The repository path to sync is:

```text
custom_components/brewassistant/
```

---

## Manual install / update

From a temporary clone of the repository:

```bash
rm -rf /tmp/brewassistant-beta
git clone --depth 1 --branch main https://github.com/Jocke1970/brewassistant-beta.git /tmp/brewassistant-beta

cp -a /config/custom_components/brewassistant /config/custom_components/brewassistant_backup_$(date +%Y%m%d_%H%M) 2>/dev/null || true

rsync -a --delete \
  /tmp/brewassistant-beta/custom_components/brewassistant/ \
  /config/custom_components/brewassistant/
```

Restart Home Assistant after syncing.

---

## First checks after restart

Check Developer Tools → States for core entities such as:

```text
sensor.brewassistant_core_version
sensor.brewassistant_next_action
sensor.brewassistant_brewday_runtime_status
sensor.brewassistant_brewday_stage
sensor.brewassistant_brewzilla_wort_temperature
sensor.brewassistant_carbonation_status
switch.brewassistant_kegerator_fan_auto_enabled
```

Some entity IDs may be prefixed by Home Assistant, depending on the integration/device/area naming.

---

## Dashboard setup

Dashboard YAML is optional. It should display state and expose explicit operator actions, not contain hidden workflow logic.

Current dashboard baseline notes:

```text
docs/dashboard-baselines.md
```

Install required Lovelace frontend cards through HACS before using dashboard examples.

Common cards used by current dashboard baselines:

```text
custom:button-card
custom:vertical-stack-in-card
custom:mushroom-*
custom:expander-card
custom:gauge-card-pro
```

---

## Legacy package warning

Do not install old BrewAssistant YAML packages as the main setup path.

Older local Home Assistant installs may still contain BrewAssistant YAML packages under `/config/packages/` or `/config/packages_disabled/`. They are legacy/local compatibility files, not the current repository source of truth.

Running old packages together with the Python integration may create duplicate helpers, stale unavailable entities or dashboard drift.

Recommended policy:

```text
1. Keep old packages disabled unless intentionally testing migration behavior.
2. Verify dashboards use current Python-backed entities.
3. Remove orphaned unavailable entities through Home Assistant UI only.
4. Never edit .storage files manually.
```

---

## Safety scope

BrewAssistant beta is intended for supervised use.

```text
- BrewZilla orchestration is not unattended autopilot.
- Operator supervision is expected during brewday actions.
- Kegerator fan-auto only controls the circulation fan, not compressor safety.
- Compressor cycling remains owned by the Home Assistant climate/thermostat layer.
- Pressure equipment must be used within rated limits.
```
