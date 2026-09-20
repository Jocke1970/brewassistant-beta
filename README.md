# BrewAssistant Beta

Modulär Home Assistant-integration för bryggdag, BrewZilla/RAPT, Brewfather/BrewTracker, Manual Brewday, jäsning, kylning, servering, mätning, historik och dashboards.

> [!IMPORTANT]
> **Projektets aktuella läge, uppdaterat 2026-09-20:** Läs först [projektstatus och nästa steg](docs/project-status-2026-09-20_sv.md) samt [roadmap](docs/roadmap.md). **Senast publicerad prerelease är [v0.2.0-beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14)**; tagg och manifest är verifierade på `1a956c04044df870e005392b6bfe946097b9d440`. Beta.14 har *inte* godkänts i fysisk driftsacceptans. Vi vet inte vilken version användarens HA för närvarande kör.
>
> **Branchvarning:** denna README ligger på `dev`, vars manifest fortfarande säger `0.2.0-beta.13` och vars kod **inte** innehåller beta.14:s read-only-switch och ABORT-/Manual-UI-förändringar. `beta` har senare kod och är divergerad från `dev`. Läs [jämförelsen](https://github.com/Jocke1970/brewassistant-beta/compare/dev...beta) före ändringar eller installation. En doc-sync återför ingen kod, och en GitHub-merge uppdaterar inte HA.

## Säker användning och beta.14 i korthet

- **BA observe-only:** I den [publicerade beta.14](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/beta14-prerelease-notes_sv.md) blockerar `switch.brewassistant_brewzilla_observe_only` i läge PÅ BA:s ordinarie/automatiska hot-side-skrivningar. Det stänger **inte** av befintlig fysisk värme eller pump. AV kräver ny käll- och telemetrikontroll; uppstart ska fail-closed. Den äldre `switch.brewassistant_brewzilla_orchestration_enabled` är borttagen i beta.14 och måste rensas från egna YAML-/automationsreferenser.
- **ABORT:** Separat nödanrop som försöker stoppa profilen och begära OFF/0 även i read-only. Ett service-ACK eller `off` i HA bevisar inte att värmare, pump eller huvudström verkligen är av. Kontrollera maskinen lokalt och ha möjlighet till fysisk frånkoppling.
- **Manual Brewday:** Beta.14 har ett separat [svenskt observations-/direktreglagekort](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only_sv.yaml) och [engelskt](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only.yaml) att *manuellt* lägga intill Manual Brewday-kortet. Operatörens direkta RCL-entiteter ligger utanför BA:s automationsspärr; kortets visningsvillkor är ingen global åtkomstkontroll. BA:s äldre setpointfält skickar inte styrning i observe-only. Kontrollera verkligen stoppad RAPT-profil före övertagning.
- **Acceptans:** Automatiserad CI/HACS/Hassfest och isolerad HA/RCL-smoke är rapporterat grön för beta.14, men full installation, faktiska RCL-molnkommandon, Lovelace-klicktest, omstarter och fysisk ABORT-återkoppling är **inte** därmed verifierade. Endast kontrollerade vattenprov med närvarande operatör, backup och lokalt säkerhetsstopp; ingen obevakad användning eller maltprovning kan härledas från gröna tester. Se [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) och [beta.14-anteckningar](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/beta14-prerelease-notes_sv.md).
- **HLT:** HLT SIM-1 är fortfarande endast läsning och virtuell effekt/temperatur. Det styr ingen fysisk HLT, begränsar inte BZ och ger inget elsäkerhetsskydd. [Fältrapport 20/9](docs/hlt-sim1-field-validation-2026-09-20.md) beskriver fem virtuella värmeprover under RAPT-steget `Heat Strike` och tre *hypotetiska* effektkonflikter. Ramp-/HLT-beredskapskontraktet är ännu inte rättat/accepterat.

## Kod, roller och körlägen

```text
Brewfather Brew Tracker / RAPT profile / Manual Brewday
   -> Brewday: normaliserad källa, stage, steg, tider, Audit och Flight Recorder
   -> BrewZilla-backend: policy, aktörsbehörighet och eventuella RCL-kommandon
   -> HLT SIM-1: fristående, ENBART läsande 30 s-consumer
Dashboard YAML: visning och uttryckliga operatörsreglage (kan vara direkta RCL-anrop)
```

Källa till recept/profil, ägare av timer och rätt att styra fysisk utrustning är **tre skilda begrepp**. I beta.14 ger den valda RAPT-profilen processintention; BA kan endast styra enligt aktuell källpolicy och spärrar när observe-only är AV. BF-fermentering är självständig; BT som bryggkälla är observerande för BA:s hot-side-skrivningar; Manual har sin separata policy. Ingen tyst övergång till BF/BT vid RAPT-bortfall. Läs [Brewday-lägen](docs/brewday-execution-modes.md), [RAPT-kontrakt](docs/rapt-brewzilla-profile-runtime.md) och [aktuellt käll-/versionsförbehåll](docs/project-status-2026-09-20_sv.md); äldre designtexter kan vara historiska för den implementerade beta.14-versionen.

`custom_components/brewassistant/` innehåller integration, sensor-/policy-/runtimekod; `dashboard/cards/` innehåller manuella Lovelace-exempel som **inte** automatiskt installeras i en anpassad dashboard. Håll svenska/engelska kort synkade. Samordna installation med aktuell RCL-fork (beta.14-beroende `v0.5.0-beta.1`), rätt BA-tagg och säkerhetskopia; byt aldrig hela HA-integrationen från en äldre feature-branch mitt under parallellt arbete.

## Brancher och releaseprocess

```text
dev (gemensam utveckling) -> beta (integrerat test + prerelease) -> main (fältvaliderad stabil)
```

Normalt ska promotion ske med granskad PR, **Create a merge commit** och kvalitetskontroller på exakt resulterande beta-SHA innan en *ny*, oflyttad tagg publiceras. Beta.14 kom från en separat release-/featuregren via [PR #221](https://github.com/Jocke1970/brewassistant-beta/pull/221) och finns ännu inte återförd till `dev`. **Rekonciliera den skillnaden uttryckligen före nästa gemensamma releasearbete**, utan force-push eller återanvändning av taggar. `beta` har även en städcommit efter beta.14-taggen; installera taggen, inte ett antaget branch-head. `main` lämnas orörd tills lämplig fältacceptans och uttryckligt beslut. Se [CONTRIBUTING](CONTRIBUTING.md).

**Watchdogs:** CI (Python 3.11–3.13), Hassfest och HACS finns. Från 2026-09-20 triggas CI inte automatiskt av `dev`-push/PR; releasebrancher, `beta`, `main` och manuella körningar omfattas av det nya workflow-kontraktet. Avsaknad av en ny körning är inte ett godkänt test. Automatiska kontroller bevisar aldrig fysisk säkerhet.

## Dokumentationskarta: börja här

| Fråga | Dokument |
| --- | --- |
| **Aktuellt läge och prioriterade beslut** | [Status 2026-09-20](docs/project-status-2026-09-20_sv.md), [roadmap](docs/roadmap.md) |
| **Senaste publicerade BA och vattenprovsinstruktioner** | [Beta.14-release](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14), [taggade beta.14-anteckningar](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/beta14-prerelease-notes_sv.md), [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) |
| **HLT senaste fältbevis / tidigare prov** | [20 september](docs/hlt-sim1-field-validation-2026-09-20.md), [19 september](docs/hlt-sim1-field-validation-2026-09-19.md) |
| HLT kod, sensorer och dashboard | [Backend-README](custom_components/brewassistant/hlt/README.md), [sensoravtal](docs/hlt-dashboard-backend.md), [kortguide](docs/hlt-dashboard-card.md) |
| Brewday och BrewZilla | [Brewday-README](custom_components/brewassistant/brewday/README.md), [Brewday/BZ](docs/brewday-brewzilla.md), [execution modes](docs/brewday-execution-modes.md) |
| Observations-/ABORT-test | [Beta.14:s testguide](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/brewzilla-observe-only-test_sv.md) (innehåller äldre förrelease-status; följ publicerad release och 20/9-status) |
| Historisk beta.11-incident och tidigare fälttest | [BA-paus och RAPT-handoff](docs/ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md), [Mash-testplan](docs/physical-mash-test-plan-2026-09-19_sv.md), [validering 6/9](docs/physical-validation-2026-09-06.md) |
| Utvecklings-/releasekontrakt | [CONTRIBUTING.md](CONTRIBUTING.md), [Brewday Audit](docs/brewday-audit.md) |
| Backends och övriga moduler | [BrewZilla-backend](docs/backends/brewzilla-backend.md), [Cooling](docs/backends/cooling-backend.md), [Equipment Learning](docs/brewzilla-equipment-learning.md), [dashboard](docs/dashboard-baselines.md), [lokalisering](docs/localization.md) |

**Historik:** beta.10-taggen är felaktig för tidigare styrprov; beta.11:s Mash-In-vattenprov avbröts och blev inte godkänt. Beta.12 och beta.13 har egna oförändrade releaseanteckningar. [README-versionen före 20/9-synken](https://github.com/Jocke1970/brewassistant-beta/blob/94b3dbe5f9f62c76d3f847184fad9400b12d3a17/README.md) och daterade underlag ligger kvar för spårbarhet, men äldre ord som "nuvarande beta.12" och "CI på dev" är inte dagens driftinstruktioner.
