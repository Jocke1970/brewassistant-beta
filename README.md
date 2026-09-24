# BrewAssistant Beta

Modulär Home Assistant-integration för bryggdag, BrewZilla/RAPT, Brewfather/BrewTracker, Manual Brewday, jäsning, kylning, servering, mätning, historik och dashboards.

> [!IMPORTANT]
> **Aktuellt 2026-09-24:** Läs [24/9-checkpointen inför nästa beta-promotion](docs/doc-sync-2026-09-24_sv.md), [roadmap](docs/roadmap.md) och [installationsguiden](docs/INSTALLATION.md). Senaste publicerade prerelease är fortfarande [v0.2.0-beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14), taggad på `1a956c04044df870e005392b6bfe946097b9d440`. Fysisk acceptans saknas; använd endast kontrollerat vattenprov. 24/9-synken innehåller dokumentations- och arkitekturstädning inför nästa `dev → beta`-testcykel; den skapar ingen ny release, flyttar ingen publicerad tagg och uppgraderar inte `main`.

## Säker användning av beta.14

- **BA endast observation:** `switch.brewassistant_brewzilla_observe_only` **PÅ** spärrar BA:s ordinarie automatiska BrewZilla-skrivningar. Den stänger **inte** redan aktiv fysisk värme/pump eller externa RCL-/panelkommandon. Switch **AV** genomför kontroll av behörig källa, separat ABORT och sex färska readbacks; misslyckas kontrollen förblir read-only PÅ. HA-start är fail-closed. Avvecklad `switch.brewassistant_brewzilla_orchestration_enabled` får inte ligga kvar i egna kort/automationer.
- **Känt HA-entitets-ID:** i en riktig beta.14-installation skapade HA `switch.brewassistant_endast_observation_brewzilla_styrs_lokalt` i stället för kanoniska ID:t ovan. Byt ID i HA:s entitetsinställningar eller anpassa lokalt YAML; en automatiserad migrationsfix återstår. Ändra inte `.storage` manuellt.
- **ABORT:** separat nödåtgärd som försöker stoppa RAPT-profil och begära OFF/0 även under read-only. Service-ACK eller HA `off` verifierar inte fysisk avstängning. Efter fysisk kontroll används `button.brewassistant_rearm_brewday_control`; verifiera `operator_abort_active: false`. Det återger inte i sig BA skrivbehörighet eller väljer bryggkälla.
- **Manual Brewday:** beta.14:s [SV-observationskort](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only_sv.yaml) och [EN-kort](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only.yaml) monteras manuellt bredvid ordinarie Manual-kort. Direkta RCL-reglage visas bara med observe-only PÅ, vald Manual-källa, bekräftat profil-STOP och ingen ABORT; de direkta kommandona går utanför BA:s automationsspärr. Äldre BA-ägda Manual-setpoints skickas inte i observe-only. Lovelace-synlighet är inte fysisk säkerhetsbarriär.
- **Senaste HA-fynd:** orchestration-sensorn rapporterade `observe_only_effective: true`, `hot_side_actuator_writes_allowed: false`, men RCL var samtidigt `Disconnected`. Separat ABORT återställdes därefter (`operator_control_state: armed`), men bryggkälla var fortfarande `None`/runtime `idle`. Varken fysisk utgångskontroll eller vattenprov är därmed godkänt. Se [fältanteckningar 22/9](docs/doc-sync-2026-09-22_sv.md).
- **Acceptans:** 387 automatiserade beta.14-testfall, CI/HACS/Hassfest och isolerad HA/RCL-smoke är inte full verklig config-entry/klicktest/molnkommando/fysisk STOP-verifikation. Endast övervakat vattenprov med backup och åtkomlig fysisk frånkoppling. [Issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) förblir öppen.
- **HLT:** SIM-1 läser och simulerar virtuell effekt/temperatur. Ingen fysisk HLT-styrning, BZ-begränsning eller elsäkerhet. [Fältrapport 20/9](docs/hlt-sim1-field-validation-2026-09-20.md) innehåller fem virtuella värmeprover och tre hypotetiska effektkonflikter; `Heat Strike`/ramp-beredskap är ännu inte rättad eller accepterad.

## Kod, roller och körlägen

```text
Brewfather Brew Tracker / RAPT profile / Manual Brewday
   -> Brewday: källa, stage, steg, timer, Audit och Flight Recorder
   -> BrewZilla-backend: policy, behörighet, eventuella RCL-kommandon
   -> HLT SIM-1: fristående, endast läsande 30 s-consumer
Dashboard YAML: presentation och uttryckliga operatörsreglage (kan vara direkt RCL)
```

Recept/profilkälla, timerägare och tillstånd att styra fysisk utrustning är skilda begrepp. RAPT-profil ger processintention men BA:s skrivrätt följer källpolicy och säkerhetsspärrar; BrewTracker som bryggkälla är observerande i hot-side; Manual har separat policy; Brewfather-fermentering är oberoende. Ingen tyst fallback till BF/BT vid RAPT-bortfall. Se [execution modes](docs/brewday-execution-modes.md), [RAPT-kontrakt](docs/rapt-brewzilla-profile-runtime.md) och [aktuellt fältkontrakt](docs/brewzilla-observe-only-test_sv.md).

Integrationskoden finns under `custom_components/brewassistant/`. Kort under `dashboard/cards/` monteras inte automatiskt i användarens anpassade dashboard. Håll SV/EN-kort synkade och kontrollera verkliga entitets-ID. Beta.14:s RCL-beroende är `v0.5.0-beta.1`. Byt aldrig integration från gammal featuregren under en aktiv bryggning.

## Brancher, tester och releaseflöde

```text
dev (utveckling) -> beta (test och prerelease) -> main (fältvaliderad stabil)
```

[PR #223](https://github.com/Jocke1970/brewassistant-beta/pull/223) återförde beta.14-koden från `beta` till `dev` med merge-commit `2d8f2c0fdb1d609e39ca71d24c0f581c653c4c7e` och behöll dev:s HLT-/dokumentationsändringar. Den separata [PR #225](https://github.com/Jocke1970/brewassistant-beta/pull/225) synkade den korrigerade dokumentationen till `beta` med merge-commit `720f14a9724397cc81bced01a708dd284bc3dc54`. Detta var **ingen ny release**: beta.14-taggen flyttades inte, `main` ändrades inte, och HA uppdateras inte av en GitHub-merge. Nya ändringar på `dev`, även dokumentationsändringar, ska granskas separat före promotion. Ny kodrelease kräver egen manifestversion, granskning, CI/HACS/Hassfest på exakt avsedd SHA, ny oflyttad tagg och separat fältacceptans. Se [CONTRIBUTING](CONTRIBUTING.md).

CI finns för Python 3.11–3.13, HACS och Hassfest. Automatiska push-/PR-triggers på `dev` är avsiktligt exkluderade enligt workflow 20/9; releasebrancher, `beta`, `main` och explicita manuella körningar används. Att test inte körts är aldrig ett grönt test. Inga automatiska tester ersätter fysisk kontroll.

## Dokumentationskarta

| Fråga | Börja här |
| --- | --- |
| **Aktuell status och åtgärder** | [24 september](docs/doc-sync-2026-09-24_sv.md), [roadmap](docs/roadmap.md), [22 september – föregående checkpoint](docs/doc-sync-2026-09-22_sv.md) |
| **Installation av publicerad beta.14** | [Installationsguide](docs/INSTALLATION.md), [release](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14) |
| **Read-only, ABORT, Manual, vattenprov** | [Observationskontrakt](docs/brewzilla-observe-only-test_sv.md), [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) |
| **HLT SIM-1** | [20/9-fältrapport](docs/hlt-sim1-field-validation-2026-09-20.md), [19/9-fältrapport](docs/hlt-sim1-field-validation-2026-09-19.md), [backend](custom_components/brewassistant/hlt/README.md), [kortguide](docs/hlt-dashboard-card.md) |
| **Brewday och BrewZilla** | [Brewday README](custom_components/brewassistant/brewday/README.md), [Brewday/BZ](docs/brewday-brewzilla.md), [execution modes](docs/brewday-execution-modes.md) |
| **Fermentation och planerad SG-styrning** | [Backend](custom_components/brewassistant/fermentation_tracking/README.md), [två lägen och UI-kontrakt](docs/sg-driven-fermentation.md) |
| **Tidigare fälthistorik** | [BA-paus och RAPT-handoff](docs/ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md), [Mash-testplan](docs/physical-mash-test-plan-2026-09-19_sv.md), [6/9](docs/physical-validation-2026-09-06.md) |
| **Andra backends och UI** | [Cooling](docs/backends/cooling-backend.md), [Equipment Learning](docs/brewzilla-equipment-learning.md), [dashboard](docs/dashboard-baselines.md), [lokalisering](docs/localization.md) |
| **Ändringshistorik och utveckling** | [CHANGELOG](CHANGELOG.md), [CONTRIBUTING](CONTRIBUTING.md), [Brewday Audit](docs/brewday-audit.md) |

**Historiska fakta ändras inte till PASS:** beta.10-taggen var fel för tidigare styrprov, beta.11:s Mash-In-vattenprov avbröts och var inte godkänt, och de taggade beta.14-releaseanteckningarna har äldre förpubliceringsfraser. Senare publicering/fältfynd redovisas separat, utan att publicerad tagg eller gamla testrapporter skrivs om.