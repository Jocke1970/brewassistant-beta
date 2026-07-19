from pathlib import Path

BAD = {"unknown", "unavailable", "none", ""}


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly 1 match for {old!r}, found {count}")
    write(path, text.replace(old, new, 1))


def replace_all(path, old, new, minimum=1):
    text = read(path)
    count = text.count(old)
    if count < minimum:
        raise RuntimeError(f"{path}: expected at least {minimum} matches for {old!r}, found {count}")
    write(path, text.replace(old, new))


sensor = "custom_components/brewassistant/sensor.py"

replace_once(
    sensor,
    "from homeassistant.const import UnitOfTemperature\n",
    "from homeassistant.const import UnitOfPower, UnitOfTemperature\n",
)

replace_once(
    sensor,
    "    CONF_GRAVITY_ENTITY,\n"
    "    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,\n",
    "    CONF_FERMENTATION_HEAT_POWER_ENTITY,\n"
    "    CONF_GRAVITY_ENTITY,\n"
    "    CONF_KEGERATOR_AIR_TEMP_ENTITY,\n"
    "    CONF_KEGERATOR_FAN_POWER_ENTITY,\n"
    "    CONF_KEGERATOR_POWER_ENTITY,\n"
    "    CONF_RUNTIME_COLD_CRASH_TARGET_ENTITY,\n",
)

replace_once(
    sensor,
    "def _runtime_entities(coordinator: BrewAssistantCoordinator) -> dict[str, str]:\n",
    "def _configured_numeric_source_value(\n"
    "    coordinator: BrewAssistantCoordinator,\n"
    "    config_key: str,\n"
    ") -> float | None:\n"
    '    """Return a numeric value from one configured external source entity."""\n'
    "    entity_id = coordinator.configured_entities.get(config_key)\n"
    "    state = coordinator.hass.states.get(entity_id) if entity_id else None\n"
    "    if state is None or str(state.state).lower() in {\"unknown\", \"unavailable\", \"none\", \"\"}:\n"
    "        return None\n"
    "    try:\n"
    "        return float(str(state.state).replace(\",\", \".\"))\n"
    "    except (TypeError, ValueError):\n"
    "        return None\n"
    "\n"
    "\n"
    "def _runtime_entities(coordinator: BrewAssistantCoordinator) -> dict[str, str]:\n",
)

replace_once(
    sensor,
    "BREWZILLA_TEMPERATURE_SENSORS = {\n",
    "CONFIGURED_SOURCE_VALUE_SENSORS = {\n"
    '    "kegerator_air_temperature": {\n'
    '        "config_key": CONF_KEGERATOR_AIR_TEMP_ENTITY,\n'
    '        "unit": UnitOfTemperature.CELSIUS,\n'
    '        "device_class": SensorDeviceClass.TEMPERATURE,\n'
    '        "state_class": SensorStateClass.MEASUREMENT,\n'
    "    },\n"
    '    "kegerator_power": {\n'
    '        "config_key": CONF_KEGERATOR_POWER_ENTITY,\n'
    '        "unit": UnitOfPower.WATT,\n'
    '        "device_class": SensorDeviceClass.POWER,\n'
    '        "state_class": SensorStateClass.MEASUREMENT,\n'
    "    },\n"
    '    "kegerator_fan_power": {\n'
    '        "config_key": CONF_KEGERATOR_FAN_POWER_ENTITY,\n'
    '        "unit": UnitOfPower.WATT,\n'
    '        "device_class": SensorDeviceClass.POWER,\n'
    '        "state_class": SensorStateClass.MEASUREMENT,\n'
    "    },\n"
    '    "fermentation_heat_power": {\n'
    '        "config_key": CONF_FERMENTATION_HEAT_POWER_ENTITY,\n'
    '        "unit": UnitOfPower.WATT,\n'
    '        "device_class": SensorDeviceClass.POWER,\n'
    '        "state_class": SensorStateClass.MEASUREMENT,\n'
    "    },\n"
    "}\n"
    "\n"
    "\n"
    "BREWZILLA_TEMPERATURE_SENSORS = {\n",
)

replace_once(
    sensor,
    "        + [BrewAssistantSourceSensor(coordinator, key) for key in SOURCE_SENSORS]\n"
    "        + [BrewAssistantRuntimeSensor(coordinator, key) for key in RUNTIME_SENSORS]\n",
    "        + [BrewAssistantSourceSensor(coordinator, key) for key in SOURCE_SENSORS]\n"
    "        + [\n"
    "            BrewAssistantConfiguredSourceValueSensor(coordinator, key)\n"
    "            for key in CONFIGURED_SOURCE_VALUE_SENSORS\n"
    "        ]\n"
    "        + [BrewAssistantRuntimeSensor(coordinator, key) for key in RUNTIME_SENSORS]\n",
)

replace_once(
    sensor,
    "class BrewAssistantBrewZillaTemperatureSensor(BrewAssistantEntity, SensorEntity):\n",
    "class BrewAssistantConfiguredSourceValueSensor(BrewAssistantEntity, SensorEntity):\n"
    '    """Normalized numeric mirror of one configured external sensor."""\n'
    "\n"
    "    _attr_has_entity_name = False\n"
    "\n"
    "    def __init__(self, coordinator: BrewAssistantCoordinator, key: str) -> None:\n"
    "        super().__init__(coordinator, key)\n"
    "        config = CONFIGURED_SOURCE_VALUE_SENSORS[key]\n"
    "        self._key = key\n"
    '        self._config_key = str(config["config_key"])\n'
    "        self._attr_name = _display_name_from_key(key)\n"
    '        self._attr_suggested_object_id = f"{DOMAIN}_{key}"\n'
    '        self._attr_native_unit_of_measurement = config.get("unit")\n'
    '        self._attr_device_class = config.get("device_class")\n'
    '        self._attr_state_class = config.get("state_class")\n'
    "\n"
    "    @property\n"
    "    def native_value(self) -> float | None:\n"
    '        """Return the configured external sensor value."""\n'
    "        return _configured_numeric_source_value(self.coordinator, self._config_key)\n"
    "\n"
    "    @property\n"
    "    def extra_state_attributes(self) -> dict[str, object]:\n"
    '        """Expose the selected source entity for diagnostics."""\n'
    "        entity_id = self.coordinator.configured_entities.get(self._config_key)\n"
    "        state = self.coordinator.hass.states.get(entity_id) if entity_id else None\n"
    "        return {\n"
    '            "source_entity": entity_id,\n'
    '            "source_state": state.state if state is not None else None,\n'
    '            "source_available": self.native_value is not None,\n'
    "        }\n"
    "\n"
    "\n"
    "class BrewAssistantBrewZillaTemperatureSensor(BrewAssistantEntity, SensorEntity):\n",
)

replacements = {
    "dashboard/brewassistant_sanity.yaml": [
        ("sensor.brewassistant_kegerator_air_temperature_average", "sensor.brewassistant_kegerator_air_temperature"),
        (
            "      - type: attribute\n        entity: sensor.brewassistant_source_health_summary\n        attribute: kegerator_power_entity_state\n        name: Kegerator power\n",
            "      - entity: sensor.brewassistant_kegerator_power\n        name: Kegerator power\n",
        ),
        (
            "      - type: attribute\n        entity: sensor.brewassistant_source_health_summary\n        attribute: kegerator_fan_power_entity_state\n        name: Fan power\n",
            "      - entity: sensor.brewassistant_kegerator_fan_power\n        name: Fan power\n",
        ),
    ],
    "dashboard/cards/brewassistant_hub.yaml": [
        ("sensor.brewassistant_kegerator_air_temperature_average", "sensor.brewassistant_kegerator_air_temperature"),
    ],
    "dashboard/cards/brewassistant_source_health.yaml": [
        ("sensor.brewassistant_kegerator_air_temperature_average", "sensor.brewassistant_kegerator_air_temperature"),
        (
            "Number(states['sensor.brewassistant_source_health_summary']?.attributes?.kegerator_power_entity_state)",
            "num('sensor.brewassistant_kegerator_power')",
        ),
    ],
    "dashboard/cards/kegerator.yaml": [
        ("sensor.brewassistant_kegerator_air_temperature_average", "sensor.brewassistant_kegerator_air_temperature"),
        (
            "attrNum('sensor.brewassistant_source_health_summary', 'kegerator_power_entity_state')",
            "n('sensor.brewassistant_kegerator_power')",
        ),
        (
            "attrNum('sensor.brewassistant_source_health_summary', 'kegerator_fan_power_entity_state')",
            "n('sensor.brewassistant_kegerator_fan_power')",
        ),
        (
            "states['sensor.brewassistant_source_health_summary']?.attributes?.kegerator_power_entity_state",
            "states['sensor.brewassistant_kegerator_power']?.state",
        ),
    ],
    "dashboard/cards/fermentation.yaml": [
        (
            "Number(states['sensor.brewassistant_source_health_summary']?.attributes?.fermentation_heat_power_entity_state)",
            "Number(states['sensor.brewassistant_fermentation_heat_power']?.state)",
        ),
        (
            "const pillStatus = clean(states['sensor.brewassistant_smart_pill_status_core']?.state) || clean(states['sensor.brewassistant_smart_pill_status_core']?.state) || '—';",
            "const pillStatus = clean(states['sensor.brewassistant_smart_pill_status_core']?.state) || '—';",
        ),
        (
            "              - entity: sensor.brewassistant_gravity\n                name: BrewAssistant SG\n\n              - entity: sensor.brewassistant_gravity_last_updated\n",
            "              - entity: sensor.brewassistant_gravity\n                name: BrewAssistant SG\n              - entity: sensor.brewassistant_gravity_last_updated\n",
        ),
        (
            "              - entity: sensor.brewassistant_gravity_last_updated\n                name: SG last updated\n              - entity: sensor.brewassistant_smart_pill_status_core\n                name: Pill status\n",
            "              - entity: sensor.brewassistant_gravity_last_updated\n                name: SG last updated\n",
        ),
        (
            "              - type: attribute\n                entity: sensor.brewassistant_source_health_summary\n                attribute: fermentation_heat_power_entity_state\n                name: Heat mat power\n",
            "              - entity: sensor.brewassistant_fermentation_heat_power\n                name: Heat mat power\n",
        ),
    ],
}

for path, pairs in replacements.items():
    for old, new in pairs:
        replace_all(path, old, new)

for path in [
    "dashboard/brewassistant_sanity.yaml",
    "dashboard/cards/brewassistant_hub.yaml",
    "dashboard/cards/brewassistant_source_health.yaml",
    "dashboard/cards/fermentation.yaml",
    "dashboard/cards/kegerator.yaml",
]:
    text = read(path)
    forbidden = [
        "kegerator_power_entity_state",
        "kegerator_fan_power_entity_state",
        "fermentation_heat_power_entity_state",
        "sensor.brewassistant_kegerator_air_temperature_average",
    ]
    hits = [item for item in forbidden if item in text]
    if hits:
        raise RuntimeError(f"{path}: indirect/average source references remain: {hits}")

fermentation = read("dashboard/cards/fermentation.yaml")
if fermentation.count("const pillStatus =") != 1:
    raise RuntimeError("fermentation.yaml: expected one pillStatus declaration")
if fermentation.count("entity: sensor.brewassistant_smart_pill_status_core") != 2:
    raise RuntimeError("fermentation.yaml: expected Pill status on card and detail row")

print("Configured source cleanup applied")
