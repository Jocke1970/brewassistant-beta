# BrewZilla: endast observation / lokal styrning – testkontrakt

**Status:** Utvecklingsgren `feat/220-brewzilla-observe-only`, PR #221. Publicerade `v0.2.0-beta.13` saknar funktionen. Installera inte PR-koden som om den vore en färdig HACS-release. Ny unik version och publicerad prerelease krävs för vanlig HACS-installation.

## Syfte och avgränsning

BA:s switch `switch.brewassistant_brewzilla_observe_only` är PÅ som standard vid första installation. ON blockerar BA-skrivning till BrewZilla: target, heater, pump, nyttjandegrad, huvudström och legacy-profilens direkta utgångsanrop. Även OFF och 0 % räknas som skrivning och ska inte skickas när observering aktiveras. RCL/BrewZilla och kontrollpanelen på det fysiska bryggverket påverkas inte av switchen. Andra Lovelace-kort som direkt adresserar RCL/BrewZilla ligger utanför BA:s spärr och måste hanteras separat.

BA fortsätter att läsa RAPT-profildata, temperaturer, energivärden, status och logga Flight Recorder. Learning får beräkna förslag och historik men **Learning APPLY får inte köras** i observerande läge.

## Återaktivering

Att slå AV switchen lämnar BA i spärrat `operator_rearm_required`. Först en separat bekräftelse via `brewassistant.brewzilla_rearm_after_observe` kan återge BA skrivbehörighet, och endast när identiteten för aktiv RAPT-session är giltig samt BrewZillas temperatur, mål, värmare, pump och nyttjandegrader rapporterats färskt. Gamla väntande planer ogiltigförklaras. Vid Home Assistant-omstart eller reload är styrningen åter spärrad även om switchen var AV tidigare. ABORT-spärren är separat och får inte kringgås.

**Viktigt:** När BA återaktiveras kan Heatstrike/Mash-in-reglering ske automatiskt utan kvittens för varje intern justering enligt befintlig implementation. Detta är inte samma sak som att samtliga framtida kommandon kvitteras ett och ett.

## Kort praktisk testsekvens – endast vatten, operatör närvarande

1. Säkerställ på det fysiska BrewZilla att vattennivå, temperatur, värme och pump är under kontroll. Den lokala nödstopp-/frånslagsvägen ska vara tillgänglig. Bekräfta installerad **ny** version och att switchen faktiskt finns; avsaknad är INTE read-only.
2. Med switchen PÅ, se att `sensor.brewassistant_brewzilla_orchestration_mode` har `orchestration_mode: observe-only`, `observe_only_effective: true` och `hot_side_actuator_writes_allowed: false`. Den säger inte att fysiska utgångar är OFF.
3. Ändra mål/värme/pump **på BrewZillas kontrollpanel**. Kontrollera att BA:s temperatur/status, logg och passiva learning fortfarande uppdateras och att BA **inte** skriver tillbaka gammalt mål eller nyttjandegrad. Verifiera kommandoflödet i både Flight Recorder och RCL-/HA-loggar; frånvaro av loggrad ensam är inte bevis för noll skrivningar.
4. Provtryck inga BA-hårdvaruknappar i ett aktivt test innan deras gränssnitt och negativa kvittenser är kontrollerade. Vid ett separat negativt tjänstetest ska även `OFF` och `0 %` spärras; låt ingen automatisk logik använda dessa som nödstopp.
5. Testa omstart, kort telemetribortfall och PÅ mitt i en väntande BA-plan: inga BA-utgångskommandon eller oavsiktlig återstart. Ett kommando redan skickat före PÅ går inte att återkalla. Om fysisk stopp krävs, använd bryggverkets egna reglage.
6. Slå AV: kontrollera att BA fortfarande är spärrad och gamla planer borta. Återaktivera inte förrän den separata bekräftelsen och de fysiska förhållandena har granskats.

## Kända öppna punkter i PR #221

- Automatiska tester täcker centrala writer-gates men ersätter inte en fullständig HA/RCL end-to-end-verifiering av alla tjänstevägar och redan påbörjade async-kommandon.
- Befintliga operatörskort kan fortfarande visa BA-knappar fast backend nekar själva hårdvaruskrivningen. Dessa ska döljas/inaktiveras konsekvent innan funktionen utannonseras som färdig.
- Ingen ny prerelease-version är publicerad från denna gren; installerad beta.13 ska aldrig antas innehålla observationsspärren.
