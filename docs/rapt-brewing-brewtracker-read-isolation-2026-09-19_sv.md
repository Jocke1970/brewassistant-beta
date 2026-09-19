# RAPT och BT: isolera källa, inte sensorer (2026-09-19)

**Beslut från användaren:** BF = jäsningsrelaterad; BT = bryggningsrelaterad och vår egen utbyggnad av den befintliga Brewfather-integrationen. BT är inte en egen extern datakälla eller en jäsningsmodul. RAPT är ett alternativ till BT som bryggprocesskälla. Sensorerna kan fortsätta uppdateras även när deras värden inte är auktoritativa.

## Källkontrakt

- **RAPT vald för Brewing:** endast RAPT-profilen får bestämma bryggsteg, tids-/stegkontext, processmål och nästa steg. BA styr BrewZilla via RCL med separat hårdvaruåterrapportering. BT kan uppdateras/läsas i fristående informationsvyer, men BT-värden får aldrig blandas in i RAPT:s normaliserade process eller styra BA:s aktuation.
- **RAPT tappar data, STOP eller RAPT-ABORT:** BT får inte bli automatisk reservkälla. Visa okänd/otillgänglig RAPT-process och spärra nya positiva kommandon. Att kommandon spärras innebär inte att fysisk värme/pump bevisligen är avstängd.
- **BT vald för Brewing:** BT-sensorerna levererar bryggprocessdata från den BF-baserade utbyggnaden. Nuvarande styrpolicy gör detta läge observer-only gentemot BrewZilla tills annat explicit beslutas.
- **BF Fermentation:** BF:s ursprungliga jäsningsdata och BA:s jäsningsregulator fortsätter oberoende av RAPT/BT-valet. BT ska inte användas som en ersättande jäsningskälla.

Det tidigare releasekravet om **noll BT-sensorläsningar överallt** var fel. Det korrekta acceptanskriteriet är **noll BT-inflytande på RAPT-processens tillstånd, värmemål, pumpbeslut, Learning-kontext och sessionsväxling**. Separat informationsvisning eller BF-jäsning ska inte hindras av en global sensor-spärr.

## Ändring på feature-branchen

`brewzilla_rapt_brewing_read_isolation.py` spärrar nu **källrutterna** `brewday_runtime_core.source` och `brewday_runtime_core.build_core_snapshot` under aktiv/tappad/stoppad/aborterad RAPT. Övriga generella BT-läsare (`core.state`, `attr`, `state_obj`, `resolved_entity_id`) lämnas intakta för självständiga informationsvyer. Den tidigare globala mutation som maskerade `brewfather_batch_phase` är borttagen. Ingen fermentationsmodul patchas.

Learning får ingen BT-batchkontext när RAPT är styrkälla; BT får därmed inte fylla saknade RAPT-receptparametrar med gamla värden. Audit får inte använda BT-aktivitet/status eller BT-event för att starta eller rotera en RAPT-bryggsession. Audit-spärren sitter på konsumenten, även där `brewfather_session_active` redan importerats som en funktion. Den äldre batch-control-guardens BT-aktivitet kan inte ge parallellt styransvar.

`tests/test_rapt_brewing_read_isolation.py` injicerar olika BT-status under aktiv RAPT, källa-tapp, STOP och ABORT; käll-/snapshot-/Learning-resultat ska vara oförändrade. Testet verifierar dessutom att separata BT-informationsläsningar och en BF-jäsningssensor fortfarande kan läsas, samt att BT fungerar som källflöde när RAPT inte äger processen. Detta är isolerade funktionstester, inte komplett Home Assistant-simulering.

Brewfather Feed EN/SV använder BF:s receptnamn och jäskammarens tillstånd. De korten ändrades under ett tidigare, för brett läskrav; deras visningsvillkor och BF-jäsningsanknytning behöver kontrolleras i HA. BT:s egna recept-/runtimekort får behålla informationsfunktioner, men ska inte presenteras som en parallell auktoritativ bryggkälla i RAPT-vyn.

## Återstår före beta

1. Simulera HELA BA-integrationen med RAPT och BT samtidigt; mutera BT-status, temperaturdirektiv och steg; kontrollera att RAPT-normaliserade värden och alla styrintents är oförändrade. Kontrollera även ofullständigt första RAPT-kontrakt och återanslutning.
2. Kör BF-jäsningen oberoende och granska Feed/Recipe/BT Runtime/Source Health EN/SV för korrekt auktoritetsmärkning och Lovelace-rendering. Ingen global BT-läsblockering får läggas tillbaka.
3. Inventera samtliga HA-servicevägar till BrewZilla och utför simulerade körningar utan fysisk utrustning. BF/BT observer-only får ge noll hot-side-skrivningar, och alla positiva RAPT/Sparge-skrivningar ska lyda kvittens och fysiska readback-krav.
4. Verifiera verklig RCL-profil/step-payload och lös möjlig konflikt mellan lokalt RAPT-börvärde 78 °C och BA:s 95 °C förkok innan positiv Sparge-värme släpps.
5. Kontrollera senaste CI, Hassfest, HACS och kodgranskning före promotion.

**Releaseordning:** `feature → dev → beta → ny publicerad prerelease → HACS-installation → övervakat water-only-test → uttryckligt godkännande → main`. Inget praktiskt test före prerelease; inga automatiska mergar eller fysisk-säkerhetsanspråk från gröna CI-tester.
