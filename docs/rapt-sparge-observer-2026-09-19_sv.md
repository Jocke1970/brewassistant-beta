# RAPT Sparge – passiv BA-observation (utkast, 2026-09-19)

**Status: endast ett fristående, läsande kort är implementerat i denna gren. INGEN fysisk BA-styrning och INGEN verifierad central skrivspärr.** Läs först `docs/ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md`.

## Faktisk RAPT-profil som operatören byggt

`Heatstrike → Mash-in → Malt Rest → Mash Out (78 °C / 10 min) → Sparge (78 °C, manuellt slutvillkor) → Boil (100 °C / 60 min) → Chill Out`.

Sparge har `Step Type: Heat/Cool to target temperature`, `Target Temperature: 78 °C` och `Go to next step when: I press a button on the Device`. Den manuella övergången hindrar **profilens stegtidsautomat** från att gå till Boil före knapptryckningen, men den garanterar **inte** heater OFF, pump OFF eller att BA:s befintliga skrivvägar är avstängda. Det är inte en säkerhetsinterlock.

## Implementerat i denna gren

- `dashboard/cards/rapt_sparge_observer_sv.yaml` och engelsk spegel: fristående, receptoberoende, endast läsande `custom:button-card` som visas när RCL rapporterar aktiv profil och `step_name` är `Sparge`/`Lakning`.
- Kortet läser rapporterad värmare, pump, utilization och målvärde samt manuellt slutvillkor, men har inga serviceanrop/knappar för aktivering, stopp, kvittens eller profilfortsättning.
- Kortet markerar uttryckligen att rapporterad telemetry kan vara fördröjd och att kortet **inte** gör BA:s installation skrivskyddad.

## Avsedd process – INTE implementerad fysisk styrlogik

1. Vid Sparge: operatören verifierar lokalt på BZ att pump och värme är avstängda **före lyft**. BA:s observerade värden räcker inte som bevis.
2. När maltpipan lyfts säkert, värmeelementen är täckta och vörtnivån verifierats: eventuell uppvärmning mot kok utförs under **enbart RAPT/BZ:s** kontroll enligt den dedikerade RAPT-arbetsströmmen. BA får inte skriva target/heater/pump eller reassert.
3. Efter 11,38 L lakvatten **i det aktuella Julöl-receptet** (inte ett standardvärde för alla kort): operatören verifierar volym/avrinning och avancerar den manuella RAPT-profilen på enheten.

En framtida operatörsbekräftelse som bara loggas i BA kan visas som diagnostik men får aldrig tolkas som tillstånd för BA att slå på värme eller pump. `Awaiting Lift` och `Heat to Boil` måste i en externägararkitektur beteckna RAPT/operatörens processläge, inte ett BA-aktuatorläge.

## Blockerare för samtidig BA+RAPT-drift

Implementera och testa **central external-owner / monitor-only-gate först**: täck target, heater ON/OFF, heat utilization, pump ON/OFF, pump utilization, reassert, auto-handoff, STOP, ABORT och direkta services/buttons. Ingen uppstarts- eller återanslutningsskrivning. Kontrollera att ett `monitor`-fält i en sensor inte blandas ihop med fysisk isolation. Sedan test utan aktiv hårdvara och separat övervakad fysisk validering före release.

RAPT-/RCL-profilens faktiska värme- och pumplogik hör till separat RAPT-arbetsström; ingen RAPT-kod eller profil ändras av denna gren.
