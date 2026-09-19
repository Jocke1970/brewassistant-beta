# RAPT-bryggning: isolering från BrewTracker-läsningar (2026-09-19)

**Status: backendens identifierade läsvägar och Brewfather Feed EN/SV patchade med avgränsade tester. Fullständig isolering, parallell fermentation och fysisk drift ännu INTE verifierade.** Detta är ett releasevillkor i PR #215 och ändrar inte ordningen `feature → dev → beta → ny GitHub-prerelease → HACS-installation → praktiskt test → main`.

## Beslut

När RAPT äger Brewing ska BA:s bryggningsflöde inte läsa BrewTracker-sensorer för bryggsteg, temperaturmål, batchkontext, fallback, audit eller frontend. RAPT/RCL levererar steg och processmål, BrewZilla/RCL levererar faktisk hårdvarutelemetri. Vid RAPT source-loss, STOP-handoff eller RAPT-ABORT får gamla BT-data inte återanvändas. Brewfather Fermentation ska fortsätta läsa separata jäsningssensorer och styra jäskammaren oberoende.

## Genomförd kod på feature-branchen

`brewzilla_rapt_brewing_read_isolation.py` installerar avgränsat lässkydd för Brewday-core, Learning och audit. Även BT-event filtreras innan audit-callbacken. `tests/test_rapt_brewing_read_isolation.py` använder en fake `hass.states.get` som kastar vid BT-läsning; de rena kontraktstesterna passerade CI, Hassfest och HACS. Dessa tester är **inte** end-to-end Home Assistant.

`dashboard/cards/brewfather_feed.yaml` och `_sv.yaml` har nu ersatt direkta BrewTracker-råvärden med `sensor.brewfather_recipe_name` och `climate.fermentation_chamber`. Nytt regressionstest `tests/test_rapt_fermentation_feed_isolation.py` förbjuder direkta BT-läsningar i båda korten. CI och Hassfest passerade för testcommit `a7b48ec`. **Begränsning:** kortens synlighet beror fortfarande på `sensor.brewassistant_brewfather_batch_phase`, som den gamla batchfaslogiken döljer under RAPT-ägarskap. Samtidig RAPT-bryggning + BF-jäsning är alltså ännu INTE säkrad i UI.

## Återstående releaseblockerare

1. Dashboardkort `brewfather_recipe*.yaml`, `brewtracker_runtime*.yaml`, `brewassistant_source_health*.yaml` och eventuellt andra har direkta BT-referenser. Ta bort eller källspärra dem, inklusive EN/SV, och testa faktisk Lovelace-rendering; Python-wrappern skyddar inte frontend.
2. Frikoppla fermentationssynlighet och dess styrning från BT-batchfasen, så att samtidigt aktiv RAPT-bryggning och BF-jäsning fungerar utan BT-läsning i BA:s bryggningsflöde.
3. Kör fullständigt HA-integrationstest med förbjuden BT-läsning vid aktiv/tappad/stoppad/aborterad RAPT, inklusive tidigare importerade funktioner och kontroll av separata fermentationssensorer.
4. Initialt ofullständigt RAPT-kontrakt får inte leda till tyst BT-fallback. Skilj vald RAPT-källa från giltigt styrkontrakt.
5. Granska alla BA→BrewZilla-skrivvägar och lös eventuell lokal RAPT-regleringskonflikt i Sparge (78 °C kontra BA:s möjliga 95 °C) innan beta-publicering.

Ingen merge till `dev`, ingen beta eller main av dessa ändringar har utförts i denna genomgång. Inget praktiskt hårdvarutest före publicerad och installerad beta.
