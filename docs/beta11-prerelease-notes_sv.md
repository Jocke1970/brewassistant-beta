# BrewAssistant v0.2.0-beta.11 — korrigerad övervakad testversion

> [!WARNING]
> **Endast övervakade water-only-tester.** GitHub Actions och kodtester ersätter inte verifiering i Home Assistant, RAPT Cloud Link och BrewZilla. Kör inte obevakad bryggning och använd inte malt förrän water-only-protokollet är godkänt. HLT SIM-1 är enbart simulering och är ingen elektrisk säkerhetsspärr.

## Viktig korrigering av beta.10

Den publicerade GitHub-releasen `v0.2.0-beta.10` pekar på en gammal commit (`b8f2f58463865d443855adb67cbc23f181fb9c58`) vars integrationsmanifest anger `0.2.0-beta.9` och vars `brewzilla/__init__.py` **inte** installerar den nya fysiska mash-interlocken. Beta.10:s releasetext beskriver därmed fel kodpaket. **Använd inte beta.10 för nästa styrtest.** Flytta inte den gamla taggen och återanvänd inte versionsnumret.

Den korrigerade publiceringsvägen är **`dev` → PR/merge commit → `beta` → tagg och GitHub Pre-release från verifierad `beta`-commit → HACS-installation → övervakat fälttest**. `main` är reserverad för senare stabil version och berörs inte av denna prerelease. Se [`CONTRIBUTING.md`](../CONTRIBUTING.md). Skapa inga extra branches.

## Ändringar avsedda att ingå i beta.11

### Mash-In, maltbäddsvila och fysiskt temperaturmål

Den fysiska styrspärren adresserar fyndet från water-only-testet 19 september: Brewfather gick vidare från 66 °C till 72 °C innan BrewAssistant hade slutfört den fysiska 66 °C-vilan.

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

## Publiceringsgrind — hela kedjan måste stämma

1. Verifiera på `dev` att `custom_components/brewassistant/manifest.json` anger `0.2.0-beta.11`, att `custom_components/brewassistant/brewzilla/__init__.py` installerar `brewzilla_physical_mash_interlock`, och att release-Markdown, YAML och testschema hör till samma kandidat.
2. Öppna och granska PR **`dev` → `beta`** (PR #213 för denna kandidat). Använd **Create a merge commit**, aldrig squash/rebase. Denna PR innehåller även annat utvecklingsarbete; granska hela diffen och behåll `dev`.
3. Efter merge: notera den **nya `beta`-mergecommittens fullständiga SHA**, kontrollera att branch `beta` pekar dit och att **CI (Python 3.11, 3.12, 3.13), HACS och Hassfest är gröna just på den SHA:n**. Grön `dev`-CI före merge räcker inte.
4. Kontrollera `manifest.json`, installationen av interlocken samt Markdown **på den verifierade `beta`-commiten**. Om något saknas: publicera inte; rätta på `dev`, gör en ny promotion och välj vid behov nytt versionsnummer.
5. Skapa den **nya** taggen `v0.2.0-beta.11` från exakt verifierad `beta`-mergecommit. GitHub Releases: **Target = beta**, titel `BrewAssistant v0.2.0-beta.11 — korrigerad övervakad testversion`, markera **Set as a pre-release**, lämna senaste/stabil av och klistra in **hela detta Markdown-dokument** som release description. Skapa inte taggen från `dev` eller `main`.
6. **Efter publicering:** läs taggens verkliga commit-SHA och dess egna `manifest.json` och `brewzilla/__init__.py` via `.../blob/v0.2.0-beta.11/...`. Matcha SHA mot den verifierade `beta`-mergecommiten, version `0.2.0-beta.11` och interlock-installationen. Om någon kontroll fallerar: stoppa distribution/test; publiceringssidan eller texten är inte tillräckligt bevis.

## Uppdatering i Home Assistant — först efter godkänd publiceringsgrind

1. Avsluta föregående körning, verifiera fysiskt att pump och värmare är OFF och säkerhetskopiera nuvarande integration och dashboard-YAML.
2. Installera **exakt `v0.2.0-beta.11`** via HACS med prereleases aktiverade; kontrollera valt versionsnummer. Installera inte beta.10 och kopiera inte över ett äldre brancharkiv.
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

**Versionsidentitet:** release-titel `BrewAssistant v0.2.0-beta.11 — korrigerad övervakad testversion` · tagg `v0.2.0-beta.11` · manifest `0.2.0-beta.11` · **taggens commit = verifierad mergecommit på `beta`**. `main` förblir orörd. Ingen gammal tagg återanvänds.
