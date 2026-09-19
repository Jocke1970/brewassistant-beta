# HLT SIM-1 – fälttest och överlämning till Brewday, 2026-09-19

**Status:** PR [#212](https://github.com/Jocke1970/brewassistant-beta/pull/212) är mergad till `dev` (merge-commit `746633cfd5c22483fc25e821a966cccb25f84784`). Det är **enbart simulering och läsande telemetri**. Ingen fysisk HLT-styrning, ingen effektbegränsning av BrewZilla, ingen release till `beta` eller `main`. Den fysiska testen nedan gäller en tidigare installerad testbuild; rättningar som kom efteråt är testade i CI men inte omverifierade i en fullständig HA-bryggning.

## Sammanfattning av verkliga observationer

- BrewZilla var inkopplad i det avsedda effektmätta uttaget. `sensor.brewzilla_power` följde värmning omkring 2 323–2 356 W. Tidigare cirka 15,8 W avsåg ölkyl på samma uttag; detta var **inte** ett bevis på fel entitetsmappning.
- Brewday Audit var aktiv: `live`, steg `Mash`. Batch Context hade 17,0 L mäsk-/testvatten och 11,38 L lakvatten. Den normaliserade lakvattenvolymen gick från 0 till 11,38 L i HLT och status från `IDLE` till `WAITING_FOR_POWER`.
- Under fysisk ramp visade BZ ungefär 2 356,3 W, temperatur 50,054 °C, target 71,8 °C och heat utilization 100 %. HLT stannade på 0 W virtuell effekt: rätt konservativt utfall, men fel orsak `brewzilla_power_or_request_unknown`.
- Rotorsak: BZ-target och heat utilization hade inte **ändrats** på 819 respektive 892 sekunder och avvisades av en 180-sekunders `last_updated`-gräns trots giltiga `number`-inställningar. BZ-effekt och temperatur var färska (19 respektive 35 sekunder). Efterföljande kodrättning tillåter oförändrade inställningar, men kräver fortsatt färsk fysisk effekt- och temperaturtelemetri. `unknown`/`unavailable` ger inget virtuellt klartecken.
- Mörka engelska och svenska HLT-kort har visats i HA. Kategorivärdet `none` feltolkades i tidigare kort som `Okänt`; rättat till `Ingen`/`None` för **virtuell** mottagare. Verklig mottagare förblir okänd utan båda fysiska effektmätarna.

## JSONL-bevis (från granskning av inlämnad testlogg)

Den genomgångna loggen innehöll 94 poster under cirka 07:49–08:35 UTC. Ett virtuellt HLT-ON inträffade vid observerad BZ-effekt cirka 554 W, följt av `YIELDING` när BZ drog cirka 1 628 W. Reservationen under virtuell frånslagsfördröjning gav en **simulerad** överlappning cirka 3 427,7 W. Loggen visade inga fysiska HLT-skrivningar eller BZ-effektbegränsningar. HLT-ON inträffade trots att det explicita steget var `Ramp to 72°C`; telemetri ensam gav en falsk cruise-bedömning.

Efter analysen ändrades SIM-1 till en explicit allowlist för förberedande steg (`Setup`, `Heat strike`, `Heat strike water`, `Mash`, `Mash in`, `Mash out`, `Sparge`) och en rampstegs-veto som bland annat känner igen `Ramp to 72°C`. Okända steg tillåts inte. Denna nya stegpolicy är **inte fullständigt fälttestad**.

**Tolkning:** loggen visar varför 30 sekunders HA-sampling och virtuell OFF-fördröjning **inte** är ett elektriskt överlastskydd. BZ:s autonomt styrda värmare kan slå till mellan två avläsningar. Scenariobudgeten 2 500 W är en simuleringsparameter, inte en verifierad säkringsgräns.

## Aktuell kod och avgränsningar på `dev`

- SIM-1 läser Brewday Runtime/Audit och normaliserad `sparge_water_l` via BrewZilla Batch Context. Noll betyder No Sparge; okänd volym ger ingen körbar simulering. Mäskvatten är **inte** HLT-lakvatten.
- BrewZilla har absolut effektprioritet. Låg momentan BZ-effekt räcker aldrig ensam som HLT-tillstånd: känd heat utilization, färsk temperatur/effekt, överensstämmande börvärden, cruising, inget rampsteg och scenarioutrymme krävs.
- HLT-tillstånd, virtuell effekt, uppskattad eller uppmätt temperatur inklusive källa, tre huvudtidräknare samt JSONL-sökväg exponerats som läsande HA-sensorer. Minne-baserade tid-/Wh-räknare nollställs vid HA-omstart; JSONL på disk består.
- Loggfil: `/config/brewassistant/logs/hlt-sim-<session-hash>.jsonl`; aktuell fullständig sökväg: `sensor.brewassistant_hlt_trace_path` (kontrollera eventuellt HA-entity suffix).
- HLT simulerar endast; `power_budget_verified=false`. Fysisk HLT-effekt/relä/temperatur är okänd tills riktiga, verifierade enheter finns. Ingen HLT-kod får ge BZ ett cap/grant-kommando.
- Sammanslagen `dev` innehåller också parallell SG-styrd jäsningsutveckling; ingen sådan fil ersattes i PR #212. Den lokala testinstallationen från commit `977136c5` är **inte samma sak som sammanslagen `dev`** och innehåller inte de sista stegpolicyändringarna.

## Återstående acceptanspunkter för Brewday/HLT

1. Verifiera på nästa riktiga HA-körning att en oförändrad `number.brewzilla_target_temperature` och `number.brewzilla_heat_utilization` inte felaktigt räknas som gamla, men att gamla watt-/temperaturvärden ger fail-closed.
2. Verifiera att `Ramp to 72°C` och andra verkliga rampsteg veto:ar virtuell HLT även när mätningar råkar sammanfalla; kontrollera namnen från Brewfather, Manual Brewday och RAPT-profiler. Okända steg förblir stängda.
3. Följ en hel sekvens: BZ ramp → HLT väntar → verklig cruise + utrymme → virtuell HLT → nästa BZ-behov → virtuell yield/off, med JSONL och UI jämförda. Använd normalt bryggförlopp; tvinga inte BZ-utgångar för att få loggen att se rätt ut.
4. Utvärdera temperaturmodell, ETA, sampling-gaps, sessionsbyte, restart och HLT:s faktiska senaste-start-behov mot tillgänglig mäsk-/laktid. Inlärning är än så länge datainsamling/rådgivning, **inte** självändrande säkerhetsstyrning.
5. För eventuell framtida fysisk HLT: separat driftsatt, snabb fail-OFF-lastfrånkoppling oberoende av 30 s HA-loop; verifierad fysisk OFF-återkoppling, säkring/kabel/effektbedömning och övervakning mot torrkokning. Denna fas ingår inte i SIM-1 och får inte introduceras genom en dashboarduppdatering.

## Samordning och installation

Utveckling sker på gemensam `dev`, därefter separat PR-promotion `dev → beta → main` enligt `CONTRIBUTING.md`. Skapa inte fler långlivade HLT-feature-brancher. **Installera inte en gammal feature-branch som ett helt katalogbyte** när annan BA-utveckling pågår; jämför först aktuell `dev`, HA-installation och backup. Merge till GitHub uppdaterar inte Home Assistant automatiskt. Låt Brewday-backenden samordna nästa fälttest och eventuell installation.

Se [HLT-kodens README](../custom_components/brewassistant/hlt/README.md), [sensoravtal](hlt-dashboard-backend.md), [kort-/testinstruktion](hlt-dashboard-card.md), [Brewday/BZ-arkitektur](brewday-brewzilla.md) och [roadmap](roadmap.md). Äldre fysiska valideringsrapporter är historiska observationer och ska inte skrivas om retroaktivt.
