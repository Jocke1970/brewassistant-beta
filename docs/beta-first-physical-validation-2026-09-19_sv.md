# BrewAssistant – beta först, därefter praktisk verifiering

Beslut 2026-09-19: **Inget praktiskt BrewZilla-test före en publicerad och installerad beta-prerelease.** En beta-release är testartefakten, inte ett intyg om fysiskt säker drift. `main` förblir orörd tills betan är utvärderad.

## Före publicering (utan aktiv fysisk BrewZilla)

1. Stäng kodgranskade skrivvägar, källbyte, RAPT-session/stegidentitet, gamla supervised-planer, Sparge-interlock, ABORT, förlorad telemetri och BF observer-läge. End-to-end-simulera BA-kommandon med fejkade Home Assistant-serviceanrop och ingen fysisk utrustning.
2. Verifiera att BF:s fermentation-regulator bara använder cold-side-output. UI ska visa osäker status som osäker, aldrig som bekräftat fysikt AV.
3. Granska konkurrensrisken med RAPT-profilens eget mål (78 °C i manuellt Sparge) och BA:s operatörskvitterade förkoksmål (högst 95 °C). Om detta inte kan styrkas utan hårdvara ska risken uttryckligen anges i betan och förkoksvärme lämnas oaktiverad vid första kontrollen.
4. Alla förväntade CI-, Hassfest-, HACS- och regressionstester måste vara godkända. PR från feature till `dev`, därefter separat PR `dev → beta`, versionshöjning och GitHub-prerelease med tagg på exakt `beta`-commit. Kontrollera vilket versionsnummer HACS faktiskt erbjuder.

## Först EFTER installerad prerelease

5. Operatören kontrollerar lokalt att BrewZilla är i säkert läge. Vatten-only under ständig uppsikt; börja med källbyte/observer-läge och OFF-avläsning, sedan låsta steg och kvittenser. Förkoksvärme testas först när den lokala RAPT-regleringens konkurrensbeteende och tillräcklig vattennivå verifierats. Bekräfta output på den fysiska enheten; ett HA-serviceanrop är inte bevis på OFF.
6. Logga utfall, regressionsfel och installerad version. Eventuella fel repareras `feature → dev → beta → NY prerelease`, inte genom att ändra en publicerad tagg.
7. `beta → main` först efter godkänt praktiskt test och uttryckligt releasebeslut. Publicera ingen stabil release enbart på grund av gröna CI-checkar.

**Notering:** `dev` och feature-kod kan statiskt granskas före release, men ingen fysisk körning ska påbörjas från dessa brancher.
