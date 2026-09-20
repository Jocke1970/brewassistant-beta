# HLT SIM-1 – kort, diagnostik och fälttest

**Status 2026-09-20:** HLT är **endast simulering/läsning** och har ingen fysisk kontroll av HLT eller effektbegränsning av BrewZilla. Starta med [projektstatus](project-status-2026-09-20_sv.md), [19/9-rapport](hlt-sim1-field-validation-2026-09-19.md) och [ny 20/9-rapport](hlt-sim1-field-validation-2026-09-20.md). Publicerad beta.14 och `dev` innehåller olika kod; verifiera vilken tagg/commit som faktiskt är installerad före ett nytt prov.

## Kort och installation

- [Svensk hel YAML](../dashboard/cards/hlt_power_dashboard_sv.yaml) och [engelsk hel YAML](../dashboard/cards/hlt_power_dashboard.yaml); kräver `custom:button-card`.
- [Backend-/sensoravtal](hlt-dashboard-backend.md) och [HLT:s kodnära README](../custom_components/brewassistant/hlt/README.md).

Kopiera hela YAML-kortet till den egna Lovelace-vyn efter versionskontroll. Korten monteras **inte automatiskt** i användarens dashboard och är read-only (`tap_action`, `hold_action`, `double_tap_action: none`). Ren YAML-ändring kräver normalt ingen HA-omstart; backend-Python och versionsbyte ska samordnas och installeras när BZ är inaktivt. Byt aldrig ut hela integrationen från ett gammalt feature-arkiv: parallell kod kan gå förlorad. GitHub-merge installerar inget i HA.

## Vad panelen betyder

BZ:s blå effektpanel är en **fysisk mätning**; HLT:s orange är en **virtuell simulering**. Verklig energimottagare/total kräver BÅDA fysiska effektmätarna. Utan HLT-mätare ska fysisk mottagare vara `Okänt`, verklig summa `—`, inte 0 W. För virtuell mottagare är `none` ett giltigt kategoriskt läge som visas `Ingen`, `hlt` visas `HLT (virtuell)`; saknad entitet, `unknown` eller `unavailable` får inte döljas som 0.

HLT-temperatur visas med källan `measured`, `estimated` eller `thermostat_calibrated_estimate`; modellerat vattenvärde är inte uppmätt. Tre tider är total session, samplad virtuell värme och uppskattad fysisk värmetid; den sista förutsätter HLT-effekt och switch ON vid båda samplen. Wh/tidsräknare är uppskattningar i minne och nollställs efter HA-omstart. JSONL lagras separat i `/config/brewassistant/logs/`, med aktuell serversökväg i `sensor.brewassistant_hlt_trace_path` (möjligt entity-suffix).

## Fynd 19 september – historik

Ett partiellt utdrag med 50 poster 13:28–13:53 svensk tid hade 0 W virtuell HLT och `WAITING_FOR_POWER` hela tiden; framför allt `Ramp to 71.8°C`, sedan `Hold 66°C · 5 min` och mäsktillsatser. Operatören förtydligade att Brewday **ännu inte skulle aktivera HLT**, så utebliven HLT-värmning är inte i sig ett fel. En äldre 19/9-logg visade dock en falsk virtuell grant vid explicit `Ramp to 72°C`; den specifika text-veto-kodfixen CI-testades. Dokumentera gamla och nya observationer separat.

Skärmbilden visade även `Okänt` för virtuell mottagare. Den dåvarande 50-postersloggen saknade värdet som HA faktiskt publicerade och bevisade inte varför. Senare lades endast *läsande* schema-2-JSONL-diagnostik till på `dev`: BZ temperatur, fysisk target, Brewday-target, individuella sensoråldrar och `hlt_virtual_recipient_ha_state` inklusive ålder. Dessa kan ligga en coordinator-uppdatering efter simulatorn; `null` är inte noll och gamla loggar uppdateras inte retroaktivt.

## Fynd 20 september – ÖPPET, inte rättat

[44 giltiga poster 09:21–09:43 svensk tid](hlt-sim1-field-validation-2026-09-20.md) innehåller fem virtuella ON-prover under RAPT-steget **`Heat Strike`** och tre *simulerade* effektkonflikter runt 3,7 kW mot scenariobudget 2,5 kW. Alla poster är märkta `physical_writes=false`, utan BZ-cap; detta är inte fysisk strömverifiering. `dev` tillåter stage `heat strike` men parsern känner inte igen exakt `step=Heat Strike` som ramp. Vid runt 40 °C och ~14 W BZ kunde den därför ge virtuell HLT-värmning innan ett positivt, källaoberoende HLT-startkontrakt är definierat. **Kodfix/acceptans kvarstår.** Bestäm först avsedd HLT-beredskap med Brewday, lägg sedan källspecifika regressionstester och rätta policyn utan att lätta på BZ-prioriteten.

Publicerat `hlt_virtual_recipient_ha_state` var `none` i 39 poster, `hlt` i fem; fyra av de fem runtime-ON-posterna hade ännu publicerat värde `none`. HA-sensorn kan alltså släpa efter simulatorns beslut. Tidigare `Okänt`-skärmbild är ännu inte entydigt förklarad.

## Felsök `Okänt` på rätt installation

Öppna Utvecklarverktyg → Tillstånd, kontrollera exakt `sensor.brewassistant_hlt_virtual_energy_recipient` och eventuellt `_2`-suffix. Jämför publicerat värde/tid med loggens runtime och **hela installerade YAML-kortet**, inklusive `triggers_update` och direkta entitetsreferenser. `none` ska ge `Ingen`, `hlt` ska ge `HLT (virtuell)`; oväntad text är ett sensor-/entitets-/versionsproblem att utreda, inte anledning att anta 0 W. Undvik omstart mitt under bryggning för att åtgärda ett visningsfel.

## Nästa test och säkerhetsgrind

Samordna först aktuell kodversion och avsedd HLT-start med Brewday. Verifiera BZ:s verkliga effektmätare, temperatur, fysisk target, Brewday-target, steg, läsningarnas färskhet och positiv lakvattenvolym. Efter en separat kodfix med tester ska ramp → väntan → **avsedd** cruise/HLT-beredskap → virtuellt ON → nytt BZ-behov → yielding/OFF följas i en *hel* JSONL-körning. Gör inga fysiska BZ-manipulationer för att få simuleringen att se grön ut; skriv i stället en ny daterad rapport.

**30 s sampling och ett scenariobudgetvärde är inte elsäkerhetsskydd.** Ingen fysisk HLT får kopplas till simulatorns grant. En framtida HLT kräver snabb oberoende fail-OFF, verifierad fysisk OFF, korrekt el-/säkringsdimensionering och torrkokningsskydd. BZ får aldrig strypas för HLT:s skull.
