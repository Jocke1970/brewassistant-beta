"""Real HA Core service-registry / pinned RCL profile boundary smoke test.

Run only in an isolated CI instance. Real BA and RCL Python code is imported,
RCL API and physical BrewZilla outputs are NOT connected. Passing this test is
not approval for a physical or production HA installation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from homeassistant.core import HomeAssistant

from custom_components.brewassistant import control_policy
from custom_components.brewassistant.brewday import rapt_profile_runtime as rapt
from custom_components.brewassistant.brewzilla import brewzilla_observe_only as observer
from custom_components.brewassistant.brewzilla import brewzilla_observe_only_dispatch_guard as dispatch
from custom_components.brewassistant.brewzilla import brewzilla_source_authority_runtime as authority
from custom_components.rapt_cloud_link.binary_sensor import BrewZillaProfileActiveBinarySensor


async def run() -> None:
    with TemporaryDirectory(prefix="ba-rcl-ha-smoke-") as config_dir:
        assert Path(config_dir).is_dir()
        hass = HomeAssistant(config_dir)
        calls: list[tuple[str, str, dict]] = []

        # Real HA ServiceRegistry: the registered handlers stand in for RCL's
        # cloud-backed entities. Record ALL calls, including OFF and 0 %.
        for domain, services in {
            "switch": ("turn_on", "turn_off"),
            "number": ("set_value",),
            "rapt_cloud_link": ("end_brewzilla_profile", "start_brewzilla_profile"),
        }.items():
            for service in services:
                async def record(call, *, domain=domain, service=service):
                    calls.append((domain, service, dict(call.data)))
                hass.services.async_register(domain, service, record)

        device = {
            "name": "BrewZilla Gen 4.1 35L",
            "activeProfileId": "profile-water",
            "activeProfileStepId": "step-heatstrike",
            "activeProfileSession": {
                "id": "session-water-1",
                "profileId": "profile-water",
                "profile": {
                    "id": "profile-water", "name": "Water-only integration test",
                    "steps": [{"id": "step-heatstrike", "order": 0,
                               "name": "Heatstrike", "temperature": 40}],
                },
            },
        }
        coordinator = SimpleNamespace(data={"brewzilla-test": device})
        rcl_sensor = BrewZillaProfileActiveBinarySensor(coordinator, "brewzilla-test")
        attrs = rcl_sensor.extra_state_attributes
        assert rcl_sensor.is_on is True
        assert attrs["ba_source"] == rapt.RAPT_PROFILE_BA_SOURCE
        assert attrs["profile_contract_complete"] is True
        assert attrs["profile_session_id"] == "session-water-1"
        assert attrs["step_target_temperature"] == 40

        # The real RCL entity may have a device-prefixed entity ID.
        profile_entity = "binary_sensor.brewzilla_gen_4_1_35l_profile_active"
        hass.states.async_set(profile_entity, "on", attrs)
        selected = rapt._profile_state(hass)
        assert selected is not None and selected.entity_id == profile_entity
        assert rapt._active_contract(selected)
        assert rapt._last_known_from_state(selected)["profile_session_id"] == "session-water-1"
        print("PASS real RCL profile entity -> real HA StateMachine -> BA dynamic discovery")

        # Make every proposed physical destination visible in the real HA state
        # machine, so a mistaken call cannot be hidden by an entity-not-found
        # short circuit in BA's legacy STOP path.
        for entity, value in {
            "sensor.brewzilla_temperature": "35.0",
            "number.brewzilla_target_temperature": "40",
            "number.brewzilla_heat_utilization": "60",
            "number.brewzilla_pump_utilization": "50",
            "switch.brewzilla_heater": "on",
            "switch.brewzilla_pump": "on",
            "switch.brewzilla": "on",
        }.items():
            hass.states.async_set(entity, value)

        observer.install_observe_only_guard()
        dispatch.install_observe_only_dispatch_guard()
        assert observer.observation_required(hass)
        assert observer._store(hass)["reason"] == "startup_fail_closed"

        for entity, action, value in (
            ("number.brewzilla_target_temperature", None, 40.0),
            ("number.brewzilla_heat_utilization", None, 0.0),
            ("number.brewzilla_pump_utilization", None, 0.0),
            ("switch.brewzilla_heater", "on", None),
            ("switch.brewzilla_heater", "off", None),
            ("switch.brewzilla_pump", "on", None),
            ("switch.brewzilla_pump", "off", None),
            ("switch.brewzilla", "off", None),
            ("switch.bryggeriet_brewzilla_pump", "off", None),
        ):
            assert observer._protected(entity)
            assert authority._write_allowed(hass, entity, switch_action=action, value=value) is False

        for section, command, value in (
            ("target", "set_target_temperature", 40),
            ("heater", "heater_on", None),
            ("heater", "heater_off", None),
            ("pump", "pump_on", None),
            ("pump", "pump_off", None),
        ):
            request = await control_policy.request_action(
                hass, section=section, command=command, value=value,
            )
            assert request["status"] == "observe_only_denied", request
            direct = await control_policy.execute_action(
                hass, control_policy.build_action(section=section, command=command, value=value),
            )
            assert direct["status"] == "observe_only_denied", direct

        # Confirmed STOP and operator ABORT must not transform observation into
        # a BA-issued OFF or utilization=0; run the real legacy STOP function.
        await rapt._async_safe_off_after_profile_stop(hass, "session-water-1:test-stop")
        assert calls == [], f"BA service escaped observe-only: {calls}"
        assert observer._safe_off_allowed(SimpleNamespace(), {"observe_only": True}) is False
        print("PASS real HA ServiceRegistry: BA target/heat/pump + OFF/zero/STOP no output")

        # Switching OFF is intentionally not permission to resume control.
        observer._store(hass).update(enabled=False, rearmed=False)
        assert observer.observation_required(hass)
        denied = await control_policy.request_action(hass, section="heater", command="heater_on")
        assert denied["status"] == "observe_only_denied"
        assert calls == []
        print("PASS switch OFF without separate rearm remains denied")

        # BA must not intercept independently initiated RCL/local actions. This
        # invokes the same HA service registry directly, outside BA's writer.
        await hass.services.async_call("switch", "turn_on",
                                       {"entity_id": "switch.brewzilla_heater"}, blocking=True)
        assert calls == [("switch", "turn_on", {"entity_id": "switch.brewzilla_heater"})]
        print("PASS independent direct RCL/local service remains outside BA guard")

        # A broken handoff stays an ACTIVE but INCOMPLETE RCL contract, not STOP.
        device["activeProfileStepId"] = "unknown-step"
        attrs = rcl_sensor.extra_state_attributes
        assert rcl_sensor.is_on and not attrs["profile_contract_complete"]
        assert attrs["profile_stop_confirmed"] is False
        print("PASS RCL incomplete step transition does not report confirmed STOP")

    print("RESULT isolated HA/RCL observer smoke: PASS (NO live API/device proof)")


if __name__ == "__main__":
    asyncio.run(run())
