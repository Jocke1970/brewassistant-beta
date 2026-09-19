# RAPT-bryggning: isolering från BrewTracker-läsningar (2026-09-19)

**Status: backendens identifierade läsvägar patchade och testade i isolerade tester; fullständig isolering och fysisk drift ännu INTE verifierade.** Detta är ett releasevillkor i PR #215 och ändrar inte releaseordningen `feature → dev → beta/prerelease → HACS → praktiskt test → main`.

## Beslut

När en RAPT-profil äger Brewing ska BA inte läsa BrewTracker-sensorer för bryggsteg, temperaturmål, batchkontext, fallback eller bryggdagsaudit. RAPT/RCL levererar steg och processmål, BrewZilla/RCL levererar faktisk hårdvarutelemetri. Vid RAPT source-loss, STOP-handoff eller RAPT-ABORT får tidigare BT-data inte återanvändas. Brewfather Fermentation fortsätter läsa sina **separata jäsningssensorer** och styra jäskammaren oberoende.

## Kod som lagts till i denna feature-branch

`brewzilla_rapt_brewing_read_isolation.py` installerar ett lässkydd sist i BrewZilla-initieringen, efter styrspärren. Det avgör RAPT-ägarskap via RAPT-profilens aktiva kontrakt samt BA:s lagrade handoff och operatörs-ABORT – utan att fråga BrewTracker. Under RAPT-ägarskap blockeras BF/BT-entityreferenser i `brewday_runtime_core.state`, `state_obj`, `attr` och `resolved_entity_id`. Learning får inget BrewTracker-raw/batchunderlag; den manuella batchkontexten är fortsatt separat. Audits direkta BF-status-/availability-läsningar avbryts, och BT-state-change-event filtreras innan dess callback läser innehållet. Legacy batch-context-guardens direkta BT-aktivitetssökning blockeras. BF:s batchfas visas som inaktiv vid RAPT-handoff; fermentationsmoduler patchas inte.

Tester i `tests/test_rapt_brewing_read_isolation.py` använder en fake `hass.states.get` som kastar undantag vid BT-access. De kontrollerar aktiv RAPT, source-loss, STOP-handoff, RAPT-ABORT, core-läsare, Learning, audit och BT-eventfiltrering. Senast kontrollerade commit `469151a` hade grön CI, Hassfest och HACS, men dessa är **inte** ett end-to-end-HA- eller fysiskt test.

## Återstående releaseblockerare

1. Dashboardkort såsom `brewfather_recipe*.yaml`, `brewtracker_runtime*.yaml`, `brewassistant_source_health*.yaml` och eventuellt andra kort innehåller fortfarande direkta BT-entityreferenser. Villkorsstyr/hindra dem från att läsas i RAPT-läget och testa även svensk/engelsk UI. Frontend är inte skyddad av backendens Python-wrapper.
2. Kör fullständig instrumentation på hela Home Assistant-integrationen med BT-läsningar förbjudna under aktiv, tappad och ABORTad RAPT samt verifiera oberoende Brewfather Fermentation. Isolerade AST-tester ovan räcker inte.
3. Kontrollera att en RAPT-profil med ofullständigt kontrakt vid första anslutning aldrig kan trigga tyst BF-fallback. Klargör skillnaden mellan upptäckt/vald RAPT-källa och ett giltigt styrkontrakt.
4. Avsluta separat säkerhetsgranskning av alla BA→BrewZilla-skrivvägar och RAPT:s lokala temperaturreglering i Sparge (78 °C kontra BA:s möjliga 95 °C) före beta-publicering.

**Ingen merge till `dev`, ingen `beta` och ingen `main` är gjord av dessa kodändringar vid denna dokumentuppdatering.**
