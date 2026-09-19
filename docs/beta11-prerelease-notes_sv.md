# BrewAssistant v0.2.0-beta.11 — korrigerad övervakad testversion

> [!WARNING]
> **Endast övervakade water-only-tester.** GitHub Actions och kodtester ersätter inte verifiering i Home Assistant, RAPT Cloud Link och BrewZilla. Kör inte obevakad bryggning och använd inte malt förrän water-only-protokollet är godkänt. HLT SIM-1 är enbart simulering och är ingen elektrisk säkerhetsspärr.

## Viktig korrigering av beta.10

Den publicerade GitHub-releasen `v0.2.0-beta.10` pekar på en gammal commit (`b8f2f58463865d443855adb67cbc23f181fb9c58`) vars integrationsmanifest fortfarande anger `0.2.0-beta.9` och vars `brewzilla/__init__.py` **inte** installerar den nya fysiska mash-interlocken. Beta.10:s releasetext beskriver därmed fel kodpaket. **Använd inte beta.10 för nästa styrtest.** Vi flyttar inte den gamla taggen. Beta.11 ska taggas från en ny, verifierad slutcommit på befintliga `dev`, och `main` lämnas orörd. Skapa ingen ytterligare branch.

## Ändringar avsedda att ingå i beta.11

### Mash-In, maltbäddsvila och fysiskt temperaturmål

Den fysiska styrspärren från `dev` adresserar fyndet från det övervakade water-only-testet 19 september: Brewfather gick vidare från 66 °C till 72 °C innan BrewAssistant hade slutfört den fysiska 66 °C-vilan.

- **Mash-In Started:** släpp strike-målet till faktiskt mäskmål; pump OFF och 0 %.
- **Mash-In Complete:** Brewfather PAUSED efter Started och senare RUNNING/FORTSÄTT är ordinarie kvittens; manuell Complete är reserv. Pumpen ska fortfarande vara OFF/0 % och en 10-minuters settling-period börjar.
- **Efter 10 minuter:** endast ett förslag om första operatörskvittens. Först ett faktiskt knapptryck får begära cirka 25 % pump-utilization och pump ON. Timer får inte slå på pumpen.
- **Efter verklig pumpåterkoppling:** fem minuters lågflödesperiod. Förslag om cirka 50 % kräver en andra separat kvittens; höjningen sker inte automatiskt.
- **Fysiskt mål:** när Brewfather går vidare ska BrewAssistant behålla den fysiska 66 °C-vilan tills den är klar och normalt flöde är bekräftat; först då får nästa receptmål släppas genom ordinarie Supervised Apply och säkerhetsspärrar.
- **Felhantering:** gammal processtemperatur nekar nya positiva pumpkommandon; utebliven pumpåterkoppling, källbyte eller förlorad sessionsauktoritet kan spärra sekvensen. ABORT har företräde. En HA-omstart får aldrig återställa tidigare kvitteringar automatiskt.

**Viktigt:** 25 % och 50 % avser inställd *utilization*, inte uppmätt genomströmning. BA saknar nivå- och flödessensor. Operatören måste själv kontrollera vattennivå, pumpens primning och avrinning. Ett water-only-test verifierar inte en verklig maltbädd.

### Dashboard och andra moduler

- Brewday-korten på svenska och engelska har status och separata pumpkvitteringar. Texten som felaktigt angav att Brewfathers FORTSÄTT startar pumpen är rättad.
- Dashboardkort som klistrats in manuellt i HA **uppdateras inte av HACS**; lägg in rätt YAML separat från samma tagg.
- HLT SIM-1 från PR #212 följer med den sammanslagna utvecklingskoden, men är **read-only simulering**. Ingen fysisk HLT-effektstyrning eller elektrisk lastsäkring ingår.
- Den önskade totala bryggtidsklockan och en kommande kompakt dashboardlayout ingår **inte** i beta.11.

## Publiceringsgrind — kontrollera före knappen Publish release

1. På `dev` ska `custom_components/brewassistant/manifest.json` ange exakt `0.2.0-beta.11` och `custom_components/brewassistant/brewzilla/__init__.py` både importera och installera `brewzilla_physical_mash_interlock`.
2. Vänta in grön **CI (Python 3.11, 3.12, 3.13), HACS validation och Hassfest** på **exakt samma slutcommit** som ska taggas. Tidigare gröna körningar räcker inte.
3. I GitHub Releases: använd ny tagg `v0.2.0-beta.11` med **`dev` som mål** och kontrollera den skapade taggens commit-SHA mot den verifierade slutcommitten. `main` eller gamla `beta` får inte vara taggens mål. Flytta inte befintliga beta.10-taggen.
4. Markera **Set as a pre-release** och lämna **Set as latest release** av. Använd **hela detta Markdown-dokument som release description**.
5. **Efter publicering:** läs taggens eget manifest och `brewzilla/__init__.py` via `.../blob/v0.2.0-beta.11/...`. Kontrollera version `0.2.0-beta.11` och att interlock-installationen verkligen finns. Om någon kontroll fallerar: stoppa distributionen och testet; publiceringssidan ensam räcker inte.

## Uppdatering i Home Assistant — först efter godkänd publiceringsgrind

1. Avsluta föregående körning, verifiera fysiskt att pump och värmare är OFF och säkerhetskopiera nuvarande integration och dashboard-YAML.
2. Installera **exakt `v0.2.0-beta.11`** via HACS med prereleases aktiverade; kontrollera valt versionsnummer. Installera inte beta.10 och kopiera inte över en äldre brancharkivversion.
3. Starta om hela Home Assistant. Lägg separat in de svenska kort du faktiskt använder från **samma tagg**, i synnerhet `dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml` och/eller `dashboard/cards/brewzilla_mash_in_controls_sv.yaml`. Uppdatera webbläsarcache.
4. Kontrollera `button.brewassistant_start_mash_circulation` och `sensor.brewassistant_brewzilla_control_reason` med attributet `physical_mash_interlock_active` (ska finnas även om värdet är `false`). Vid aktiv sekvens ska även fas, tidsfält och fysiskt mål finnas. Kontrollera verklig pump- och värmeåterkoppling, processtemperaturens rapportfärskhet och ABORT.
5. Kör **endast ett övervakat water-only-test** enligt det svenska protokollet. Avbryt vid oväntad pumpstart, felaktigt målbyte eller avvikande återkoppling. Test med malt kommer separat först efter godkänd styr- och säkerhetsverifiering.

## Kända begränsningar

- Fysiskt fälttest av interlocken återstår. Grön CI innebär inte att utrustningen är säker för obemannad körning.
- Spärren för fysisk mäskvila är i denna patch verifierad i kod för den dokumenterade **Brewfather-vägen**; andra källor och hela bryggdagen kräver separat validering.
- Pumpens procentvärde är ett inställningsvärde, inte en flödesmätning. Verklig återkoppling och konservativ värmning medan pumpen är avstängd måste granskas på plats.
- Den förra water-only-körningen slutade i ABORT och ska inte återupptas med gamla kvitteringar; börja bara en ny session efter säker återställning och rätt installerad version.

## Dokumentation från samma versionspaket

- [Svenskt testschema](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.11/docs/physical-mash-test-plan-2026-09-19_sv.md)
- [Engelskt testschema](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.11/docs/physical-mash-test-plan-2026-09-19.md)
- [Fysisk mash-interlock och verifierat fel](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.11/docs/physical-mash-control-contract-2026-09-19.md)
- [HLT SIM-1, fältobservationer](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.11/docs/hlt-sim1-field-validation-2026-09-19.md)

**Versionsidentitet:** release-titel `BrewAssistant v0.2.0-beta.11 — korrigerad övervakad testversion` · tagg `v0.2.0-beta.11` · manifest `0.2.0-beta.11` · målbranch `dev` · slutcommit = SHA som verifieras och taggas vid publicering. Ingen tidigare tagg återanvänds.
