"""Isolated explicit emergency STOP against real HA ServiceRegistry; NO device/cloud."""

from __future__ import annotations

import asyncio
from tempfile import TemporaryDirectory

from homeassistant.core import HomeAssistant

from custom_components.brewassistant.brewzilla import brewzilla_orchestration as base
from custom_components.brewassistant.brewzilla import brewzilla_observe_only as observe
from custom_components.brewassistant.brewday.brewday_operator_abort import brewday_operator_abort_active


async def run() -> None:
    with TemporaryDirectory(prefix="ba-emergency-smoke-") as config_dir:
        hass = HomeAssistant(config_dir)
        calls: list[tuple[str, str, dict]] = []
        fail_pump = False

        for domain, services in {
            "switch": ("turn_on", "turn_off"),
            "number": ("set_value",),
            "rapt_cloud_link": ("end_brewzilla_profile",),
        }.items():
            for service in services:
                async def record(call, domain=domain, service=service):
                    nonlocal fail_pump
                    payload = dict(call.data)
                    calls.append((domain, service, payload))
                    if fail_pump and service == "turn_off" and payload.get("entity_id") == base.BREWZILLA_PUMP_SWITCH:
                        raise RuntimeError("simulated pump service failure")
                hass.services.async_register(domain, service, record)

        hass.states.async_set("binary_sensor.brewzilla_test_profile_active", "on", {
            "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
            "raw_device_id": "water-test-device",
            "profile_active": True,
            "profile_contract_complete": True,
            "profile_session_id": "session-emergency",
            "step_id": "heatstrike",
            "step_name": "Heatstrike",
            "step_number": 1,
            "step_target_temperature": 40,
        })
        for entity, state in {
            base.BREWZILLA_HEATER_SWITCH: "on",
            base.BREWZILLA_PUMP_SWITCH: "on",
            base.BREWZILLA_MAIN_SWITCH: "on",
            base.BREWZILLA_HEAT_UTILIZATION: "80",
            base.BREWZILLA_PUMP_UTILIZATION: "45",
            base.BREWZILLA_TARGET_NUMBER: "40",
            base.BREWZILLA_TEMP_SENSOR: "35",
        }.items():
            hass.states.async_set(entity, state)

        assert observe.observation_required(hass), "BA must start read-only"
        assert base.async_abort_brewzilla.__module__.endswith("brewzilla_emergency_abort"), (
            "ABORT must be wired through the emergency lane before button imports"
        )
        result = await base.async_abort_brewzilla(hass)
        assert brewday_operator_abort_active(hass), "ABORT latch must precede output attempts"
        assert observe.observation_required(hass), "ABORT may not turn BA automation back on"
        assert calls == [
            ("rapt_cloud_link", "end_brewzilla_profile", {"brewzilla_id": "water-test-device"}),
            ("switch", "turn_off", {"entity_id": base.BREWZILLA_HEATER_SWITCH}),
            ("switch", "turn_off", {"entity_id": base.BREWZILLA_PUMP_SWITCH}),
            ("number", "set_value", {"entity_id": base.BREWZILLA_HEAT_UTILIZATION, "value": 0}),
            ("number", "set_value", {"entity_id": base.BREWZILLA_PUMP_UTILIZATION, "value": 0}),
            ("switch", "turn_off", {"entity_id": base.BREWZILLA_MAIN_SWITCH}),
        ], calls
        assert result["readback_safe_after_abort"] is False
        assert result["outputs_physically_off_verified"] is False
        assert result["status"] == "emergency_unverified_check_device"
        print("PASS ABORT read-only + RAPT: STOP, heater/pump OFF, both zero and main OFF attempted")

        # An explicit repeat is not blocked by the existing ABORT latch.
        previous_count = len(calls)
        fail_pump = True
        second = await base.async_abort_brewzilla(hass)
        assert len(calls) == previous_count + 6
        assert second["emergency_commands"]["pump_off"] == "failed"
        assert second["emergency_commands"]["main_power_off"] == "requested_not_physically_verified"
        assert second["outputs_physically_off_verified"] is False
        assert brewday_operator_abort_active(hass)
        print("PASS repeated ABORT independent of source/latch; one failed OFF does not skip remaining commands")

        # Missing RAPT owner still must not block the direct emergency OFF lane.
        hass.states.async_set("binary_sensor.brewzilla_test_profile_active", "off", {
            "ba_source": "rapt_cloud_link_brewzilla_profile_runtime",
            "raw_device_id": "water-test-device", "profile_active": False,
            "profile_stop_confirmed": False,
        })
        before = len(calls)
        fail_pump = False
        no_owner = await base.async_abort_brewzilla(hass)
        assert len(calls) == before + 5
        assert no_owner["emergency_commands"]["rapt_profile_end"] == "no_active_profile_verified"
        assert no_owner["outputs_physically_off_verified"] is False
        print("PASS ABORT without verified profile still requests all local outputs OFF/zero")

    print("RESULT isolated emergency HA smoke PASS; physical BrewZilla NOT verified")


if __name__ == "__main__":
    asyncio.run(run())
