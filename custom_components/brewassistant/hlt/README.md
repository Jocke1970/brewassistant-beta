# HLT SIM-1 — BrewZilla har alltid absolut effektprioritet

**Status 2026-09-19:** SIM-1 är mergad i `dev` via [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212), merge-commit `746633cfd5c22483fc25e821a966cccb25f84784`. CI, HACS och Hassfest passerade på både PR-head och sammanslagen `dev`. **Endast läsning, simulering och dashboard; ingen fysisk HLT-styrning.** Detta är inte en release till `beta` eller `main` och ingen fysisk certifiering. Fälttestets observationer och kvarvarande risker finns i [den daterade överlämningen](../../../docs/hlt-sim1-field-validation-2026-09-19.md).

## Effektprioritet och simulatorns beslut

- BrewZilla får aldrig strypas, kaps eller skrivas om för HLT:s skull. BZ:s uppmätta effekt kan öka när som helst, inklusive mellan två HA-prover.
- HLT är sekundär. Virtuell HLT får värma endast vid *observerad* BZ-cruise vid aktuell target, överensstämmande enhets-/runtime-target, färska fysiska effekt- och temperaturvärden, känd BZ-utnyttjandegrad och plats för **hela** den virtuella HLT-värmarens watt inom ett **simuleringsscenario**.
- Låg momentan BZ-effekt räcker aldrig ensam för tillstånd. Ett explicit rampsteg (`Ramp to 72°C` och motsvarande prefix) veto:ar cruise även om target/temperatur tillfälligt verkar sammanfalla.
- Endast explicit kända steg `Setup`, `Heat strike`, `Heat strike water`, `Mash`, `Mash in`, `Mash out` och `Sparge` får simulera. Okända/terminala steg fail-closed. Detta är en konservativ startpolicy, inte ett färdigvaliderat normaliserat lakningskontrakt för alla källor.
- Vid ny BZ-ramp, ändrat effektbehov, mätbortfall eller saknat utrymme släpps virtuellt HLT-tillstånd vid nästa simuleringstick. Reservationen kan kvarstå under en **virtuell** OFF-fördröjning, medan BZ aldrig kaps. Överlapp redovisas som `simulation_budget_conflict`, inte som en godkänd verklig effektbudget.
- Noll normaliserat lakvatten = No Sparge / HLT `IDLE`; okänd volym = ingen start. `sparge_water_l` är separat från `mash_water_l`/`strike_water_l`.
- `power_budget_verified` är alltid `false`. Kompatibilitetsfälten `brewzilla_would_grant_w` och `brewzilla_would_cap_utilization` är `None` och får aldrig användas för hårdvarustyrning. Äldre `brewzilla_unconstrained` är ingen aktiveringsflagga för kontroll.

**Elsäkerhet:** Den återkommande simuleringen var 30:e sekund är inte ett elektriskt överlastskydd. BZ:s termostat/RAPT kan slå på värmaren mellan avläsningar. `2500 W` är ett standardsättningsvärde i scenariot, **inte** verifierad säkringsgräns. Fysisk drift kräver en separat, snabb och oberoende fail-OFF-frånkoppling av HLT, bekräftad fysisk OFF-återkoppling, dokumenterade effekt-/kabel-/säkringsförutsättningar samt torrkokningsskydd. BZ ska få full effekt utan att invänta en långsam HA-loop eller virtuellt kvitto.

## In- och utdata

Standard-BZ: `sensor.brewzilla_power`, `number.brewzilla_heat_utilization`, `sensor.brewzilla_temperature`, `number.brewzilla_target_temperature` samt normaliserad Brewday `target_temperature`. Inställningarna i `number.*` kan vara oförändrade länge och avvisas **inte** enbart utifrån `last_updated`; `unknown`/`unavailable` avvisas däremot. Fysiska BZ-effekt- och temperaturvärden kräver fortfarande färska prover. Cruise kräver att target-/temperaturvärdena överensstämmer inom 0,5 °C, och ett explicit rampsteg blockerar ändå tillstånd.

Volym hämtas från BrewZilla Batch Contexts effektiva `sparge_water_l`. `Water only` betyder inte automatiskt 0 lakvatten; men mäsk-/testvattnet i BZ får inte återanvändas som påhittat lakvatten. Provisoriska och valbara HLT-entity IDs: `switch.sparge_heater`, `sensor.sparge_heater_power` och valfri HLT-temperatursensor. De fysiska HLT-entiteterna fanns inte i det första testet och ska då vara **okända**, inte 0 W eller bekräftat OFF.

HLT-temperatur använder färsk fysisk givare när sådan finns. I annat fall integrerar modellen virtuell effekt mot volym, starttemperatur, effektivitet och förlust. Termostatkalibrering kräver separat känd bryttemperatur och ett belagt värme→OFF-förlopp; manuellt OFF är inte en termostatkalibrering. Modellen är en uppskattning, inte en mätning.

## Driftsättning, logg och HA-ytor

`async_setup_hlt_simulation()` registrerar en frånkopplingsbar, självständig 30-sekunderstimer när BA startar. HLT-paketet har inga HA-hårdvaruserviceanrop och utfärdar inga BZ-caps. HLT-sensorerna uppdateras i BA:s koordinator och kortet kan ligga något prov efter. 31 läsande sensorvärden inkluderar status/orsak, faktisk kontra virtuell effekt, energimottagare, temperatur och källa, scenariototaler, väntan/värmetid/uppskattad energi samt aktuell JSONL-sökväg. Se [sensoravtalet](../../../docs/hlt-dashboard-backend.md).

Vid aktiv Brewday Audit skrivs JSONL per session under `/config/brewassistant/logs/hlt-sim-<session-hash>.jsonl`. Full aktuell sökväg visas i `sensor.brewassistant_hlt_trace_path` (HA kan ge entity-ID-suffix). Varje rad särskiljer uppmätt och virtuell effekt, uppmätt och skattad temperatur och markerar simulering/inga fysiska skrivningar. Betydande övergångar skrivs även i Brewday Event Log. Tid-/Wh-räknare lagras i minnet och återställs vid HA-omstart; JSONL ligger kvar på disk. Se [kort- och testguiden](../../../docs/hlt-dashboard-card.md).

**Installation och samordning:** PR #212 är redan mergad till den gemensamma `dev`-grenen. Den tidigare lokala testinstallationen på commit `977136c5` är inte den sammanslagna `dev` och saknar de sista ramp-/stegpolicyändringarna. Byt aldrig hela den installerade integrationen mot ett äldre feature-arkiv samtidigt som andra BA-arbeten fortgår. Jämför version, backup och lokal installation före uppdatering. En GitHub-merge installerar ingenting automatiskt i HA.

## Återstår före `beta`/`main` eller fysisk HLT

1. Testa senaste `dev` i HA: held `number.*` kontra färsk fysisk watt/temperatur, verkliga rampstegsnamn från Brewfather/Manual/RAPT och fail-closed vid okänt steg.
2. Följ en hel virtuell kedja BZ-ramp → cruise → virtuellt HLT-tillstånd → BZ-ramp/yield, samt kontrollera JSONL och UI mot verkliga BZ-avläsningar. Loggen från 2026-09-19 visade en felaktig virtuell grant under `Ramp to 72°C`; kodfixen är CI-verifierad men väntar på omtest i HA.
3. Bedöm uppskattad HLT-temperatur, tillgänglig uppvärmningstid, omstarter och sessionshantering. Automatiskt självlärande kontrollpolicy är **inte implementerad**; inlärning ska tills vidare vara granskad rådgivning.
4. För **fysisk** HLT: separat elsäkerhetskonstruktion med oberoende fail-OFF, fysisk OFF-bekräftelse, torrkokningsskydd och operatörsstyrd driftsättning; ingen av dessa funktioner är levererad i SIM-1.

Se [fältöverlämningen 2026-09-19](../../../docs/hlt-sim1-field-validation-2026-09-19.md) och [roadmapen](../../../docs/roadmap.md).