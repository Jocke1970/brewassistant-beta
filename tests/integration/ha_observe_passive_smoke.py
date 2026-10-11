"""Isolated real-HA passive observation smoke; no cloud or hardware.

Exercises real BrewAssistant learning and persisted Flight Recorder against HA
StateMachine. This is not a full config-entry restart or device verification.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.brewassistant.brewday import brewday_audit as audit
from custom_components.brewassistant.brewzilla import brewzilla_learning as learning
from custom_components.brewassistant.brewzilla import brewzilla_observe_only as observe


async def run() -> None:
    with TemporaryDirectory(prefix="ba-observe-passive-") as config_dir:
        # A real HA Store from the old rolling-window test era must be
        # discarded exactly once when the clean JSONL generation starts.
        legacy = HomeAssistant(config_dir)
        legacy_store = Store(legacy, audit.STORAGE_VERSION, audit.STORAGE_KEY)
        await legacy_store.async_save({
            "active": True, "event_count_total": 250,
            "started_at": "2026-10-10T15:40:00+00:00",
            "events": [{"event_type": "runtime_tick", "note": "prior test"}],
        })
        hass = HomeAssistant(config_dir)
        clean = await audit.async_load_brewday_audit_log(hass)
        assert not clean.active and not clean.events and clean.total_events == 0
        assert clean.file_path is None
        saved = await Store(hass, audit.STORAGE_VERSION, audit.STORAGE_KEY).async_load()
        assert saved["archive_generation"] == audit.ARCHIVE_GENERATION
        print("PASS one-time reset discards only pre-release audit test history")
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
        hlt_event = audit._event_base(hass, "hlt_sim_yield", note="isolated HLT audit")
        hlt_event.update({"hlt_simulation": True, "hlt_state": "yield",
                          "hlt_transition_events": ["virtual_hlt_off_requested"]})
        await audit.async_record_brewday_audit_prebuilt_event(hass, hlt_event)
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
        assert reloaded.active and reloaded.total_events == snap["event_count"]
        assert len(reloaded.events) <= audit.STORE_TAIL_EVENTS
        assert reloaded.file_path == snap["archive_path"]
        path = Path(config_dir, reloaded.file_path)
        assert path.is_file()
        import json
        archived = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert len(archived) == snap["event_count"]
        assert any(event.get("power_w") == 1650.0 for event in archived)
        assert any(event.get("hlt_state") == "yield" and event.get("hlt_simulation")
                   for event in archived)
        assert "events" not in snap and "recent_events" not in snap
        assert calls == []
        print("PASS complete JSONL survives HA Store reload; HA only keeps light continuity")

        hass.states.async_set("sensor.brewzilla_power", "unavailable")
        await audit.async_record_brewday_audit_tick(hass, brewzilla_result=result)
        assert audit.get_brewday_audit_log(hass).events[-1].get("power_w") is None
        assert calls == []
        print("PASS unavailable power is not invented as 0 W; no BA outputs")

    print("RESULT isolated passive HA smoke: PASS (no full config-entry/device proof)")


if __name__ == "__main__":
    asyncio.run(run())
