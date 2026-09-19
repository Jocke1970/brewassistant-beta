# Källbaserat ansvar för Brewing och Fermentation (2026-09-19)

**Målarkitektur – kod- och hårdvaruverifiering återstår.** Den här beskrivningen ersätter endast den felaktiga arkitekturslutsatsen i `ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md`. Det avbrutna beta.11-testets observationer kvarstår. En lyckad service-call innebär inte verifierad fysisk avstängning.

## Integrationernas faktiska roller

**BF är jäsningsrelaterad. BT är bryggningsrelaterad.** BA använde ursprungligen BF-integrationen för jäsning och byggde sedan själv ut den med BrewTracker-sensorer för bryggningsinformation från samma Brewfather-källa. BT är inte en separat extern tjänst eller ett jäsningsbackend. RAPT och BT är alternativa **bryggprocesskällor**; det valet ändrar inte BF:s separata jäsningsansvar.

| Process/läge | Auktoritativ data | BA:s roll | Maskin/transport |
| --- | --- | --- | --- |
| Brewing: RAPT vald | RAPT-profilens steg, tider, mål och stegövergångar | Reglerar temperaturmål, värme och pump med interlocks och kvittens | RAPT Cloud Link till BrewZilla; RCL/BrewZilla lämnar fysisk readback |
| Brewing: BT vald | Våra BF-baserade BrewTracker-sensorer | Nuvarande policy: passiv observatör, inga BA-skrivningar till BrewZilla | BT-information får visas/loggas utan aktuation |
| Brewing: Manual | Manuell källa | Separat befintlig policy; kräver egen granskning | BrewZilla/RCL där det är tillåtet |
| Fermentation | Ursprunglig BF-jäsningsinformation | BA styr jäskammarens värme/kyla enligt fermentationssäkerhet | Home Assistant / jäskammare |

RAPT → BA hot-side-regulator → RCL → BrewZilla. BF-jäsning → BA fermentationsregulator → jäskammare. RAPT-profilen äger stegövergångarna: BA får aldrig automatiskt trycka Next/Continue eller starta RAPT:s koktimer.

## Kritisk källisolering

När RAPT är vald **får BT fortsätta publicera sensorvärden och vara läsbar i separata informations-/diagnostikvyer**. BT får däremot inte leverera eller påverka det auktoritativa bryggsteget, tidskontexten, temperaturdirektivet, nästa steg, Learning-input, kommandon eller sessionsväxling. BT-data får inte bli automatisk reservkälla vid saknad, stale, ofullständig eller motstridig RAPT-data. Processvärdet ska då vara okänt/otillgängligt och nya positiva hot-side-skrivningar spärras.

Det äldre acceptanskravet om **noll BT-sensorläsningar globalt** var fel och är återkallat. Kravet är **noll BT-inflytande på RAPT-bryggningens process och styrning**. Generella BT-läsare och BT:s informationsvyer ska inte stängas av. BF:s fermentationssensorer ska fortsatt kunna läsas och styra jäsning oberoende av bryggkälla.

`brewzilla_rapt_brewing_read_isolation.py` begränsar legacy `brewday_runtime_core.source` och `build_core_snapshot` när RAPT äger processen, hindrar BT-receptkontext från att påverka BrewZilla Learning, och ser till att BT-status/event inte kan starta/rotera RAPT-bryggdagens audit. Generella BT-accessorer och `brewfather_batch_phase` lämnas läsbara i självständiga observationsvyer. Detta är en avgränsad kompatibilitetspatch, inte en komplett testad HA-arkitektur.

Kontrollpunkter: RAPT vald, source-loss efter aktiv session, STOP-handoff, RAPT-ABORT, ny session, samt ofullständigt första RAPT-kontrakt. Ändring i BT-status/steg/mål får aldrig ändra RAPT-snapshot eller BA:s avsedda styrkommandon. BF-fermentation får inte skapa BA→BrewZilla-skrivningar. Varken en UI-märkning eller ett rent unit-test ersätter en central skrivspärr.

## Säker Sparge vid RAPT-ägarskap

1. Exakt session och steget `Sparge`/`Lakning` ska identifieras. Börja `awaiting_lift`: beordra värme/pump AV och båda utilization 0 med verifierad färsk fysisk återrapportering innan manuellt lyft.
2. Operatören lyfter maltpipan och kvitterar uttryckligen säkert lyft **och** att värmeelementen är täckta av vört. Tid/temperatur/profilnamn får inte räknas som kvittens.
3. `heat_to_boil` håller pump AV; förkoksmål högst 95 °C kräver separat Supervised Apply för varje positiv körplan. Läs färsk OFF/0%-telemetri före värme. Kontrollera konflikter mellan RAPT:s lokala 78 °C-reglering och BA:s förkoksvärme innan denna aktiveras.
4. När lakningen och volymen är klara flyttar **operatören RAPT-profilen** manuellt till Boil. BA utför ingen automatisk stegväxling.
5. Källbyte, stegs-/sessionsbyte, telemetribortfall, restart eller ABORT ogiltigförklarar lyft-/värmekvittens. Ett läge som förbjuder BA-skrivningar får aldrig beskrivas som att hårdvaran bevisligen är AV.

## Återstående verifiering

- Inventera alla direkt- och indirekt importerade BA→BrewZilla-kommandovägar: target, heater, pump, heat-/pump-utilization, Learning APPLY, manual override, STOP/ABORT och pending-planer. BT observer-only ska ge **noll BA→BrewZilla-skrivningar**.
- Instrumentera simulerad HA med BT som samtidigt uppdateras när RAPT äger; BT-värden får inte påverka normaliserad process eller command intent. Testa också jäsning parallellt och både svenska/engelska Lovelace-kort.
- Verifiera faktiskt RCL-profilpayload/step-ID och möjlig konflikt mellan lokal temperaturreglering och BA:s 95 °C under Sparge. Inga påståenden om fysisk OFF från service-anrop.
- Genomför kodgranskning, CI, Hassfest och HACS före mergning.

## Releaseordning

`feature/* → PR till dev → separat PR dev→beta → ny versionshöjd GitHub-prerelease på exakt beta-SHA → HACS-installation → övervakat water-only-test → uttryckligt godkännande → separat PR beta→main`.

**Användarbeslut:** inget praktiskt test före publicerad och installerad prerelease. Beta är en testartefakt, inte ett intyg om fysisk säkerhet. Ingen automatisk merge eller ändring i main före praktiskt godkännande.
