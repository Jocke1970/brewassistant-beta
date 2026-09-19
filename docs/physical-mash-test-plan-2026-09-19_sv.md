# Brewday / BrewZilla: testschema för fysisk mäskning och maltbäddsvila – 2026-09-19

**Status: endast kod och CI verifierade. Fälttest i Home Assistant/RAPT/BrewZilla återstår.** Detta är ett övervakat utvecklingstest, inte obemannad bryggautomatik. Gäller verifierad kod på befintliga `dev`, inte `main`. HLT är fortfarande **enbart simulering** och ingår inte i testet.

> [!WARNING]
> Den publicerade `v0.2.0-beta.10` pekar på fel commit och saknar den nya mash-interlocken. **Använd inte beta.10 för nästa styrtest.** Skapa/publicera i stället `v0.2.0-beta.11` från exakt verifierad slutcommit på `dev`, där manifestet anger `0.2.0-beta.11` och `brewzilla/__init__.py` installerar `brewzilla_physical_mash_interlock`. Kontrollera båda filerna via **taggen**, inte enbart via `dev`, före HA-installation. Flytta inte den gamla taggen och skapa ingen ny branch. Se [`beta11-prerelease-notes_sv.md`](beta11-prerelease-notes_sv.md).

## Syfte och förväntat beteende

Brewfather tillhandahåller receptets schema. Om Brewfather går vidare till 72 °C får det **inte** höja BrewZillas mål medan den fysiska **66 °C-vilan** fortfarande pågår. Vid **Mash-In Started** släpps strike-målet till det verkliga mäskmålet och pumpen ska förbli avstängd. Det normala beviset för **Mash-In Complete** är att BA observerar Brewfather **PAUSED efter Started** och därefter **RUNNING** när operatören trycker FORTSÄTT. Manuell Complete är reservväg, inte ett frikort för pumpstart.

Vid Complete ska pumpen ställas till **0 % och OFF** och en **10-minuters maltbäddsvila** börja parallellt med den fysiska mäskvilan. När de tio minuterna har gått får BA enbart **föreslå** 25 %; först en aktiv knapptryckning får skicka LOW FLOW-kommandot. En femminutersperiod med lågt flöde börjar först efter faktisk återkoppling från BrewZilla. Därefter föreslås cirka 50 %, med **en andra separat operatörskvittens**. Nästa temperaturmål får släppas igenom först när både den fysiska vilan är färdig och normalt flöde är bekräftat. Den fysiska mäskvilans ordinarie timer börjar enligt befintlig regel: Mash-In Complete och processtemperatur inom **±0,3 °C** från mål. Den startar inte automatiskt bara för att settling-timern gör det.

**Observera:** Pumpens procentsatser är *inställd utilization*, inte uppmätt genomströmning. BA saknar flödes- och nivågivare: du måste själv övervaka vätskenivå, bädd och avrinning. Timerutgångarna får aldrig slå på pumpen. Färsk processtemperatur krävs för båda positiva pumpkommandona; gammal givardata ska neka kommandot. Efter oväntad HA-omstart mitt i mäskningen får BA inte härleda tidigare kvitteringar från ett senare Brewfather-steg. Förvänta spärrat återhämtningsläge, inte automatisk pumpstart. ABORT och separata säkerhetsspärrar har alltid företräde.

## A. Förberedelser och installation

- [ ] Avsluta föregående bryggkörning. Bekräfta att BrewZilla är inaktiv och att värmare och pump är **OFF**.
- [ ] Säkerhetskopiera installerad `custom_components/brewassistant` och dashboard-YAML. Anteckna installerad version och Git-revision.
- [ ] Kontrollera att CI (Python 3.11–3.13), HACS och Hassfest är gröna för exakt commit som ska taggas. Skapa `v0.2.0-beta.11` med **`dev` som target**, och verifiera att taggens commit är identisk med denna slutcommit. Kontrollera taggens manifestversion och installerad interlock-kod.
- [ ] Installera **endast den verifierade `v0.2.0-beta.11`** via HACS med prereleases aktiverade. Beta.10 är felpaketerad. Om release/taggkontrollen misslyckas ska **inget fysiskt test påbörjas**. En Git-commit uppdaterar inte HA automatiskt.
- [ ] Starta om hela Home Assistant.
- [ ] Uppdatera det dashboardkort du faktiskt använder från **samma verifierade tagg**: `dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml` och/eller `dashboard/cards/brewzilla_mash_in_controls_sv.yaml`. YAML som tidigare klistrats in i HA ersätts inte av en integrationsuppdatering. Uppdatera webbläsarens cache.
- [ ] Under **Utvecklarverktyg → Tillstånd**, kontrollera att `sensor.brewassistant_brewzilla_control_reason` har attributet `physical_mash_interlock_active` (det ska finnas även i viloläge när värdet är `false`). Under relevanta faser ska `mash_recirculation_phase`, `mash_physical_hold_target`, nedräkning och återkopplingsfält visas.
- [ ] Kontrollera att `button.brewassistant_start_mash_circulation` finns. En knapp med state `unknown` bevisar inte att den kan verkställa; kontrollera installation och fas innan den används. Om interlock-attribut eller nödvändiga entiteter saknas: **stoppa innan fysisk testning**.
- [ ] Bekräfta färsk processtemperatur, faktiskt BrewZilla-mål, värme- och pump-utilization samt båda brytarnas verkliga status. Säkerställ att ABORT är lätt åtkomligt.
- [ ] Kontrollera källa, steglista och mål-ägarskap i kallt/observationsläge där det är möjligt.
- [ ] Planera ett separat **övervakat water-only-test** med lämplig vattennivå enligt BrewZillas instruktioner. Kör inte tomt kärl, torr pump eller obevakad uppvärmning. Vatten kan inte verifiera en maltbädd; ett separat litet malttest får övervägas först när alla styr- och återkopplingskontroller har passerat.

## B. Testpunkter – markera varje rad

| Klart | Kontrollpunkt | Förväntat beteende i BA | Kontrollera fysiskt / i RCL |
| --- | --- | --- | --- |
| ☐ | BF PLAY, Heatstrike, READY | Befintlig Heatstrike och automatisk READY ±1 °C respektive manuell override högst ±2 °C fungerar som tidigare. | Aktiv källa, MASH- och WORT-temperatur, BrewZilla-mål samt värme-/pumpåterkoppling. |
| ☐ | Mash-In Started | BA måste senare observera BF PAUSED **efter** Started för automatisk Complete. Strike-målet ändras till mäskmålet; pump **OFF / 0 %**. | Klockslag, `mash_in_gate_state`, effektivt mål, faktisk mål- och pumpåterkoppling. |
| ☐ | BF FORTSÄTT | PAUSED→RUNNING ger Mash-In Complete och fas `settling` – **ingen automatisk pumpstart**. | Tidsstämplar; pump-utilization 0 % och brytare OFF. |
| ☐ | Settling 0–10 min | `settling`; fysiska 66 °C är fortsatt styrmål även om BF visar 72 °C; lågflödesknappen dold. | Jämför begärt och faktiskt mål, fysisk timer, båda temperaturerna, verklig värme och pump. |
| ☐ | Settling går ut | Endast `recirculation_ready`; timern skickar **inget** pumpkommando. | Nedräkning 0; pumpbrytare fortsatt OFF. |
| ☐ | Första kvitteringen | Med färsk processtemperatur och verifierat pump OFF: cirka 25 % + pump ON. `low_flow_pending` tills återkoppling, därefter `low_flow`. | Knapptryckningens tid, utilization, brytarens `last_reported`, synligt flöde och vätskenivå. |
| ☐ | Fem minuter efter lågflödets återkoppling | `normal_ready`; 25 % kvarstår och pumpen höjs **inte automatiskt**. | Fas och timer, faktisk utilization, visuell kontroll av bädd och avrinning (vid senare malttest). |
| ☐ | Andra kvitteringen | Efter färsk givare och bedömt gott flöde: cirka 50 %; `normal_pending` och därefter `normal` först vid återkoppling. | Tid, utilization, pumpbrytare och vätskenivå. |
| ☐ | Innan fysisk 66 °C-vila är färdig | BF får visa nästa steg, men BA begär fortfarande **66 °C**. | Jämför BF-mål, BA:s begärda mål och BrewZillas verkliga mål. |
| ☐ | Fysisk 66 °C-vila klar + normalt flöde bekräftat | Interlock släpper nästa steg; 66→72 °C-rampen kan därefter passera ordinarie Supervised Apply och säkerhetsspärrar. | `mash_physical_hold_complete`, fas, BF/BA/BZ-mål och när uppvärmningen verkligen börjar. |
| ☐ | Gammal temperaturdata / utebliven pumpåterkoppling | Ingen ny pumpstart vid stale givare. Saknad återkoppling i mer än **120 s** ska ge `blocked`. | Orsakskod, inga positiva skrivningar. ABORT/felsök i stället för blinda omförsök. |
| ☐ | Källbyte, ABORT, oväntad HA-omstart | Inga tidigare kvitteringar eller pumpstarter får återskapas från BF ensamt; explicit säker återhämtning eller ny session krävs. | `blocked`/`recovery_required`, verkliga utgångar och audit-historik. |

**Resultat per rad:** skriv `PASS`, `FAIL` eller `EJ TESTAD` och notera tid/kort kommentar. Ett water-only-test kan inte ge PASS för faktisk maltbädd och avrinning.

## C. Omedelbara stoppkriterier

Avbryt om BrewZillas verkliga mål höjs mot nästa receptsteg innan den fysiska 66 °C-vilan är klar; pumpen startar eller ändrar utilization utan separat kvittens; vätska stiger ovanför maltbädden, avrinningen stannar, pumpen tappar primning; MASH och WORT avviker på ett farligt sätt; kommenderat läge och faktisk återkoppling inte stämmer; eller källa/session blir oklar. Säkra utrustningen manuellt eller använd ABORT efter situationens behov. Spara observerade värden och Flight Recorder innan återställning om det kan göras säkert. **Grön GitHub Actions betyder inte verifierad hårdvarusäkerhet.**

## D. Dokumentera efter testet

Anteckna Git-commit och tagg, HA-version, installations-/integrationsversion, version av dashboard-YAML, Brewfather-recept och exakta stegtider, batch-/vattenvolym, eventuell maltmängd och maltkrossgap, vald styrkälla, RCL:s rapporttider, MASH-/WORT-temperaturkurvor, BrewZillas mål-/värme-/pumpinställningar och faktisk återkoppling, alla knapptryckningar, Flight Recorder-/audit-export samt fel och oväntade automatiska skrivningar.

Sammanställ `PASS / FAIL / EJ TESTAD` per kontrollpunkt. Först efter godkänt **övervakat** fälttest kan koden bedömas för fortsatt releasehantering. Granska särskilt konservativ värmereglering när pumpen står stilla och verklig återkoppling efter pumpkommandon innan någon obemannad användning övervägs.

**Engelsk källversion:** [`physical-mash-test-plan-2026-09-19.md`](physical-mash-test-plan-2026-09-19.md). Detta är den svenska motsvarigheten med samma säkerhets- och funktionskrav samt ett tillägg för det felaktigt taggade beta.10-paketet.
