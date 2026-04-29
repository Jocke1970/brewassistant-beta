# BrewAssistant Roadmap

## Hardware Evolution

BrewAssistant is designed to grow step by step with the brewing setup.

### Phase 1 — Fermentation / Kegerator Chamber

Current focus.

Goals:

- Control kegerator cooling through Home Assistant
- Protect the fridge compressor with safe cycle timing
- Add circulation fan support
- Add Shelly-based power monitoring
- Support fermentation and serving/storage use cases
- Provide a premium dashboard for chamber status, targets and workflow state

Main modules:

- Fermentation chamber control
- Kegerator control
- Compressor activity detection
- Fan circulation logic
- Brewfather fermentation target alignment
- Cold crash workflow support

---

### Phase 2 — DigiBoil 35L BIAB Support

Planned next step.

The DigiBoil will not be controlled by Home Assistant. It will use its built-in thermostat for heating and temperature holding.

Home Assistant / BrewAssistant will only provide:

- Power monitoring
- Guided BIAB workflow
- Mash timers
- Mash-out timers
- Sparge / lautering checklist
- Manual step tracking
- Notifications and reminders

Design principle:

> DigiBoil remains manually controlled. BrewAssistant acts as a guide, checklist and logging layer.

---

### Phase 3 — Dedicated Fercubator

Planned future expansion.

A separate Fercubator will become the dedicated fermentation chamber.

Goals:

- Separate fermentation control from the kegerator
- Improve fermentation temperature stability
- Add dedicated chamber workflow logic
- Support recipe-driven fermentation profiles
- Allow the kegerator to focus on serving, cold crash, carbonation and storage

---

### Phase 4 — BrewZilla 35L Gen 4.1 RAPT

Long-term target.

The BrewZilla RAPT system is considered the full hot-side automation target.

Expected integration goals:

- Read RAPT temperature
- Read target temperature
- Read heater status
- Read pump status
- Read heater utilisation
- Read pump utilisation
- Track RAPT profile state
- Support guided or semi-automated mash and boil workflows
- Reuse the DigiBoil BIAB workflow as the foundation for advanced hot-side control

Design principle:

> DigiBoil support builds the manual hot-side workflow. BrewZilla RAPT later upgrades that workflow with real device telemetry and automation.
