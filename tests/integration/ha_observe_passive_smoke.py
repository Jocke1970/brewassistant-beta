"""Isolated real-HA passive observation smoke; no cloud or hardware.

Exercises real BrewAssistant learning and persisted Flight Recorder against HA
StateMachine. This is not a full config-entry restart or device verification.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from homeassistant.core import HomeAssistant

from custom_components.brewassistant.brewday import brewday_audit as audit
from custom_components.brewassistant.brewzilla import brewzilla_learning as learning
from custom_components.brewassistant.brewzilla import brewzilla_observe_only as observe


async def run() -> None:
    with TemporaryDirectory(prefix="ba-observe-passive-") as config_dir:
        hass = HomeAssistant(config_dir)
        calls: list[tuple[str, str, dict]] = []
        for domain, services in {"switch": ("turn_on", "turn_off"), "number": ("set_value",)}.items():
            for service in services:
                async def record(call, domain=domain, service=service):
                    calls.append((domain, service, dict(call.data)))
                hass.services.async_register(domain, service, record)

        assert observe.observation_required(hass)
        for entity, value in {
            "sensor.brewzilla_temperature": "35.0",
            "sensor.brewassistant_brewzilla_current_temperature": "35.0",
            "sensor.brewassistant_brewzilla_target_temperature": "40.0",
            "sensor.brewassistant_brewzilla_device_target_temperature": "40.0",
            "number.brewzilla_target_temperature": "40.0",
            "number.brewzilla_heat_utilization": "35",
            "number.brewzilla_pump_utilization": "50",
            "sensor.brewzilla_power": "1725.0",
            "sensor.brewassistant_brewzilla_power": "1725.0",
            "switch.brewzilla": "on",
            "switch.brewzilla_heater": "on",
            "switch.brewzilla_pump": "on",
            "select.brewassistant_brewzilla_learning_context": "Water only",
            "sensor.brewassistant_brewday_runtime_state": "running",
        }.items():
            hass.states.async_set(entity, value)

        await audit.async_start_brewday_audit_log(hass, note="isolated observe-only test")
        first = learning.build_brewzilla_learning_snapshot(hass)
        assert first["observation_count"] >= 1
        assert first["auto_apply_allowed"] is False
        assert first["power_w"] == 1725.0
        assert calls == []
        print("PASS passive learning reads live HA temperatures, utilization and power; no services")

        result = {"orchestration_mode": "observe-only", "control_reason": "operator_observe_only",
                  "apply_result": "observe_only", "applied": False, "actions": []}
        await audit.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        hass.states.async_set("sensor.brewzilla_temperature", "36.2")
        hass.states.async_set("sensor.brewassistant_brewzilla_current_temperature", "36.2")
        hass.states.async_set("sensor.brewzilla_power", "1650.0")
        second = learning.build_brewzilla_learning_snapshot(hass)
        assert second["observation_count"] > first["observation_count"]
        assert second["power_w"] == 1650.0
        await audit.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        snap = audit.build_brewday_audit_snapshot(hass)
        assert snap["active"] is True and snap["event_count"] >= 2
        assert any(event.get("power_w") == 1650.0 for event in audit.get_brewday_audit_log(hass).events)
        assert calls == []
        print("PASS Flight Recorder tracks changing readbacks and watts while BA observes")

        # A new in-memory HA object reading the same temporary config directory
        # validates real Store serialization, not full HA config-entry startup.
        restarted = HomeAssistant(config_dir)
        assert observe.observation_required(restarted), "fresh HA runtime must fail closed"
        reloaded = await audit.async_load_brewday_audit_log(restarted)
        assert reloaded.active and len(reloaded.events) == snap["event_count"]
        assert any(event.get("power_w") == 1650.0 for event in reloaded.events)
        assert calls == []
        print("PASS audit log survives Store reload; new BA runtime defaults to observation")

        hass.states.async_set("sensor.brewzilla_power", "unavailable")
        await audit.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        assert audit.get_brewday_audit_log(hass).events[-1].get("power_w") is None
        assert calls == []
        print("PASS unavailable power is not invented as 0 W; no BA outputs")

    print("RESULT isolated passive HA smoke: PASS (no full config-entry/device proof)")


if __name__ == "__main__":
    asyncio.run(run())
