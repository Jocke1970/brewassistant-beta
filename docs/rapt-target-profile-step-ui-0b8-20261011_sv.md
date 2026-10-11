# RAPT target & Profilsteg – UI-fälttest 2026-10-11 (0b8-dev)

## Observation
Operatörens installerade Lovelace-kort visade under `Mash Rest`:
`RAPT-target 0,0 °C`, `runtime-target 31,0 °C`,
`profilsteg 0/0` och `snapshot 2,5 min`.
Det går inte att avgöra en giltig rå RAPT-target från dessa siffror.
Värdet 31 °C är BA:s normaliserade runtime-referens, **inte** bevis
på RAPT-profilens aktiva temperaturmål.

## Förväntat UI-kontrakt
- Endast en aktiv RCL-profilsensor med matchande `ba_source` (eller en
  explicit identifierad sensor bland flera) kan användas.
- `profile_contract_complete=true`, `restored!=true`, tillstånd `on`
  och källans observation inom 90 sekunder behövs för att visa
  aktuellt RAPT-target och `steg/antal`. När data inte verifieras:
  target/steg visas `—`, och tidigare steg visas som *senast känt*.
- `0 °C` är **inte** ett hot-side-mål vid `Mash Rest` eller `Heatstrike`.
  Ett 0 °C-värde i `ChillOut` kan vara profilmarkör, inte automatiskt
  ett fysiskt temperaturmål.
- `0/0` är inte en giltig profilposition; visa `—`. Vi fyller inte
  automatiskt i saknade steg från en annan källa.
- BA:s runtime-mål visas endast som **BA-mål (referens)** när både RCL:s
  aktuella källa är verifierad och BA:s snapshot är högst 90 s gammal
  utan aktiv `resync_required`. BA-värdet ersätter aldrig RAPT-target.
- Märk tydligt: **RAPT profilägare** och **BA → RCL → BrewZilla** för
  assistans/kommandon. BA är inte en parallell direkt-BZ-styrare.
- Profilens nästa steg, timer- och villkorsinstruktioner får inte
  presenteras som aktuella åtgärder när källa/telemetri saknas.
- Kortet är read-only presentation; ingen target-, heat-,
  pump- eller profil-START/STOP-tjänst finns i kortet.

## 2026-10-11: falsk föråldring trots färsk RCL-temperatur

Fältbild: RCL Telemetry Age/BLE Data Age 43,7 s, medan BA visade
BA-snapshot 2,0 min och rödmarkerade samma profil (Mash Out).
Orsaken är att frontend normalt inte exponerar `last_reported`,
och `last_updated` står still när profilsteg och attribut är oförändrade.
Temperaturen kan samtidigt uppdateras separat.

RCL `dev`-PR #2 inför det explicita profilsensorattributet
`profile_observed_at`, som bara sätts vid lyckad API-hämtning av en
ansluten, aktiv profil. Det bekräftar en ny observation av samma profil,
INTE ett nytt stegbeslut och INTE fysisk utrustningsstyrning.
BA-kortet beräknar därför profilens 90-sekundersfärskhet från
`profile_observed_at`. Fältet får inte härledas från BLE/temperaturålder.
Om äldre RCL ännu inte rapporterar attributet fortsätter BA att
markera profildata overifierad (fail-closed).

Efter installation av BÅDA dev-ändringarna ska en frisk, stabil Mash Out
kunna vara grön även med gammal `last_updated`; en misslyckad
RCL-poll ska INTE förnya `profile_observed_at`. Kontrollera råattributet
i Utvecklarverktyg och status i båda integrationerna före beta.
## 2026-10-11: stegnamn, rödmarkering och diagnostik

Visa både **3/7** och **Mash Rest** i profilstegets ruta. Saknade eller
ej verifierade värden markeras rött. Huvudvärdet ska vara **—** när
fältet är osäkert; senast rapporterat tal/steg kan visas som liten röd
diagnostiktext med märkningen *uppgivet* / *senast*, aldrig som aktivt mål.
Temperatursensorns eget rapportdatum gäller oberoende av profilsteget.

**Profilsteg ≠ temperatur.** RCL läser API:ts aktiva profilsteg från
`activeProfileStepId` matchat mot `activeProfileSession.profile.steps`.
Temperatur kan ändras många gånger medan steget är samma. Använd
profilsensorns `last_reported` i första hand, inte dess `last_changed`,
för att verifiera att integrationen fortsatt rapporterar. 90-sekunders-
regeln och `profile_contract_complete` används fortfarande.

**Möjlig RCL-avvikelse:** RCL:s BrewZilla Debug-sensor innehåller
`devices[*].profile_runtime.telemetry_profile_step_id` från rå telemetri.
Profilens `step_id` kommer från rotfältet `activeProfileStepId`.
Vid matchande BrewZilla-enhets-ID men olika icke-tomma steg-ID:n
får kortet visa en tydlig röd konflikt och inga *verifierade*
setpoints/steg. Det finns ingen automatisk step-advance, heater/pump-
åtgärd eller ny styrväg. Saknas diagnostikkällan ignoreras jämförelsen
utan att ett påhittat fel visas.

**Fälttest:** Jämför binär profilsensors `step_id`, `step_name`,
`step_number`, `step_count`, tidpunkten `last_reported`, BrewZilla Debug
`active_profile_step_id` och `telemetry_profile_step_id` mot riktiga
stegbyten på BrewZilla. Om RCL-root och telemetri divergerar krävs
utredning i RCL/API, inte ett kosmetiskt UI-antagande.

## Acceptans
Fälttesta komplett SV/EN-kort under vattenprov med en aktiv RCL-session:
`Mash Rest` och giltig måldata, gammal RCL-observation >90 s,
saknat/0-värde i target och steg, samt efter återanslutning.
Verifiera exakt rå RCL-sensor och BA:s sammanställda runtime-värden.
Automatisk omstyrning vid förlorad källa är förbjuden.
