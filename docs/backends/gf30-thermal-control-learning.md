# GF30: DIY-kylning, köldmediestyrning och thermal learning – arkitekturkontrakt

Status: **delvis implementerad read-only på `dev`**. Thermal preflight, persistent manuell/Pill-historik, passiv rate-learning, dual-sensor safe-point och ett rent coolant-monitor-kontrakt finns 2026-09-24. Ingen frys-, pump-, climate- eller GF30-write är implementerad.

Relaterat: [GF30-fermenterroadmap](grainfather-fermenter.md), [fermentation tracking](../sg-driven-fermentation.md), [`fermentation_chamber/` README](../../custom_components/brewassistant/fermentation_chamber/README.md) och [`grainfather_fermenter/` README](../../custom_components/brewassistant/grainfather_fermenter/README.md).

## Implementerat 2026-09-24 – thermal preflight

`custom_components/brewassistant/grainfather_fermenter/thermal.py` kan redan nu jämföra en RAPT Pill-temperatur med en manuellt avläst referenstemperatur. Båda observationerna tidsstämplas, stale/ogiltiga värden underkänns, delta beräknas och resultatet märks som learning-eligible endast när båda är färska och rimliga. Avvikelse väljer aldrig automatiskt en vinnande sensor. Vägen är strikt read-only med `control_allowed: false` och innehåller inga Home Assistant-serviceanrop.

Detta är avsett för de första kyl-/vattentesterna innan GF30:s Wi-Fi/controllerdata finns tillgänglig. Nästa sensorsteg efter Wi-Fi är att lägga till GF30:s interna temperatur som en andra permanent öltemperaturkälla; den manuella referensen förblir test-/kalibreringsunderlag.

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

- **GF30 äger pumpen.** BA skickar inga pumpkommandon, bygger inga pumpautomationer och försöker inte ersätta GF30:s lokala kylningslogik. `binary_sensor.grainfather_gf30_cooling = on` får användas som **GF30 cooling-command / expected pump activity**: controllern begär kylning och pumpen förväntas vara aktiverad. Det är däremot inte fysisk flödesverifiering. Utan flödesmätare kan BA inte bevisa att pumpen snurrar, att slangar är anslutna eller att kylvätska faktiskt cirkulerar.
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
| GF30 cooling-status | `binary_sensor.grainfather_gf30_cooling`; cooling-command / expected pump activity | `on` betyder att GF30 är i kylstatus och förväntas ha aktiverat pumpen. Det bevisar inte fysiskt flöde eller anslutna slangar. |

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
- BA v1 har read-only/learning mot `generic_thermostat`; ändrar varken dess setpoint, HVAC-läge eller frysbrytare.
- **Beslutad framtida målmodell:** reservoaren ska inte hållas permanent så kall som möjligt. BA ska i stället beräkna en dynamisk köldmedietarget relativt GF30:s aktuella ölbörvärde och fas:

```text
coolant_target = gf30_beer_target - adaptive_cooling_headroom
coolant_target = clamp(coolant_target, verified_min_safe, verified_max_useful)
```

  Målet är den **varmaste köldmedietemperatur som fortfarande ger GF30 tillräcklig kylkapacitet**. Stabil jäsning, aktiv temperatursänkning och cold crash får ha olika headroom. Learning får senare föreslå/justera headroom endast från validerad fysisk data. GF30 äger fortsatt kylbehov och pump; BA får inte skapa en parallell pumpregulator.
- En framtida aktiv setpoint-funktion får endast ändra `generic_thermostat`-target inom verifierade medium-/frysgränser. Den kräver separat explicit kvittering och testad validering; inga självjusteringar från learning innan den grinden passerats.

Referens: https://www.home-assistant.io/integrations/generic_thermostat/ . Plattformens konfigurationsmöjligheter är inte bevis för verklig OFF-funktion hos användarens frys.

## 5. Thermal learning v1: två ölkurvor och en mediumkurva

Beräkna endast från tidsstämplade, färska och rimliga observationer, utan att reglera hårdvaran:

- Pill–GF30-delta, varaktighet, trend, placerings-/kalibreringsindikation och safe-point-status;
- separat temperaturändring °C/h för Pill respektive GF30-intern under kyla/vila/värme; uppskatta inte sann temperatur genom okalibrerat medelvärde;
- tidsfördröjning från GF30 cooling-command till termisk respons. `binary_sensor.grainfather_gf30_cooling` får användas som startpunkt för observationsfönstret, men inte som flödesbevis;
- eftersläpning/overshoot i båda ölkurvorna, reservoarens värmeupptag och återhämtning, frysluft/vätske-delta;
- verkligt bekräftade frysbrytar-/effektsignaler, kompressorcykler och drifttid; ETA med `unknown` eller låg konfidens vid otillräckliga data.

Logga råa mätvärden och faktiska timestamps/entiteter, freshness, batch och volym om kända, medium och blandning, aktuella börvärden, styrningens/readback-status, läge, modellversion, sampelantal och osäkerhet. Träna inte på stale/unknown, disagreement, manuell override, saknad aktorkvittens, batch-/mediumbyte eller strömavbrott. Vattenkalibrering, jäsning och cold crash är olika experiment/profiler.

Visa `learning_status`, `sample_count`, `confidence`, `reason`, `pill_temperature_c`, `gf30_internal_temperature_c`, `beer_sensor_delta_c`, `safe_point_status`, `coolant_temperature_c`, fryslufttemperatur och verifierat frysstatus. Eventuella förslag gäller i v1 operatören; inga automatiska klimat- eller GF30-åtgärder.

## 5A. Cooling-command, förväntad pumpaktivitet och termisk respons

Beslut 2026-10-04: BrewAssistant ska inte försöka skapa en falsk binär sanning som heter "pump verified" utan flödesmätare. I stället modelleras kylkedjan i separata nivåer:

```text
GF30 cooling-command
  -> binary_sensor.grainfather_gf30_cooling = on
  -> pump förväntas vara aktiverad

Physical flow
  -> inte direkt verifierbart utan flödesmätare

Thermal response
  -> observeras via coolant- och GF30/vörttemperatur över tid
```

Det innebär att `binary_sensor.grainfather_gf30_cooling` **får** användas som signalen "cooling commanded / expected pump active", men aldrig som bevis för att:

- pumpmotorn faktiskt snurrar;
- slangarna är anslutna;
- kylvätska finns i kretsen;
- vätskan cirkulerar;
- eller att värmeöverföring faktiskt sker.

### Empirisk GF30-effektsignatur

Fältobservation 2026-10-04 från Home Assistant-effektgrafen för GF30 visar tre tydligt separerade nivåer:

```text
Tomgång / elektronik: cirka 1 W
Kylpump aktiv:       cirka 6 W total GF30-effekt
Värmare aktiv:       cirka 30–31 W total GF30-effekt
```

Pumpens elektriska signatur motsvarar därmed ungefär **+5 W över tomgång** i den observerade installationen. Grafen visar en längre stabil platå nära 6 W som är tydligt skild från både tomgångsnivån och värmarens cirka 30 W.

Detta gör GF30-effekt till en användbar sekundär observationssignal:

```text
GF30 cooling = ON
  -> pump expected active

GF30 power nära observerad pumpplatå (~6 W)
  -> pump electrical signature observed

coolant temperature stiger efter termisk fördröjning
  -> heat transfer / circulation strongly indicated

GF30/vörttemperatur sjunker
  -> process cooling response observed
```

Effektsignaturen är **inte fysisk flödesmätning**. Den kan ge stark evidens för att pumpens elektriska last är aktiv, men kan inte ensam bevisa att slangar är anslutna, att kylvätska finns eller att vätskan faktiskt cirkulerar.

Värdena cirka 1 W / 6 W / 30–31 W är initiala empiriska observationer från den aktuella GF30-installationen och ska samlas in över flera ON/OFF-cykler innan de används som fasta klassificeringsgränser. Framtida klassificering bör använda intervall/hysteres snarare än exakt likhet med 6 W.

### Förväntad första termiska respons

I den nuvarande installationen sitter `sensor.glycolchiller_liquid` i reservoaren. När GF30 går till cooling och kylvätska börjar cirkulera genom den varmare GF30-manteln förväntas den första tydliga processresponsen normalt vara att **kylvätskan i reservoaren börjar stiga i temperatur**.

Den förväntade ordningen är därför:

```text
1. GF30 cooling = ON
2. coolant temperature börjar stiga
3. GF30/vörttemperatur börjar därefter sjunka
```

Detta är en fysikalisk observationsmodell, inte ett bevis på en enskild komponent. En stigande coolant-temperatur efter cooling-command är dock stark indirekt evidens för att kylkretsen tar upp värme från GF30.

### Observationsfönster

En mätbar coolant-respons förväntas inte nödvändigtvis omedelbart. Som **fält-testhypotes** används initialt cirka **5–10 minuter** efter att GF30 går till cooling innan frånvaro av coolant-respons börjar betraktas som diagnostiskt intressant.

Detta intervall är inte en verifierad konstant och ska inte hårdkodas som säkerhetsgräns innan verklig testdata finns. Påverkande faktorer inkluderar bland annat:

- reservoarvolym;
- starttemperaturer;
- temperaturskillnad GF30 ↔ coolant;
- pumpflöde;
- slanglängd och isolering;
- kylmantelns värmeöverföring;
- fryseffekt;
- sensorupplösning och uppdateringsintervall.

Framtida read-only diagnostik bör därför kunna uttrycka tillstånd i stil med:

```text
idle
cooling_commanded
waiting_for_thermal_response
coolant_response_observed
process_cooling_observed
cooling_chain_responding
no_thermal_response_observed
```

`no_thermal_response_observed` får inte automatiskt översättas till "pumpfel". Möjliga orsaker kan vara pump, slangar, luft i kretsen, saknad kylvätska, otillräcklig temperaturskillnad, sensorplacering eller annan fysisk orsak.

### Tvåfasidé för framtida cold-crash-styrning

Följande är dokumenterad **designhypotes för senare validering**, inte implementerad styrning:

**Fas 1 – snabbnedkylning, ungefär från jäsningstemperatur ner mot +6 °C**

- GF30 cooling-command förväntas innebära kontinuerlig pumpdrift.
- Liquid Cooler/frys bör kunna förberedas samtidigt som kylningen startar för att möta värmelasten proaktivt.
- +6 °C behandlas som en initial testparameter, inte som en fysikalisk naturkonstant.

**Fas 2 – lågtemperatur/inversionsområde, ungefär under +6 °C**

- framtida processbedömning kan behöva använda `max(T_top, T_bottom)` för att kräva att hela vätskevolymen når målet;
- pulserad pumpidé, initial testparameter: cirka 2 min ON / 6 min OFF;
- lågtemperaturguard, initial testparameter: cirka +1,5 °C på någon relevant öltemperaturgivare.

Dessa värden är **inte verifierade** för GF30-installationen och får inte betraktas som produktionssäkra innan fälttest. Framför allt får +1,5 °C inte beskrivas som att den "eliminerar all risk för isbildning"; sensorplacering, mätfel, lokala kalla zoner och tidsfördröjning gör ett sådant absolut påstående omöjligt.

För framtida dual-sensor-logik måste `T_top` och `T_bottom` först kopplas till **fysiskt verifierade sensorplaceringar**. RAPT Pill flyter och kan vara kandidat för övre vätsketemperatur, men ingen annan befintlig temperaturkälla får automatiskt kallas "bottom" utan fysisk verifiering.

## 6. Cold crash och säkerhetsansvar

- `fermentation_tracking` ger cold-crash-readiness; kräver operatörens särskilda cold-crash-bekräftelse och separat kvittens av skydd mot luftsug. Ingen automatisk cold-crash-start från SG/tid/safe-point/learning.
- GF30:s lokala styrning och pump får inte förbigås. Köldmediet kan hållas redo separat via sin egen säkert konfigurerade regulator, men BA får inte tolka ett färdigt medium som ett tillstånd att sänka GF30:s ölbörvärde.
- Vid Pill/cloud/HA-problem: ingen automatisk ny GF30-måländring, ingen dold fallback, ingen återspelning av gammal kylbegäran och ingen learning-aktivering av pump/frys.
- Lager: (1) mediumets fysiska frys-/pump-/kompressorskydd, (2) HA:s `generic_thermostat` som enda frysägare, (3) GF30:s interna öl-/pumpreglering, (4) BA:s jämförelse och learning. Två öltemperaturgivare är en diagnostisk safe-point, **inte** bevis för oberoende nödstopp eller mediumsäkerhet.
- Skilj `command_sent`, HA-readback och **fysisk verifiering**. Varken cloud-ACK eller HA `off` bevisar avstängd pump/kompressor.

## 7. Faser och acceptans

1. **Kartläggning/read-only:** valfria BA-mappings för köldmedium, frysluft och `generic_thermostat` är implementerade; identifiera och välj verkliga entity-ID när hårdvaran finns. Verifiera därefter GF30:s interna givares åtkomst, Pill-uppdateringar, thermostat/readback och att GF30 lokalt sköter pump utan konkurrerande BA-automation.
2. **Dual-sensorprov:** jämför Pill och GF30-intern i tempererat, termiskt utjämnat vatten och därefter kontrollerad kylning; välj tolerans, sampling/timeout och safe-point-logik empiriskt. Dokumentera om HA exponerar pump-/kylbegäransstatus.
3. **Köldmedieprov:** validera mediets fryspunkt, representativ mätpunkt, kompressorcykler och faktisk freezer-OFF under sensorstale, restart, smartplug- och HA-bortfall; verifiera oberoende failsafe där så krävs. Varje prov börjar med explicit kontroll att YAML/integration har lästs om, att `generic_thermostat` faktiskt är aktiv, att rätt target-sensor används och att thermostatens target/HVAC-state/readback är rimliga **innan frysen energiseras**.
4. **Learning read-only:** sensordata + råhistorik, separata trender och modellkonfidens, regressioner för disagreement/stale/omstart/pump-unknown och mode-skiften; inget actuator-API.
5. **Eventuell supervised setpoint:** ett separat senare beslut efter fysisk bekräftelse och explicit operator-confirmation. GF30-ölbörvärdesbrygga från äldre roadmap blandas inte ihop med DIY-reservoarens börvärde. Ingen BA-pumpstyrning.
6. **Fullcykeltest:** vatten → riktig batch → normaljäsning → verifierat FG → kvitterad cold crash och bortfallsprov. Automatisk learning-styrning är inte ett v1-krav.

Öppet före fysisk inkoppling: de verkliga entity-ID:na och deras freshness, kalibrerings-/delta-tolerans, vald köldmedieblandning/fryspunkt, faktisk fail-off, kompressortider och eventuell pumptelemetri. BA-options har nu tomma, valfria mappings för köldmediegivare, frysluftgivare och coolant-`generic_thermostat`; inga entity-ID gissas eller fabriceras.

## 8. Dokumentationsregler

Den äldre [GF30-roadmapen](grainfather-fermenter.md) beskriver read-only cloud-discovery och en eventuell framtida supervised GF30-profil-target. Det här kontraktet gäller den av användaren beslutade **DIY-kretsen med GF30-autonom pump och köldmediestyrd frys**. Vid faktisk kodimplementation uppdateras kodlokal README, relevanta testplaner och UI-handbok. Read-only-koden ligger nu på `dev`; fysisk sensor-/frys-/GF30-validering återstår och inga releasepåståenden görs innan tester och fältprov är genomförda.
