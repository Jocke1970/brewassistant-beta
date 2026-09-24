# BrewAssistant doc-sync 2026-09-24

Status: beta.15 release candidate + doc-sync  
Branch source: `dev`  
Intended promotion: `dev -> beta`

## Sammanfattning

Den här synken fångar BrewAssistants faktiska läge inför nästa promotion till `beta`.

Senaste publicerade prerelease före denna releasegrind är **v0.2.0-beta.14**. `dev` är nu förberedd som **v0.2.0-beta.15**. Beta.15 får publiceras först efter `dev → beta`-merge och gröna release-watchdogs på exakt beta-merge-SHA. `main` berörs inte.

Vid beta.15-förberedelsen hade `dev` och `beta` divergerat genom tidigare promotion-mergehistorik. Funktionsdiffen från beta till dev är nu GF30-fokuserad: read-only thermal/preflight-runtime, sensorer, passiv learning, dual-sensor safe-point, coolant-monitor-kontrakt samt integration wiring/tests/docs. Manifestet bumpas till `0.2.0-beta.15`.

## Beta.15-kod och dokumentationsdelta

Skillnaden `beta -> dev` bestod av:

- uppdaterad root-`README.md`;
- uppdaterad `fermentation_tracking/README.md`;
- uppdaterat backend-index;
- nya designnoter för GF30 thermal/control learning;
- nya designnoter för GF30 -> Brewfather outbound logging;
- kompletteringar i 22/9-statusdokumentet;
- uppdaterad roadmap.

GF30 thermal/preflight är nu **implementerad read-only**. Brewfather outbound-dokumentet är fortsatt design/planering. Ingen fysisk GF30-, pump-, frys- eller coolant-setpoint-styrning är implementerad.

## Rättad branch- och testmodell

BrewAssistant använder tre långlivade brancher:

```text
dev -> beta -> main
```

Operativ regel inför fysisk test:

```text
arbete + doc-sync på dev
        |
        v
promotion dev -> beta
        |
        v
CI / HACS / Hassfest / HA+RCL-smoke på beta
        |
        v
supervised HA-/vattenprov
        |
        v
eventuella fixar tillbaka på dev
```

`dev` är utvecklingsyta och ska inte automatiskt köra release-watchdogs. `beta` är den installerbara testkandidaten. Den avgörande automatiska valideringen ska därför läsas från den **faktiska beta-SHA:n efter promotion**.

Promotion guard gäller fortsatt:

- `beta` får endast ta emot promotion från `dev`;
- `main` får endast ta emot promotion från `beta`;
- permanent promotion använder **Create a merge commit**.

## GF30-status

`grainfather_fermenter/` finns i den ordinarie branchkedjan och är inte en separat featurebranch.

Beta.15-implementationen är fortsatt fail-passive/read-only men har utökats med:

- discovery/normalisering av Grainfather fermentation-device/session-data;
- persistent manuell/Pill-preflight via Home Assistant Store;
- read-only diagnostiksensorer och två manuella preflight-tjänster;
- passiv delta/rate-learning;
- dual Pill/internal safe-point där upstream `last_heard` prioriteras för intern freshness när möjligt;
- valfria tomma mappings för köldmedium, frysluft och coolant-`generic_thermostat`;
- inget Grainfather service call, ingen fysisk pump-/frys-/setpoint-styrning och ingen modellidentitet utan live-hårdvarubevis.

## Fermentation control ownership

Det generella kontraktet kvarstår:

```text
fermentation_tracking
  observations / readiness / desired beer target
        |
        v
selected physical provider
        |
        v
local controller
  owns actual heat/cool regulation
```

Nuvarande skrivbara provider är `fermentation_chamber`. En framtida `grainfather_fermenter`-provider får inte ges write authority förrän live GF30-service/readback och single-provider-authority har verifierats.

## Fysisk acceptans

Inget i den här doc-syncen ändrar tidigare säkerhetsstatus:

- beta.14 är publicerad;
- fysisk BrewZilla-vattenacceptans är fortfarande inte dokumenterad som PASS;
- fysisk OFF/ABORT-verifiering och full HA/RCL end-to-end återstår;
- HLT SIM-1 är fortsatt read-only simulator;
- GF30 saknar live-hårdvaruvalidering.

Gröna watchdogs efter promotion till `beta` är nödvändiga men ersätter inte fysisk validering.

## Nästa steg

1. Synka de här dokumentationsrättningarna på `dev`.
2. Granska hela `dev -> beta`-diffen.
3. Promota med PR och **Create a merge commit**.
4. Kör/läs CI, HACS, Hassfest och den isolerade HA+RCL-smoken på den resulterande beta-SHA:n.
5. Om automationerna är gröna, installera/testa exakt beta-kandidaten i Home Assistant enligt det aktuella supervised/water-only-kontraktet.
6. Vid fel: dokumentera fynd, rätta på `dev`, doc-synca vid behov och promota på nytt.
7. Efter gröna beta-watchdogs: skapa ny oflyttad tagg `v0.2.0-beta.15` på exakt beta-merge-SHA och publicera GitHub Pre-release. Ingen `beta -> main`.

## Dokument som synkats i samband med 24/9-checkpointen

- `README.md`
- `CONTRIBUTING.md`
- `docs/roadmap.md`
- `docs/backend-domain-layout.md`
- `docs/backends/README.md`
- `docs/doc-sync-2026-09-24_sv.md`

Workflow-synken 24/9 flyttar dessutom beta-valideringen till den faktiska promotion-SHA:n: vanliga watchdogs körs inte som acceptance-gate på `dev`, och HA+RCL-smoken triggas på `beta`-push efter merge.

Historiska daterade fältrapporter och publicerade releaseanteckningar ändras inte retroaktivt.
