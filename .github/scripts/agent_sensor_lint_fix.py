from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "custom_components/brewassistant/carbonation_backend/carbonation_runtime.py",
    '        "local_temperature_entity": LOCAL_TEMPERATURE_ENTITY,\n',
    '        "local_temperature_entity": configured_entity(\n'
    "            hass,\n"
    "            CONF_KEGERATOR_AIR_TEMP_ENTITY,\n"
    "            DEFAULT_KEGERATOR_AIR_TEMP_ENTITY,\n"
    "        ),\n",
)

fan_control = "custom_components/brewassistant/kegerator/fan_control.py"
replace_once(
    fan_control,
    "def _snapshot_from(inputs: FanInputs, decision: FanDecision, hass: HomeAssistant) -> dict[str, Any]:\n"
    "    data = _bucket(hass)\n",
    "def _snapshot_from(inputs: FanInputs, decision: FanDecision, hass: HomeAssistant) -> dict[str, Any]:\n"
    "    air_temp_entity = configured_entity(\n"
    "        hass,\n"
    "        CONF_KEGERATOR_AIR_TEMP_ENTITY,\n"
    "        DEFAULT_KEGERATOR_AIR_TEMP_ENTITY,\n"
    "    )\n"
    "    power_entity = configured_entity(\n"
    "        hass,\n"
    "        CONF_KEGERATOR_POWER_ENTITY,\n"
    "        DEFAULT_KEGERATOR_POWER_ENTITY,\n"
    "    )\n"
    "    fan_power_entity = configured_entity(\n"
    "        hass,\n"
    "        CONF_KEGERATOR_FAN_POWER_ENTITY,\n"
    "        DEFAULT_KEGERATOR_FAN_POWER_ENTITY,\n"
    "    )\n"
    "    data = _bucket(hass)\n",
)
replace_once(fan_control, '        "air_temperature_entity": AIR_TEMP,\n', '        "air_temperature_entity": air_temp_entity,\n')
replace_once(fan_control, '        "power_entity_candidates": POWER_CANDIDATES,\n', '        "power_entity_candidates": (power_entity,),\n')
replace_once(fan_control, '        "fan_power_entity": FAN_POWER,\n', '        "fan_power_entity": fan_power_entity,\n')
replace_once(
    fan_control,
    '        "power_sensor_candidates_ok": _any_available(hass, POWER_CANDIDATES),\n',
    '        "power_sensor_candidates_ok": _available(hass, power_entity),\n',
)

print("Configured sensor lint references fixed")
