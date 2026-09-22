# BrewZilla: endast observation / lokal styrning – testkontrakt

**Status:** Utvecklingsgren `feat/220-brewzilla-observe-only`, PR #221. Publicerade `v0.2.0-beta.13` saknar funktionen. Installera inte PR-koden som om den vore en färdig HACS-release. Ny unik version och publicerad prerelease krävs för vanlig HACS-installation.

## Syfte och avgränsning

BA:s switch `switch.brewassistant_brewzilla_observe_only` är PÅ som standard vid första installation. ON blockerar BA-skrivning till BrewZilla: target, heater, pump, nyttjandegrad, huvudström och legacy-profilens direkta utgångsanrop. Även OFF och 0 % räknas som skrivning och ska inte skickas när observering aktiveras. RCL/BrewZilla och kontrollpanelen på det fysiska bryggverket påverkas inte av switchen. Andra Lovelace-kort som direkt adresserar RCL/BrewZilla ligger utanför BA:s spärr och måste hanteras separat.

BA fortsätter att läsa RAPT-profildata, temperaturer, energivärden, status och logga Flight Recorder. Learning får beräkna förslag och historik men **Learning APPLY får inte köras** i observerande läge.

## Återaktivering

Att slå AV switchen lämnar BA i spärrat `operator_rearm_required`. Först en separat bekräftelse via `brewassistant.brewzilla_rearm_after_observe` kan återge BA skrivbehörighet, och endast när identiteten för aktiv RAPT-session är giltig samt BrewZillas temperatur, mål, värmare, pump och nyttjandegrader rapporterats färskt. Gamla väntande planer ogiltigförklaras. Vid Home Assistant-omstart eller reload är styrningen åter spärrad även om switchen var AV tidigare. ABORT-spärren är separat och får inte kringgås.

**Viktigt:** När BA återaktiveras kan Heatstrike/Mash-in-reglering ske automatiskt utan kvittens för varje intern justering enligt befintlig implementation. Detta är inte samma sak som att samtliga framtida kommandon kvitteras ett och ett.

## Körda isolerade kontroller – 2026-09-20

- `tests/test_brewzilla_observe_only_combined_dispatch.py` samt övrig regressionssvit: 376/376 godkända på Python 3.11, 3.12, 3.13, med inspelade simulerade serviceanrop.
- `tests/integration/ha_rcl_observe_smoke.py` via `.github/workflows/ha-rcl-observer-smoke.yml`: godkänd på verklig Home Assistant Core 2026.9.3 och Python 3.14.2 samt fastlåst, publicerad RCL beta.1-kod (commit `149d51aaa4d467fd37c932ceaf8161c9f1387314`). Workflow: https://github.com/Jocke1970/brewassistant-beta/actions/runs/35518259462.
- Det isolerade provet instansierar riktig RCL-profil-binärsensor, för in dess data i HA:s StateMachine, kontrollerar BA:s dynamiska profilidentifiering, blockerar BA:s target/värme/pump/nyttjandegrad inkl. OFF och 0 samt separat STOP, verifierar OFF utan rearm och att direkta tjänsteanrop utanför BA inte stoppas. Falska HA-servicehanterare registrerar allt som skulle ha skickats, utan molnkonto eller bryggverk.
- Det här är **inte** fullständig HA-integrationsuppstart med riktiga config entries eller live RAPT API. Det verifierar inte Flight Recorder/learning genom faktisk omstart, CFC/handoff, redan dispatchade async-anrop, fysiska utgångar eller att samtliga tidigare UI-kort döljer hårdvaruknappar. Sådana punkter förblir öppna och får inte räknas som PASS.

## Praktisk acceptans – endast vatten, operatör närvarande och först efter separat publicerad prerelease

1. Säkerställ lokalt på BrewZilla att vattennivå, temperatur, värme och pump är under kontroll. Lokal avstängning ska vara åtkomlig. Bekräfta installerad **ny** BA-version och att observationsswitchen verkligen finns; avsaknad är INTE read-only. Ha backup av aktuell BA-installation och avbryt om någon status avviker.
2. Med switchen PÅ: kontrollera `sensor.brewassistant_brewzilla_orchestration_mode` attribut `orchestration_mode: observe-only`, `observe_only_effective: true`, `hot_side_actuator_writes_allowed: false`. Dessa uttrycker BA-behörighet, **inte** att de fysiska utgångarna är av.
3. Ändra mål/värme/pump på BrewZillas lokala panel under säkra vattenförhållanden. Kontrollera att BA:s temperatur, status, Flight Recorder, passiv learning och energivärden fortsätter uppdateras utan BA-återställning av lokala inställningar. Läs både HA-tjänstehändelser/orsakskedja och RCL-loggar/API-spår; frånvaro av en loggrad ensam bevisar aldrig att inga kommandon skickades.
4. Gör ett separat negativt test utan aktiv värme/pump: kontrollera BA:s hårdvaruknappar och direkta servicevägar inklusive `OFF`, `0 %`, ABORT, Mash-in, Sparge, bekräftelse och RAPT STOP. Ingen BA-initierad fysisk skrivning får ske under observation. Direkt RCL/Lovelace-kontroll är **inte** skyddad av BA-switchen och ska inte förväxlas med ett BA-kommando.
5. Testa integration reload, Home Assistant-omstart, tillfälligt telemetribortfall samt switch PÅ medan plan väntar. Ingen ny BA-skrivning, gammal kvittens eller automatisk återstart. Ett kommando redan skickat före switchen PÅ kan inte återkallas. Koppla inte bort nätverket om det riskerar fysisk drift; välj kontrollerad provmiljö.
6. Slå switchen AV: BA ska fortfarande vara spärrad och gammal plan borttagen. Verifiera separat rearm endast om aktuell RAPT-session och alla nödvändiga readbacks är färska och granskade. Testa inte automatisk Heatstrike-reglering utan operatör och vatten.
7. Verifiera att CFC/handoff, Flight Recorder, learning och energi förblir observerande under drift och att alla BA-hårdvaruknappar verkligen är dolda/inaktiverade medan observation gäller. Godkänn inte om en enda BA-output finns eller loggbevis saknas.

## Öppna releasegrindar

- Fullständig HA/RCL end-to-end-uppstart och tjänste-/molnspårning samt fysiskt återkopplade utgångar är inte utförda i användarens installation.
- Befintliga BA-operatörskort kan fortfarande visa knappar trots backend-nekad hårdvaruskrivning; dölj eller inaktivera dem konsekvent. Dokumentera oberoende RCL-kort.
- Ingen ny BA prerelease-version publicerad; beta.13 innehåller inte observationsspärren. Släpp inte fix-release innan ovanstående grindar har stängts.
