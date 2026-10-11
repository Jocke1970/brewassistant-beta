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

## Acceptans
Fälttesta komplett SV/EN-kort under vattenprov med en aktiv RCL-session:
`Mash Rest` och giltig måldata, gammal RCL-observation >90 s,
saknat/0-värde i target och steg, samt efter återanslutning.
Verifiera exakt rå RCL-sensor och BA:s sammanställda runtime-värden.
Automatisk omstyrning vid förlorad källa är förbjuden.
