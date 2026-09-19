# HLT-simulering – dashboard och fälttest

**Aktuell status 2026-09-19:** HLT SIM-1 från [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212) är mergad till `dev`. Kortet och backenden är enbart läsande/simulerande; ingen fysisk HLT-styrning, ingen BZ-effektbegränsning och ingen promotion till `beta`/`main`. Se [daterad testöverlämning](hlt-sim1-field-validation-2026-09-19.md) innan ett nytt fälttest.

## Kortfiler

- [`dashboard/cards/hlt_power_dashboard.yaml`](../dashboard/cards/hlt_power_dashboard.yaml) – engelskt canonical-kort.
- [`dashboard/cards/hlt_power_dashboard_sv.yaml`](../dashboard/cards/hlt_power_dashboard_sv.yaml) – svenskt kort med samma sensoravtal.
- [Backend-/sensoravtal](hlt-dashboard-backend.md) – betydelse, källor, precision och begränsningar.

Kopiera **hela** YAML-innehållet i önskat kort till ett manuellt Lovelace-kort när installationsversionen är verifierad. Kräver redan installerat `custom:button-card`. Dessa två filer är exempel och installeras inte automatiskt i en dashboard. **En ren YAML-kortändring kräver normalt ingen omstart; ändrad Python-backend kräver omstart av Home Assistant.** Byt inte ut hela den installerade `custom_components/brewassistant` från ett gammalt feature-arkiv: den gemensamma `dev` kan innehålla parallella ändringar. Jämför först versionsskillnader och backup. GitHub-merge uppdaterar inte HA automatiskt.

Kortet är read-only (`tap_action`, `hold_action`, `double_tap_action`: none). Det kan inte starta HLT, ändra BZ-effekt, kvittera Supervised Apply eller upprätthålla ett elektriskt effektutrymme.

## Presentation och datakällor

- Tydlig mörk kontrast och separata blå (BZ uppmätt) respektive orange (HLT virtuell) effektpaneler på både svenska och engelska.
- BZ-prioritet är en policy, inte en fysisk energimottagare. Verklig energimottagare och verklig totalsumma kräver **båda** fysiska effektmätarna; utan HLT-mätare visas `unknown` / `—`.
- Virtuell mottagare ska visa `Ingen` / `None` när det kategoriska värdet är `none` och HLT inte har virtuell tilldelning. Det får inte göras om till `Okänt` / `Unknown` genom generisk null-hantering. Ett virtuellt klartecken är inte fysisk strömleverans.
- `sensor.brewassistant_hlt_temperature` ska alltid visas med mätkälla `measured`, `estimated` eller `thermostat_calibrated_estimate`. Modellvärdet är inte ett uppmätt vattenvärde.
- Tre huvudklockor: total sessionstid, samplad virtuell värmetid och uppskattad fysisk värmetid. Den sista kräver fysisk HLT-effekt **och** ON-tillstånd vid båda mätpunkterna. Diagnostik visar väntan, yielding, provluckor och skattade Wh. Räknarna är minnesbaserade och nollställs vid HA/integrationsomstart.
- JSONL-filnamnet visas i kortet. Den fullständiga sökvägen finns i `sensor.brewassistant_hlt_trace_path` och är en serversökväg, inte en nedladdningslänk.
- Scenariobudgeten 2 500 W är **inte** en uppmätt eller driftsatt säkringsgräns. Den 30 sekunder långa samplingen kan inte skydda en verklig gemensam elkrets.

## Fynd från andra testutdraget 19 september

En uppladdad partiell JSONL-logg med 50 poster kl. 13:28–13:53 svensk tid visade `WAITING_FOR_POWER` hela perioden och 0 W virtuell HLT. De flesta posterna avsåg Brewdays `Ramp to 71.8°C`; en post visade `Hold 66°C · 5 min`, sedan följde `31 min, mäsktillsatser`. Operatören förtydligade att Brewday **ännu inte hade nått läget då HLT skulle aktiveras**. Vi klassar därför inte utebliven HLT-värmning som en bugg och lättar inte på ramp-/cruise-spärren.

Skärmbilden visade `Okänt` även för virtuell mottagare. Nuvarande kortkod visar däremot `Ingen` när `sensor.brewassistant_hlt_virtual_energy_recipient` publicerar exakt `none`. Utdraget hade inte det publicerade sensorvärdet; skärmbilden ensam bevisar därför inte att själva kortlogiken är fel.

**Felsökning av `Okänt`:** Öppna HA Utvecklarverktyg → Tillstånd och läs den exakta entiteten `sensor.brewassistant_hlt_virtual_energy_recipient`. `none` ska ge `Ingen`; `hlt` ska ge `HLT (virtuell)`. Saknad entitet, `unknown`, `unavailable` eller ett oväntat värde ska felsökas som sensor-/entitets-/installerad-kortversion – inte tyst behandlas som 0 W. Kontrollera även om HA har skapat ett suffix som `_2` för entiteten och att kortet är den fullständiga aktuella YAML-versionen. Undvik HA-omstart under bryggning.

Den 19 september tillkom **endast läsande JSONL-diagnostik på `dev`** i `hlt/trace.py`. Framtida nya loggrader får `bz_temperature_ha_c`, `bz_device_target_ha_c`, `bz_brewday_target_ha_c` och deras separata `_age_s` samt `hlt_virtual_recipient_ha_state` och `_age_s`. De är HA-publicerade diagnostiska värden (kan ligga en coordinator-uppdatering efter runtime), inte auktoritativa tillstånd för HLT-grant. `null` betyder saknad/ogiltig data, inte noll; gamla loggrader kompletteras inte retroaktivt. Den här GitHub-ändringen påverkar inte redan installerad HA förrän en samordnad, verifierad installation genomförts.

## Nästa kontrollerade prov

1. Samordna först med Brewday-backenden och verifiera vilken kombinerad `dev`-version som ska köras. Tidigare lokalt testade commit `977136c5` innehöll inte sista ramp-/stegpolicyn från merge `746633c`. Håll fysisk HLT frånkopplad och undvik oförankrade helkataloginstallationer.
2. Sätt BZ i det avsedda effektmätta uttaget och verifiera att `sensor.brewzilla_power` följer BZ:s värmare. Tidigare låga avläsningar kom från ölkyl på samma uttag; använd dem inte som BZ-baslinje.
3. Starta Brewday Audit med **verklig** positiv lakvattenvolym. `sparge_water_l` är lakvatten för HLT och skilt från exempelvis 17 L mäsk-/testvatten. Noll = No Sparge / ingen HLT-begäran.
4. Observera normal ramp, target/cruise och senare ramp. HLT ska avstå vid explicit `Ramp to 72°C` även om övriga mätvärden tillfälligt ser stabila ut, och vänta vid okänd temperatur/effekt eller okänt steg. Ett verkligt cruise-läge plus scenarioutrymme kan ge *virtuell* HLT-värme; inget BZ-cap får förekomma.
5. Kontrollera den korrigerade färskhetsregeln: oförändrade `number.brewzilla_target_temperature` och `number.brewzilla_heat_utilization` är giltiga inställningar, medan fysisk watt och temperatur kräver färska prover. `unknown`/`unavailable` ska fail-closed.
6. Hämta aktuell JSONL från `/config/brewassistant/logs/` via File Editor, SSH eller motsvarande. Jämför beslut och övergångar med BZ:s faktiska effekt/temperatur, steg, UI och tids-/temperaturmodellen. Dokumentera nya fakta i en **ny daterad** fältrapport. Grön CI är inte bevis på komplett fysisk HA-validering.

**Gräns för fysisk kontroll:** SIM-1 innehåller inte lastfrånkoppling, fysisk OFF-återkoppling, självständigt elsäkerhetsinterlock, torrkokningsskydd eller verifierad kretsdimensionering. Före sådan drift krävs en separat HW-fas och kvalificerad elsäkerhetsbedömning. BrewZilla behåller alltid effektprioritet.
