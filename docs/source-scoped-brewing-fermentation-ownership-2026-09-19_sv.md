# Källbaserat styransvar – Brewing och Fermentation (beslut 2026-09-19)

**Status: fastställd målarkitektur; INTE verifierat implementerad.** Denna anteckning förtydligar och ersätter *endast arkitekturslutsatsen* i `ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md`. Observationerna från det avbrutna beta.11-testet och kravet på säkerhetsverifiering i den äldre anteckningen gäller fortfarande. Att dokumentationen är uppdaterad betyder inte att fysisk körning är godkänd.

## Ansvar per process och källa

| Process | Auktoritativ processkälla | BrewAssistant | Transport / utrustning |
| --- | --- | --- | --- |
| Brewing / Hot Side, RAPT vald | RAPT-profil: steg, temperaturdirektiv, tids-/stegövergångar | **Aktiv regulator:** temperaturmål, värme, pump, interlocks och operatörskvittens | RAPT Cloud Link transporterar BA-kommandon till BrewZilla |
| Brewing / Hot Side, Brewfather/Brew Tracker vald | Brewfather processdata, tills vidare förpassad till passiv observation | **Ingen BrewZilla-aktuatorskrivning** i BF-källäge: endast läsning, UI, loggning | Ingen BA-styrning av BrewZilla |
| Brewing / Hot Side, Manual | Manuell processkälla | Existerande manuell kontroll måste granskas separat; behåll tidigare säkerhetspolicy tills explicit beslut/test | RCL/BrewZilla när manuell kontroll är verifierat tillåten |
| Fermentation / Cold Side | Brewfather: jässteg och temperaturdirektiv | Reglerar jäskammarens värme/kyla enligt separat fermentationssäkerhet | Home Assistant / jäskammare |

Brewfather kan tillhandahålla receptmetadata under en RAPT-bryggning utan att därmed bli hot-side-processkälla. **Men BrewTrackers bryggsensorer får inte läsas ens som metadata, fallback eller diagnostik av BA:s brewing-flöde när RAPT är vald källa.** Fermentationens källa påverkar aldrig val av BrewZilla-regulator eller dess skrivbehörighet.

## Process- och styrkedja

```text
RAPT brewing profile -> BrewAssistant hot-side controller -> RAPT Cloud Link -> BrewZilla
Brewfather fermentation profile -> BrewAssistant fermentation controller -> fermentation chamber
Brewfather hot-side process -> BrewAssistant observer only (NO BrewZilla writes)
```

RAPT-profilen äger alltid själva stegövergången; BA får inte hitta på en Next/Continue-övergång eller starta koktimern. RCL är transport och rapporteringsyta, inte en konkurrerande BA-regulator. BrewZillas lokala skydd/funktion måste testas och får inte antas bekräftad av ett lyckat HA-serviceanrop.

## Nytt uttryckligt krav: inga BT-sensorläsningar när RAPT äger Brewing

- Välj brewing-källa **före** insamling av stegnamn, status, temperaturdirektiv, recept-/batchkontext, timers, audit och dashboarddata. Vid RAPT används bara aktuell RAPT-profil/telemetri, BA:s egna data och BrewZillas hardware-readback. BrewTracker-sensorer som `sensor.brewfather_brew_tracker_*` får inte anropas via `hass.states.get`, templates eller läsas som reservvärden av brewing-flödet.
- Vid saknad, ofullständig, stale eller motstridig RAPT-data: rapportera `unavailable`/blockera ny positiv styrning; växla **inte** tyst till BrewTracker. En tidigare RAPT-session eller BT-värde får inte ärvas.
- Undantaget gäller **Brewfather Fermentation och dess separata jäsprofil-/temperatursensorer**, inte BrewTracker-sensorerna. Jäsningen får fortsätta oberoende.
- Normaliserade `sensor.brewassistant_brewday_*` ska vara gemensam utgång till UI; backend ansvarar för källval och autentisering. BrewZillas temperatur, verkliga target, pump, heat och utilization läses fortsatt från RCL/BrewZilla eftersom det är **fysisk readback**, inte BT.
- Konkreta läckor som identifierats i feature-granskning: `brewzilla_learning._batch_context_snapshot` läser `_brewfather_batch_context` ovillkorligt; `brewday_audit_autostart` läser BT-status oberoende av runtime-källa; `brewfather_batch_phase` sensorn och `dashboard/cards/brewtracker_runtime*.yaml` använder BF/BT-tillstånd utan en RAPT-source exclusion. `_operator_aborted_snapshot` i `brewday_runtime.py` anropar BF-core trots RAPT ABORT. Detta är identifierade fel, **inte ännu tätade bara av detta dokument**.
- Acceptanstest: kör all tillgänglig brewing-kod med simulerad aktiv/otillgänglig RAPT-profil och en `hass.states.get`-fälla som räknar eller avvisar ALLA `sensor.brewfather_brew_tracker_*`/`sensor.brewfather_brewtracker_*`-läsningar. Verifiera noll läsningar på bryggflödet inklusive Learning, audit, källa, dashboards och ABORT; BF Fermentation ska fortfarande kunna läsa sina separata jässensorer. Ingen fysisk utrustning behövs för detta test.

## Sparge, endast när RAPT är giltig brewing-källa

1. `Mash Out -> Sparge`: BA känner igen ett exakt RAPT-steg `Sparge` / `Lakning`. Ny sessionsbunden tillståndsmaskin börjar i `awaiting_lift`; pump och värme ska föras till säkert av-läge. Inga positiva kommandon från tidigare steg får överleva.
2. Efter att den fysiska pump-/värmestoppstatusen verifierats får operatören hantera och lyfta maltpipan. BA får inte dra slutsatsen att lyftet är klart av tidsförlopp, stegnamn eller temperatur.
3. Operatören kvitterar *specifikt* att maltpipan är säkert upplyft och att elementen täcks av vört. BA övergår till `heat_to_boil`, med pump OFF; BA:s uppvärmning till kok omfattas av ordinarie övervakad positiv aktivering. Lokal RAPT-profil/target får inte samtidigt skriva ett konkurrerande nytt temperaturmål; detta ska valideras innan aktiv drift.
4. När lakning/avrinning och förkokvolym är klara avancerar operatören **RAPT-profilen** manuellt till Boil. BA får inte själv flytta RAPT-steget.
5. Avbrott, profil-/sessions-/stegbyte, förlorad auktoritet, omstart och ABORT ogiltigförklarar den tidigare lyftkvittensen. Ingen automatisk återstart av värme. Skilj mellan *ingen ny BA-skrivning* vid osäker telemetri och faktisk fysisk OFF; UI får aldrig beskriva det förra som det senare.

**OBS:** Ovan beskriver önskat beteende, inte ett godkänt schema för dagens utrustning. Kontroll av RAPT:s egna lokala styrning vid manuellt steg är ett separat fysiskt integrationskrav.

## Skrivgränser som måste verifieras före fysisk drift

- En källa måste vara identifierad och aktuell för just brewing-processen. `unavailable`, återställda entity-värden, tvetydig källa eller förlorad session innebär inga nya positiva hot-side-kommandon eller tyst BF-fallback.
- BF hot-side observer: stoppa *alla* BA-vägar till BrewZilla: target, heater, pump, båda utilisation, reassert, STOP-handoff, direkta tjänster/knappar och gamla pending-planer. Separera en explicit hårdvaru-nödåtgärd från ordinär automatisk källväxling; inga påståenden om fysisk OFF utan kvittens.
- RAPT hot-side aktivt: inga BF-/Manual-kommandon får dela eller ärva ägarskap. Supervised Apply kräver färsk sessions-/steg-/källa-identitet vid både planering och bekräftelse; ABORT och hårdsäkerhet vinner.
- Jäsningens BF-direktiv påverkar endast fermentationskontroll. Säkerställ med regression att ingen hot-side-service anropas av fermentationshändelser.
- Verifiera alla existerande skrivvägar centralt – att ändra ett dashboardkort eller kontrollera `monitor` i en sensor är inte en teknisk skrivspärr.

## Releaseordning (obligatorisk)

1. Arbeta på `feature/*` från aktuell `dev`; öppna PR mot `dev`. Inga direkta ändringar på `beta` eller `main`.
2. Kodgranskning, simulering/utan fysisk utrustning, CI, HACS, Hassfest och regression för källbyte, BT-läsisolering, Sparge, omstart, ABORT, återanslutning och fermentation. Slå inte ihop en PR vars säkerhetskrav inte klarats.
3. Efter godkänd `dev`: PR `dev -> beta`. Ny prerelease endast från verifierad beta-commit; äldre taggar ändras inte. **Användarens release-först-ordning:** fysisk supervised water-only-verifiering sker först efter publicerad prerelease och installerad beta; ingen fysisk provkörning före release.
4. `beta -> main` först efter separat uttryckligt godkännande och verifierad stabil drift. Inga automatiska mergar eller releasepåståenden från gröna CI-checkar ensamma.

**Första implementationstegen:** (a) central auktoritets-/skrivgräns per hot-side-källa, (b) noll BT-läsningar under RAPT brewing, (c) BF passiv isolering, (d) sessionsbunden Sparge-interlock och svensk/engelsk status/kvittens, (e) jäsningsregression. Inget av detta är verifierat enbart genom detta dokument.