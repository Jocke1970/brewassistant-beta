# GF30: DIY-kylning, temperaturkontroll och learning – arkitekturkontrakt

Status: **planerad utbyggnad av befintlig `grainfather_fermenter/`, dokumentation endast**. Inga nya sensorer, reglage, kommandon, HA-konfigurationer eller tester är implementerade av detta dokument. 2026-09-22.

Relaterat: [GF30-fermenterroadmap](grainfather-fermenter.md), [fermentation tracking](../sg-driven-fermentation.md), [`fermentation_chamber/` README](../../custom_components/brewassistant/fermentation_chamber/README.md) och [`grainfather_fermenter/` README](../../custom_components/brewassistant/grainfather_fermenter/README.md).

## 1. Syfte och avgränsning

Användaren vill bygga vidare på GF30 Conical Fermenter med temperatur från RAPT Pill och GF30:s interna givare, separat temperatursensor i frysen, separat temperatursensor i köldmediet, Home Assistant `generic_thermostat` för frysen och en säker, lärande temperaturmodell. DIY-frysen är en övergångslösning; ett framtida byte till Grainfathers chiller ska inte kräva ändringar i fermentation tracking. Den tidigare reserverade `grainfather`-modulen är för Grainfather-bryggverk/G30-liknande hot-side, **inte GF30**.

Det finns redan en *read-only* discovery-adapter i `custom_components/brewassistant/grainfather_fermenter/adapter.py`. Utöka den befintliga fermenterbackendens domän; skapa inte en parallell, konkurrerande GF30-backend. Befintlig adapter verifierar inte GF30-modell och gör inga serviceanrop. Fältidentifiering och verkliga entitets-ID återstår.

## 2. Ägarskap och två åtskilda temperaturkretsar

```text
fermentation_tracking
  -> önskad ÖLTEMPERATUR per batch (Brewfather-dagar eller SG)
  -> rekommendation; skriver aldrig frys, pump eller GF30 direkt
             |
             v
GF30 grainfather_fermenter (valbar fysisk provider)
  -> Pill-öltemperatur + verifierad GF30-intern givare
  -> aktuellt öl-/processbörvärde, avvikelse, trend och learning
  -> GF30:s lokala controller äger värmare och kylbegäran/cirkulationspump
             |
             v
GF30:s kylmantel <- cirkulerande köldmedium <- reservoar i frys
                                                 ^
                                                 |
                       HA generic_thermostat (cool)
                       target_sensor = köldmediets vätskesensor
                       heater = frysens dedikerade brytare
                       -> ensam ägare av frysens ON/OFF

Separat frysluftgivare = diagnostik, larm och learning; inte
primär regulator om köldmediegivaren är korrekt installerad.
```

- GF30-controller och `generic_thermostat` reglerar **olika storheter**: öl/kylbehov respektive köldmediereservoar. De ska inte skicka parallella temperaturmål till samma aktor. Ingen direkt BA-on/off av frysen vid sidan av `generic_thermostat`.
- Pumpens faktiska styrning, dess tillgängliga HA-status och hur GF30-controller begär kyla måste verifieras på fysisk hårdvara. Tidigare Cooling Pump Kit-plan innebär inte att molnintegrationens API erbjuder pumpstyrning. Ingen antagen M12-pinout eller egen elektrisk modifikation.
- GF30-controller får inte samtidigt ägas av dess egen profil och en BA-skrivande provider utan vald, verifierad målauktoritet. Den gamla fermentationskammaren ska inte samtidigt applicera mål för samma batch. Provider-val sker explicit och är fail-passive.
- Om en framtida riktig GC2/GC4 används ersätts *reservoir/freezer*-adaptern; öltemperatur, tracking och learning-gränssnitt ska kunna återanvändas efter ny hårdvaruvalidering.

## 3. Ingångar och källa/färskhet

| Signal | Användning | Beviskrav |
| --- | --- | --- |
| RAPT Pill temperature | Föredragen faktisk öltemperatur, trend/learning | Konfigurerad entitet, giltigt °C, äkta ny timestamp och definierad freshness. Pill flyter och är inte en bottenreferens. |
| GF30 intern temperatur | Lokal verifierings-/reservmätning och delta mot Pill | Verklig HA-entitet och dess uppdaterings-/readback-beteende måste verifieras; inte gissa `sensor.grainfather_gf30_temperature`. |
| Fryslufttemperatur | Kompressorcykler, reservdiagnostik, varningar | Oberoende namngiven givare; får inte tolkas som köldmediets temperatur. |
| Köldmedietemperatur | `generic_thermostat`-reglering av frys + reservoirtrend | Givare nedsänkt på representativ plats, rimlighet/färskhet; verifiera korrekt temperatur även vid cirkulation/stillestånd. |
| Freezer climate/switch, ev. effekt | Status, bekräftelse, kompressorcykler och lärdata | Verifierade entiteter och readbacks, inte härled ON från enbart önskat läge. |
| GF30 kylbegäran/pump, om tillgänglig | Förklarar kylningsrespons och ETA | Endast observerade, verifierade signaler; saknas de ska modellen ange `unknown`, inte påstå pump ON. |

Pill saknad/stale: behåll senast bekräftat öltemperaturmål, flagga mätfel och stoppa BA:s *nya* måländringar. Byt inte omärkligt till GF30-givare; endast en uttryckligt vald, verifierad reservpolicy får användas efter fysisk test. Kylsystemets säkerhet får inte bero enbart på moln-Pill.

Köldmediegivare saknad/stale: freezer-control ska falla till ett verifierat säkert läge och larma. Verifiera först faktiskt HA `generic_thermostat`-/switchbeteende vid unknown, stale utan state change, HA-omstart och tappad anslutning. Lägg en oberoende failsafe/interlock om HA/smartplug inte kan garantera avstängning. Fryskontroll och kompressorskydd måste kunna fungera utan BA:s learning-loop.

## 4. Freezer/generic_thermostat: första driftkontrakt

- Använd `ac_mode: true` och vätskegivaren för reservoaren som `target_sensor`; frysluftgivare är separat diagnostik.
- Freezerns brytare ägs exklusivt av en HA `generic_thermostat`-klimatenhet. Start i `off` tills sensorer, vätska, mekanisk backup och test är validerade. Exakta entity-ID och start-/stoppsetpoints bestäms efter verklig installation, inte i dokumentationen.
- Konfigurera tillräcklig kompressorminimitid/cooldown enligt den faktiska frysen och verifiera att skyddet också gäller efter HA-omstart och spänningsbortfall. HA:s mjukvarutider är inte ett oberoende fysiskt kortcykelskydd.
- Frysen ska inte användas för kylning under villkor som riskerar att köldmediet fryser, pumpen blockerar eller reservoaren skadas. Säkert intervall beror på **faktiskt** medium, blandning och frysegenskaper. Anta inte att vatten tål negativa börvärden; skilj vattenprov från verifierad glykolblandning.
- Planerad mekanisk frysetermostat på varmaste läget kan testas som oberoende begränsning men dess uppmätta effekt måste verifieras; den ersätter inte explicit lågtemperaturskydd för reservoaren.
- BA ska inledningsvis bara **läsa** `generic_thermostat` och ge råd. En framtida ändring av reservoarbörvärde sker enbart via en registrerad, kvitterad klimatåtgärd inom verifierade gränser – aldrig via direkt frysbrytare eller självjusterande learning.

Referens: Home Assistants `generic_thermostat` stöder kyl-läge, `min_cycle_duration`, `cycle_cooldown` och `initial_hvac_mode`: https://www.home-assistant.io/integrations/generic_thermostat/ . Dessa parametrar är konfigurationsmöjligheter, **inte** bevis för korrekt fail-off i användarens faktiska anläggning.

## 5. Thermal learning v1 – observation först

Beräkna endast från tidsstämplade, rimliga och tillräckligt färska observationer:

- temperaturdelta Pill ↔ GF30-intern (kalibrerings-/placeringsindikation, inte automatiskt påstående att en givare är fel);
- ölens ändringstakt °C/h under verifierad kyla, vila och eventuell värme;
- fördröjning från bekräftad kylbegäran/pumpaktivitet tills ölet börjar svara, om signalen faktiskt finns;
- eftersläpning och overshoot efter kyla stoppas, med tillhörande trend/konfidens;
- köldmediets återhämtning, frysluft/vätske-delta och freezer on/off-duty/cykler med verifierad data;
- försiktig prognos till öltemperaturmålet, `unknown` vid otillräckliga data.

Behåll råvärden, källa, freshness, relevant batch, volym om känd, profil, aktivt setpoint, actuator-readbacks och modellversion i historik. Träna inte på stale/unknown, hopp, manuell override, saknad aktorkvittens eller byten av batch/medium/hårdvara. Separera normaljäsning och cold crash samt vattenkalibrering från faktiskt öl; deras värmetröghet och respons kan skilja sig. En ny hårdvarukonfiguration startar ny kalibreringsprofil, inte tyst återanvändning av gammal modell.

**v1 lämnar rekommendationer och diagnostik, inte autonom kontroll.** Visa `learning_status`, `sample_count`, `confidence`, `reason`, uppmätt avvikelse, trend, skattad fördröjning/overshoot och ev. förslag för operatören. Ingen numerisk rekommendation presenteras som säker utan data och verifierade hårdvarugränser.

## 6. Safety och cold crash

- Önskad cold crash kommer från tracking efter batchregler och uttrycklig bekräftelse. Skydd mot luftsug/oxidation ska kvitteras separat. GF30:s inbyggda regulator, kylsystem och medium måste faktiskt kunna uppnå målet inom verifierade gränser; ett receptmål är ingen garanti.
- HA/cloud/Pill-avbrott får inte trigga ny actuatoraktivitet, automatisk fallback till dagläge, omstart av tidigare kylbegäran eller ändrat börvärde.
- Separata lager: (1) fysisk medium-/pump-/kompressorsäkerhet och hårdvarans egen styrning, (2) `generic_thermostat` för frys, (3) GF30 lokala värme-/kylreglering, (4) BA rekommendation/learning. BA får inte kringgå lager 1–3.
- Skilj tydligt `command_sent`, HA-readback och **fysiskt verifierad** utgång; HA-state eller cloud-ACK är inte bevis för att kompressor/pump/styrning fungerar.

## 7. Faser och acceptans

1. **Kartläggning/read-only:** identifiera verkliga HA-entiteter för Pill, intern GF30, frysluft, medium, freezer climate/switch och eventuell GF-pump/kylbegäran. Dokumentera koppling, temperaturkalibrering, freshness och en enda ägare per aktor. Ingen ny fysisk BA-styrning.
2. **Sensorer och fältprov:** jämför GF/Pill i stillastående vatten med tillräcklig termisk utjämning, sedan belastat kylprov. Verifiera mediumets gräns, faktisk pumplogik, kompressorcykler, sensorbortfall, smartplug-off och HA-omstart.
3. **Learning read-only:** implementera ren beräkningsmotor, mätlogg, sensorsnapshot och regressioner för bortfall, omstart, lägesbyte, overshoot och inkonsekventa sensorer. Redovisa osäkerhet.
4. **Supervised integration:** först efter dokumenterad hårdvaruvalidering får en vald GF30-provider föreslå kvitterat mål till verifierad Grainfather-yta och eventuellt kvitterat reservoir-setpoint via `climate.set_temperature`. Inga direkta freezer/pump-kommandon från learning.
5. **Fullcykeltest:** vatten → riktig batch → steg/ramper → stabil FG → bekräftad cold crash → återhämtning/strömavbrott, utan dubbla controllers. Först därefter bedöm eventuell automation.

Öppna beroenden inför implementation: fysiska entity-ID, om GF30-controller ger lokal eller via cloud tillgänglig temperaturen/kylbegäran, medium och fryspunkt, aktuellt pumpkit och dess styrning, verkliga kompressorgränser och hur independent fail-off byggs. Inga av dessa får fyllas med gissade värden.

## 8. Dokumentationsregler

Den äldre [GF30-roadmapen](grainfather-fermenter.md) beskriver *cloud-discovery och framtida GF-profil-setpoint*. Detta kontrakt lägger till en **separat DIY-reservoar-/fryskrets och thermal learning** utan att förändra befintlig kod eller slå på styrning. Vid implementation synkas först `grainfather_fermenter/README.md`, därefter roadmap och dashboard-/installationsinstruktioner. Allt utvecklas på `dev`; inga test-/releasepåståenden utan faktiskt test.