# BrewAssistant v0.2.0-beta.14 – releasekandidat för övervakat vattenprov

**Repository:** `Jocke1970/brewassistant-beta`  
**Version i manifest:** `0.2.0-beta.14`  
**Release-status:** kandidat; ännu inte taggad, publicerad eller installerad. Publicera endast som GitHub **Pre-release** efter releasegranskning. Lämna publicerade beta.12 och beta.13 oförändrade.

> [!WARNING]
> Detta är inte ett godkännande av fysisk säkerhet. Kod- och isolerade HA/RCL-tester verifierar inte att BrewZillas värmare, pump eller huvudström faktiskt slås av. Testa bara med vatten, närvarande operatör och separat fysisk kontroll. Read-only kan inte återkalla redan skickade molnkommandon eller blockera BrewZillas egna reglage och externa RCL-automatik.

## Ändringar jämfört med beta.13

- **En enda styrbehörighetsswitch:** `switch.brewassistant_brewzilla_observe_only`. **PÅ = BA read-only:** BA får läsa, logga och lära passivt men skickar inte vanliga styrkommandon till BrewZilla. **AV = BA kan styra igen**, men först efter atomisk kontroll av behörig bryggkälla och sex färska BrewZilla-återläsningar. Nekas kontrollen stannar switchen PÅ. HA-omstart är fail-closed och kräver nytt operatörsval. Att slå PÅ skickar inga avstängningskommandon eller 0 %.
- Den gamla `switch.brewassistant_brewzilla_orchestration_enabled` hade ingen verksam spärrfunktion. Den registreras inte längre; enbart dess exakta HA-entitetsregisterpost tas bort vid switchplattformens uppstart. **Uppdatera egna dashboardkort, automationer och skript som refererar till den gamla entiteten** – den är ingen ersättning för read-only-switchen.
- Read-only spärrar BA:s automatiska hot-side-utgångar, vanliga policyförfrågningar, gamla kvittenser och BA-transport av manuellt önskade börvärden. Även vanliga BA-OFF/0 är blockerade så att BA inte stör lokalt vald reglering. Gammal pending-plan och ägd reglering ogiltigförklaras vid växling; de får inte återspelas vid återaktivering.
- **ABORT är ett separat nödstopp och blockeras aldrig av read-only eller normalt källägarbeslut.** Det spärrar fortsatt positiv BA-styrning och försöker stoppa aktiv RAPT-profil samt skicka OFF/0 till värmare, pump, utilization och huvudström via HA:s tjänsteregister. Fel per kommando loggas; ett skickat tjänsteanrop är inte bevis på att fysisk avstängning har skett. Kontrollera alltid BrewZilla fysiskt. ABORT-spärren återställs separat efter kontroll.
- **Manual Brewday i read-only:** använd det separata operatörskortet `dashboard/cards/brewzilla_observe_only_sv.yaml` (engelsk spegel `.yaml`) tillsammans med `dashboard/cards/brewassistant_manual_brewday_sv.yaml` i din personliga bryggdagsvy. Det nya kortet innehåller direktreglage för RCL/BrewZillas temperaturmål, värme-/pumputnyttjande och värmar-/pumpswitchar. De går på ditt initiativ **direkt via HA:s RCL-entiteter, inte via BA:s automatiska transport**. Knappstyrningen har bekräftelser. Observera att talfälten i det äldre Manual Brewday-kortet är BA-ägda önskade värden och **inte** skickas till BrewZilla i read-only; använd direktreglagen i observationskortet för faktisk manuell ändring.
- Direktreglagen i observationskortet visas endast om read-only är PÅ, aktuell källa är `Manual Brewday`, `binary_sensor.brewzilla_profile_active` rapporterar `off` och ABORT inte är aktiv. Om profilen är `on`, `unknown`, `unavailable` eller saknas visas inga direktreglage. Bekräfta verkligt profil-STOP och kontrollera hårdvaran innan manuell övertagning. Denna spärr gäller kortets synlighet, **inte en global behörighetsspärr på RCL:s direkta HA-entiteter från andra dashboards**.
- ABORT och read-only-switch finns överst i observationskortet även när direktreglagen är dolda. Den här modulen är ett fristående dashboardkort enligt `dashboard/README.md`: den monteras inte automatiskt i användarens redan anpassade dashboard.
- RCL-forken `v0.5.0-beta.1` ändras inte i denna BA-kandidat.

## Test och acceptans

- Python-sviten omfattar **387 testfall** efter två nya releasegrindar. Verifiera slutresultat på exakt sista release-SHA för Python 3.11, 3.12 och 3.13 samt kvalitetskontroll, HACS, Hassfest och isolerat HA/RCL-test; äldre gröna körningar får inte räknas som bevis för ändrad kod.
- Isolerat HA/RCL-test använder Home Assistant Core 2026.9.3 på Python 3.14.2, publicerad RCL-beta.1 och verkligt HA-tillstånds- och tjänsteregister med testmottagare i stället för moln/hårdvara. Det prövar BA:s ordinarie write-spärr, ABORT:s stoppförsök och passiv learning/audit. Lovelace-panelernas statiska villkor kontrolleras av releasegrindarna. Detta är **inte** ett klicktest av den installerade dashboarden eller en komplett riktig config-entry-uppstart.
- Kvar för fysisk driftsverifiering: komplett BA/RCL-uppstart i användarens HA, spårning av verkliga utgående molnkommandon, byte till/från read-only under pågående bryggning, korrekt Manual Brewday-reglage/återrapportering, loggning/energi efter omstart och framför allt bekräftat fysiskt ABORT. Använd inte detta som grund för obevakad körning.

## Praktiskt vattenprov när prereleasen är publicerad

1. Installera den exakta nya taggen via HACS först när BrewZilla är inaktiv. Säkerställ att RCL-fork och integrationernas poster är korrekta. Starta om HA; bekräfta att BA read-only står PÅ och att ingen automatisk BA-utgång skickar BrewZilla-kommando.
2. Lägg både Manual Brewday-kortet och observationskortet i bryggdagsvyn. Verifiera att den gamla `orchestration_enabled` är borta och att det endast finns en read-only-switch.
3. Verifiera RAPT-profil-STOP innan direktreglagen används. Starta Manual Brewday under uppsikt, använd direct RCL-reglage på observationskortet och kontrollera att BA inte skriver över valt temperaturmål, utilization eller ON/OFF. Läs av faktisk BrewZilla-status; loggning och learning ska fortsätta passivt.
4. Prova ABORT under kontrollerade vattenförhållanden med möjlighet till fysisk avstängning. Kontrollera faktisk värmare, pump, huvudström och effekt oberoende av HA:s kvittenser. Återställ ABORT och BA-styrning endast efter fysisk kontroll.
5. Stoppa provet om BA ändrar manuellt valda värden, RCL-status saknas, läsning blir gammal eller fysisk respons avviker.

**Publiceringsordning:** granska all divergens mellan release, dev och beta utan att pusha tester till dev; låt slutlig beta-kod verifieras på exakt beta-merge-SHA. Skapa därefter en ny oflyttad tagg `v0.2.0-beta.14`, markera GitHub-releasen **Pre-release**, verifiera manifestversion och tagg. Ingen promotion till `main`.
