# GF30: DIY-kylning, köldmediestyrning och thermal learning – arkitekturkontrakt

Status: **planerad utbyggnad av befintlig `grainfather_fermenter/`, dokumentation endast**. Inga nya sensorer, reglage, kommandon, HA-konfigurationer eller tester är implementerade av detta dokument. Skapad och förtydligad 2026-09-22.

Relaterat: [GF30-fermenterroadmap](grainfather-fermenter.md), [fermentation tracking](../sg-driven-fermentation.md), [`fermentation_chamber/` README](../../custom_components/brewassistant/fermentation_chamber/README.md) och [`grainfather_fermenter/` README](../../custom_components/brewassistant/grainfather_fermenter/README.md).

## 1. Beslutad avgränsning

GF30 Conical Fermenter används med **både RAPT Pill-temperatur och GF30:s interna temperaturgivare samtidigt**. De är två aktiva observationer och en sensoröverenstämmelse-/safe-point-kontroll, inte en ordning där Pill alltid är primär och den interna givaren bara används som reserv. Två givare förbättrar felupptäckt men ger inte automatiskt två oberoende säkra styrkanaler; kalibrering, placeringsskillnader, dataålder och felmoder behöver valideras.

**Användarens driftbeslut:** GF30:s inbyggda regulator styr cirkulationspumpen automatiskt utifrån sin egen interna logik. BrewAssistant ska **inte** styra pumpen och behöver i denna DIY-konfiguration i första hand reglera **köldmediets temperatur** via frysen, plus observera GF30/Pill och beräkna learning/diagnostik. Skilj detta från ett separat eventuellt framtida, uttryckligt och kvitterat byte av GF30:s ölbörvärde genom en validerad Grainfather-yta; det är *inte* en del av köldmediestyrningen v1.

En separat sensor mäter frysluft, en separat sensor mäter köldmediet. Home Assistant `generic_thermostat` äger frysens brytare och använder köldmediet som reglerad storhet. Learning observerar och föreslår, men skickar inga kommandon. När köldmediet håller rätt temperatur kan GF30 själv ta kyla genom att starta sin pump vid behov.

Befintlig `custom_components/brewassistant/grainfather_fermenter/adapter.py` är en read-only discovery-adapter. Bygg vidare på *samma* fermenterdomän, inte en andra konkurrerande GF30-backend. Reserverade `grainfather` gäller bryggverk som G30/G40 (hot-side), inte GF30. Upstream-modellidentifiering, lokala entitets-ID och fysisk status måste verifieras före anslutning.

## 2. Ägarskap: en ölregulator och en separat köldmedieregulator

```text
fermentation_tracking
  -> recept-/SG-/dagschema och önskat öltemperaturmål (råd)
  -> inga direkta kommandon till frys eller GF30-pump
                 |
                 v
GF30 grainfather_fermenter (observerar, jämför, lär)
  Pill temp --------------+---> två aktiva mätningar
  GF30 intern temp -------+---> delta / trend / sanity-check / safe-point
                 |
   GF30:s egen regulator äger sin interna ölstyrning
   och startar/stannar cirkulationspumpen automatiskt.
                 |
             kylmantel <--- cirkulerande köldmedium <--- reservoar i frys
                                                          ^
                                                          |
                             generic_thermostat (cool) i Home Assistant
                             target_sensor = köldmediegivare
                             heater = dedikerad frysbrytare
                             ensam ägare av frysens ON/OFF

Frysluftgivare --> observation, anomalier, kompressor-/learning-diagnostik
Learning ------> read-only rekommendation och osäkerhet; inga writes
```

- **GF30 äger pumpen.** BA skickar inga pumpkommandon, bygger inga pumpautomationer och försöker inte ersätta GF30:s lokala kylningslogik. Pumpstatus kan läsas om verklig HA-telemetri finns; annars rapporteras `unknown`, aldrig antagen `on`.
- **`generic_thermostat` äger frysen.** Varken BA eller andra automationer skriver direkt till samma frysbrytare. BA ska först bara läsa temperatur, börvärde, HVAC/status och verifierad aktorfeedback.
- **Två olika reglerstorheter:** GF30 arbetar mot öltemperaturen; frysen arbetar mot köldmediets temperatur. Köldmediets börvärde får inte härledas som om det vore samma värde som ölets börvärde.
- Tidigare `fermentation_chamber` får inte samtidigt applicera ett konkurrerande mål på samma fysiska GF30-batch. Provider-/målauktoritet är explicit och fail-passive. Ett eventuellt senare GF30-profilbörvärde hanteras som en *separat* verifierad, kvitterad providerfunktion enligt [GF30-roadmapen](grainfather-fermenter.md), inte som en bieffekt av learning.
- Byte till Grainfathers kylare ersätter DIY-frys-/reservoarregulatorn efter ny validering men ska inte ändra tracking, sensoröverenstämmelse eller det generella learning-gränssnittet.

## 3. Sensorer, sensorfusion och safe-point

| Signal | Roll | Verifiering |
| --- | --- | --- |
| RAPT Pill temperature | Aktiv öltemperaturmätning och separat trend | Konfigurerad entitet, rimlig °C, äkta mättid/färskhet. Flyter; kan mäta annan plats än intern givare. |
| GF30 intern temperatur | Aktiv öltemperaturmätning, regulatorns lokala referens och separat trend | Verifiera faktisk HA-entitet, sensorns placering, uppdateringsintervall, last-heard och readback. |
| Köldmedietemperatur | **Enda planerade processgivaren för frysbörvärdet** | Representativ vätskeplacering, kalibrering, freshness och verifierad användning i `generic_thermostat`. |
| Fryslufttemperatur | Luft/vätske-delta, diagnostik och learning | Egen givare; får aldrig förväxlas med köldmedietemperatur. |
| Freezer climate/switch/ev. effekt | Regleringens faktiska status, kompressorcykler och energimodell | Verifiera entity/readback; önskat `on` betyder inte fysisk kompressor ON. |
| GF30 pump/kylbegäran (om exponerad) | Endast observations-/modellunderlag | Verifiera faktisk signal; saknas den visas `unknown`, ingen gissad pumpstyrning. |

**Normalfall:** logga båda öltemperaturerna med egna timestamps, visa Pill, intern GF30, `delta = Pill - GF30` och båda trenderna. Använd båda för plausibilitetskontroll och lärdata; ersätt dem inte tyst med medelvärde eller en påstådd sann temperatur. Temperaturmålets ägare och vilken temperatur GF30-regulatorn *faktiskt* styr på ska framgå separat.

**Safe-point-kriterier att validera:** båda källorna uppdateras i tid, ligger inom rimligt temperaturintervall, är kalibrerade mot varandra under stabila förhållanden och differensen hålls inom en *empiriskt vald tolerans* över ett verifierat tidsfönster. Under aktiv kylning/uppvärmning kan fysisk placering och värmetröghet skapa legitimt delta; toleransen får inte hårdkodas innan vattenprov/kylningsprov. Safe-point ska ha `ok`, `degraded`, `disagreement` eller `unknown` med källålder/orsak; `ok` kräver evidens, inte bara att två HA-states finns.

**En öltemperaturkälla stale/unknown:** safe-point blir `degraded`; behåll senast bekräftade BA-mål, varna och stoppa BA:s nya automatiska måländringar samt learning som kräver två givare. GF30:s lokala temperaturreglering får fortsätta enligt sitt eget verifierade säkerhetsbeteende; BA får inte anta eller fjärraktivera dess pump. Använd inte tyst den andra givaren som auktoritativ fallback. Beslut om eventuellt fortsatt drift med endast intern GF30-sensor och dess verkliga inbyggda skydd behöver fysisk validering.

**Två färska men motstridiga öltemperaturer:** `disagreement`, ingen dold omröstning/medelvärdesstyrning, varning, pausa BA:s nya måländringar och undanta segmentet från learning. Det betyder inte automatiskt att `generic_thermostat` måste kapa reservoarens kyla om dess egen köldmediegivare och säkerhetssystem är friska; nöd-/säkerhetsåtgärder för faktisk fara måste däremot ha en separat, testad väg. Skillnaden mellan diagnos, rekommendation och fysisk åtgärd ska framgå.

**Köldmediegivare stale/unknown:** stoppa/säkra frysens kylbegäran enligt *verifierad* fail-safe och larma. `generic_thermostat`-beteendet måste provas för oförändrat gammalt värde (HA state kan se normalt ut), unavailable, HA-omstart, förlorad smartplug och strömavbrott. Om mjukvara/brytare inte säkert kan stänga av frysen krävs oberoende fysisk skyddsgräns. Dual öltemperaturgivare är **inte** ett substitut för köldmediets lågtemperaturskydd.

## 4. Kylkrets och `generic_thermostat`

- Konfigurera `generic_thermostat` i kylläge (`ac_mode: true`) med köldmediets vätskesensor som `target_sensor` och den enda dedikerade frysbrytaren som `heater`-konfigurationsfält. Frysluftgivaren är separat diagnostik, inte primär kylregulator.
- Starta med frysstyrningen `off` tills givare, medium, fysisk installation, kompressorskydd, eventuell oberoende failsafe och operatörstester är godkända. Exakta entity-ID, börvärden och toleranser väljs först efter att hårdvara och medium är kända.
- Skydda kompressorn från kortcykling med rekommenderade intervall för den faktiska frysen och verifiera även efter HA-omstart/strömavbrott. Mjukvarutidtagare ensamt är inte oberoende hårdvaruskydd.
- Mediumets **verkliga** fryspunkt, koncentration och flödes-/pumpgränser måste verifieras; vatten får inte antas fungera vid minusgrader. Köldmediebörvärde och gränser ska vara skilda från öltemperatur och cold-crash-mål.
- BA v1 har read-only/learning mot `generic_thermostat`; ändrar varken dess setpoint, HVAC-läge eller frysbrytare. En framtida aktiv setpoint-funktion kräver separat explicit kvittering och testad validering inom säkra gränser; inga självjusteringar från learning.

Referens: https://www.home-assistant.io/integrations/generic_thermostat/ . Plattformens konfigurationsmöjligheter är inte bevis för verklig OFF-funktion hos användarens frys.

## 5. Thermal learning v1: två ölkurvor och en mediumkurva

Beräkna endast från tidsstämplade, färska och rimliga observationer, utan att reglera hårdvaran:

- Pill–GF30-delta, varaktighet, trend, placerings-/kalibreringsindikation och safe-point-status;
- separat temperaturändring °C/h för Pill respektive GF30-intern under kyla/vila/värme; uppskatta inte sann temperatur genom okalibrerat medelvärde;
- tidsfördröjning från verifierad pump-/kylbegäran till respektive temperaturrespons **bara om pump-/begäransstatus faktiskt exponeras**;
- eftersläpning/overshoot i båda ölkurvorna, reservoarens värmeupptag och återhämtning, frysluft/vätske-delta;
- verkligt bekräftade frysbrytar-/effektsignaler, kompressorcykler och drifttid; ETA med `unknown` eller låg konfidens vid otillräckliga data.

Logga råa mätvärden och faktiska timestamps/entiteter, freshness, batch och volym om kända, medium och blandning, aktuella börvärden, styrningens/readback-status, läge, modellversion, sampelantal och osäkerhet. Träna inte på stale/unknown, disagreement, manuell override, saknad aktorkvittens, batch-/mediumbyte eller strömavbrott. Vattenkalibrering, jäsning och cold crash är olika experiment/profiler.

Visa `learning_status`, `sample_count`, `confidence`, `reason`, `pill_temperature_c`, `gf30_internal_temperature_c`, `beer_sensor_delta_c`, `safe_point_status`, `coolant_temperature_c`, fryslufttemperatur och verifierat frysstatus. Eventuella förslag gäller i v1 operatören; inga automatiska klimat- eller GF30-åtgärder.

## 6. Cold crash och säkerhetsansvar

- `fermentation_tracking` ger cold-crash-readiness; kräver operatörens särskilda cold-crash-bekräftelse och separat kvittens av skydd mot luftsug. Ingen automatisk cold-crash-start från SG/tid/safe-point/learning.
- GF30:s lokala styrning och pump får inte förbigås. Köldmediet kan hållas redo separat via sin egen säkert konfigurerade regulator, men BA får inte tolka ett färdigt medium som ett tillstånd att sänka GF30:s ölbörvärde.
- Vid Pill/cloud/HA-problem: ingen automatisk ny GF30-måländring, ingen dold fallback, ingen återspelning av gammal kylbegäran och ingen learning-aktivering av pump/frys.
- Lager: (1) mediumets fysiska frys-/pump-/kompressorskydd, (2) HA:s `generic_thermostat` som enda frysägare, (3) GF30:s interna öl-/pumpreglering, (4) BA:s jämförelse och learning. Två öltemperaturgivare är en diagnostisk safe-point, **inte** bevis för oberoende nödstopp eller mediumsäkerhet.
- Skilj `command_sent`, HA-readback och **fysisk verifiering**. Varken cloud-ACK eller HA `off` bevisar avstängd pump/kompressor.

## 7. Faser och acceptans

1. **Kartläggning/read-only:** identifiera alla verkliga entity-ID, GF30:s interna givares åtkomst, Pill-uppdateringar, köldmedium, frysluft, `generic_thermostat` och freezer switch; dokumentera att GF30 lokalt sköter pump och att ingen BA-automation konkurrerar.
2. **Dual-sensorprov:** jämför Pill och GF30-intern i tempererat, termiskt utjämnat vatten och därefter kontrollerad kylning; välj tolerans, sampling/timeout och safe-point-logik empiriskt. Dokumentera om HA exponerar pump-/kylbegäransstatus.
3. **Köldmedieprov:** validera mediets fryspunkt, representativ mätpunkt, kompressorcykler och faktisk freezer-OFF under sensorstale, restart, smartplug- och HA-bortfall; verifiera oberoende failsafe där så krävs.
4. **Learning read-only:** sensordata + råhistorik, separata trender och modellkonfidens, regressioner för disagreement/stale/omstart/pump-unknown och mode-skiften; inget actuator-API.
5. **Eventuell supervised setpoint:** ett separat senare beslut efter fysisk bekräftelse och explicit operator-confirmation. GF30-ölbörvärdesbrygga från äldre roadmap blandas inte ihop med DIY-reservoarens börvärde. Ingen BA-pumpstyrning.
6. **Fullcykeltest:** vatten → riktig batch → normaljäsning → verifierat FG → kvitterad cold crash och bortfallsprov. Automatisk learning-styrning är inte ett v1-krav.

Öppet före implementation: uppmätta entiteter och freshness, kalibrerings-/delta-tolerans, vald köldmedieblandning/fryspunkt, faktisk fail-off, kompressortider och eventuell pumptelemetri. Inga gissade värden eller fabricerade entiteter.

## 8. Dokumentationsregler

Den äldre [GF30-roadmapen](grainfather-fermenter.md) beskriver read-only cloud-discovery och en eventuell framtida supervised GF30-profil-target. Det här kontraktet gäller den av användaren beslutade **DIY-kretsen med GF30-autonom pump och köldmediestyrd frys**. Vid faktisk kodimplementation uppdateras kodlokal README, relevanta testplaner och UI-handbok. Endast dokumentation i detta steg, på `dev`; inga test-/releasepåståenden utan körda tester.
