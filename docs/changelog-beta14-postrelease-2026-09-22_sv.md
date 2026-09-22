# Changelog-tillägg – beta.14 och doc-sync 22 september 2026

**Det här är ett tillägg till [`CHANGELOG.md`](../CHANGELOG.md), inte en omskrivning av historiska poster eller den redan publicerade beta.14-taggen.** [Publicerad release](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14).

## 20 september: v0.2.0-beta.14 – PR #221

**Ändring:** `switch.brewassistant_brewzilla_observe_only` ersätter den äldre inerta `switch.brewassistant_brewzilla_orchestration_enabled`. PÅ blockerar BA:s ordinarie BrewZilla-skrivningar; AV validerar behörig källa, separat ABORT och sex färska enhets-readbacks. HA-start kräver nytt aktivt operatörsval för BA-styrning. Separat ABORT försöker STOP/OFF/0 även i read-only. Direkta RCL-operatörsreglage är inte BA:s automatiska kanal och förblir utanför dess skrivspärr.

**Dashboard att uppdatera:** lägg till `dashboard/cards/brewzilla_observe_only_sv.yaml` (engelsk spegel `.yaml`) bredvid `dashboard/cards/brewassistant_manual_brewday_sv.yaml` (engelsk spegel `.yaml`). Se över det befintliga `dashboard/cards/brewday_operator_actions_sv.yaml` (engelsk spegel) och gamla YAML-referenser till den borttagna orchestration-switchen. Kort installeras inte automatiskt och lokala dashboards skrivs inte över. Separata BA-ägda Manual-setpoints skickar inte till BrewZilla i observerande läge; använd uttryckliga direkta RCL-reglage efter profil-STOP.

**Backend-/testfiler:** `custom_components/brewassistant/brewzilla/brewzilla_observe_only.py`, `custom_components/brewassistant/switch.py`, ABORT-/policy-/source-authority-runtime och tillhörande regressioner inklusive `tests/test_beta14_release_gates.py`. Releasegrenens manifest anger `0.2.0-beta.14`. 387 automatiska testfall och isolerad HA/RCL-smoke är inte ett fysiskt driftsprov.

**HA-åtgärd:** integrationsuppdatering kräver HA-omstart och faktisk kontroll av registrerade entiteter. Den svenska entity-namngivningen gav i riktig HA `switch.brewassistant_endast_observation_brewzilla_styrs_lokalt` i stället för det avsedda `switch.brewassistant_brewzilla_observe_only`. Byt entity-ID i HA UI eller korrigera eget lokalt kort; automatiserad kodmigrering återstår till senare release. Ändra aldrig `.storage` manuellt.

## 22 september: felavgränsning och dokumentationssynk

- I HA verifierades `observe_only_effective: true` och `hot_side_actuator_writes_allowed: false`, samtidigt var RCL `Disconnected` och fysisk OFF **inte** verifierad.
- Operatörens ABORT-latch återställdes med `button.brewassistant_rearm_brewday_control` och sensorn rapporterade `armed`/`operator_abort_active: false`; källan var fortfarande `None`. Detta är **inte** samma sak som att slå AV observe-only eller ge BA automatisk styrning.
- PR #223 mergade `beta` tillbaka till `dev`, vilket bevarade beta.14-koden och dev:s HLT SIM-1-/dokumentationsarbete. Den separata doc-syncen uppdaterar README, roadmap, installationsguide, testkontrakt och denna addenda; ingen hårdvarukod, ny prerelease eller `main`-promotion följer av det.
- Fysisk vattenacceptans och korrekt canonical entity-ID vid nyinstallation återstår. Se [fältstatus](doc-sync-2026-09-22_sv.md), [testkontrakt](brewzilla-observe-only-test_sv.md) och [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220).

**Historiskt oförändrat:** den taggade `docs/beta14-prerelease-notes_sv.md` innehåller äldre kandidattext; korrekt efterpubliceringsstatus finns i denna addenda och i GitHub-releasen. Flytta aldrig publicerad tagg för en textkorrigering.