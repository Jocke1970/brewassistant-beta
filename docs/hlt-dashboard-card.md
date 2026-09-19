# HLT simulation dashboard (operator card)

## Files

- `dashboard/cards/hlt_power_dashboard.yaml` — English canonical standalone card.
- `dashboard/cards/hlt_power_dashboard_sv.yaml` — Swedish standalone mirror.
- Backend entity and units contract: `docs/hlt-dashboard-backend.md`.

Copy the **entire** Swedish or English YAML into a Home Assistant dashboard Manual card **after installing this feature-branch integration**, or embed it as a standalone card in a personally composed Brewday view. Requires the `custom:button-card` frontend already used elsewhere in BrewAssistant. These are example Lovelace YAML files in the repository; they are not automatically installed in the user's dashboard.

The card is read-only (`tap_action`, `hold_action`, `double_tap_action`: none). It cannot activate HLT, adjust BZ power, approve a supervised action or enforce the electricity budget. The simulation is intentionally distinct from physical readings:

- BrewZilla priority is the fixed policy. BZ observed W and *virtual* HLT W occupy separate fields/bars. The bars are relative to a configurable simulation budget, **not a measured house circuit limit**. A low reading does not authorize real concurrent heating.
- The real power recipient and physical total need both BZ and HLT physical wattmeters; when the HLT is not installed, `unknown` / `—` is correct. The virtual recipient displays only simulated permission, not physical switching.
- HLT current temperature always carries `MEASURED`, `MODEL ESTIMATE`, or `THERMOSTAT-CALIBRATED ESTIMATE`. The measured probe and estimated value are also listed separately.
- Three principal clocks: elapsed HLT session wall time, sampled *virtual* heating time, and sampled *observed* heating estimate (needs physical watts plus ON switch at both endpoints). Additional waiting/yielding/unknown-gap clocks and estimated Wh are diagnostics; all counters reset after HA/integration restart and cannot be presented as physical meters.
- JSONL trace name is shown; `sensor.brewassistant_hlt_trace_path` contains the full server-side file path. This is not a download URL.

## Field-test sequence

1. Keep the HLT heater physically disconnected and leave PR #212 in draft. Plug **BrewZilla** into the actual energy-metered outlet; while the beer fridge is on that outlet, the BZ watt sensor may describe the fridge. Confirm the mapped `sensor.brewzilla_power` value follows the kettle when its heater starts and stops. Do not infer this from the entity name alone.
2. Install/test the feature-branch integration in a controlled Home Assistant setup. Confirm `sensor.brewassistant_hlt_status`, `sensor.brewassistant_hlt_temperature_source`, `sensor.brewassistant_hlt_power_virtual`, `sensor.brewassistant_hlt_total_session_seconds`, and `sensor.brewassistant_hlt_trace_path` exist (HA may suffix renamed entity IDs).
3. Start a Brewday Audit session with a known positive sparge volume. Observe a BZ ramp, reaching target, then a new target/ramp. The virtual HLT should wait, become eligible only on observed cruise/headroom, then yield. Physical HLT wattmeter/switch remain unknown unless physically installed; the UI must not invent 0 W or a real OFF acknowledgement.
4. Upload the JSONL from `/config/brewassistant/logs/` and compare sensor states with events and actual BZ meter readings. Confirm model-estimated HLT temperature, clock quality, session reset and abnormal/unavailable readings. Do not interpret CI checks as successful on-device validation.

**Electrical safety boundary:** the 30-second simulation and UI do not provide load shedding, OFF readback, independent interlock, dry-fire protection, or commissioned circuit ratings. A separate project phase is needed before physical HLT control is considered.
