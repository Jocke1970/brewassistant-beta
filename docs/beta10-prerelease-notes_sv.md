# BrewAssistant v0.2.0-beta.10 — övervakad testversion (dev)

> [!WARNING]
> **Pre-release för utveckling och övervakade water-only-tester.** Kodtester är inte ett bevis på säker funktion i Home Assistant, RAPT Cloud Link eller BrewZilla. Kör inte obevakad bryggning och använd inte malt förrän water-only-protokollet är godkänt. HLT-funktionerna nedan är enbart simulering och kan inte skydda en elkrets.

## Vad som är nytt

### Fysisk Mash-In-spärr och maltbäddsvila

Den här testversionen adresserar felet från water-only-testet 19 september där Brewfather gick vidare från 66 °C till 72 °C samtidigt som BA:s fysiska 66 °C-vila ännu inte var färdig.

- Mash-In Started släpper strike-temperaturen till verkligt mäskmål och håller pumpen **OFF / 0 %**.
- Befintligt strikta Brewfather-kontrakt består: BA ska ha sett **PAUSED efter Mash-In Started**, och ett senare **RUNNING / FORTSÄTT** markerar Mash-In Complete. Manuell Complete är reservväg.
- Mash-In Complete ska nu stänga av pumpen och starta **10 minuter settling**. Den ska inte starta cirkulationen direkt.
- Efter tio minuter visas en separat kvittering för **lågflöde cirka 25 %**. Väntetiden i sig får aldrig starta pumpen. Femminutersnedräkningen börjar efter återkopplad lågflödesstart.
- Efter fem minuter visas en **andra kvittering** för normalt flöde cirka **50 %**. Höjningen sker inte automatiskt.
- Det fysiska mäskmålet ska hållas kvar även när Brewfather visar nästa steg. Nästa temperaturmål släpps först efter att både den fysiska vilan och normalt flöde har bekräftats.
- Försök till pumpstart nekas vid gammal processtemperatur. Saknad pumpåterkoppling kan blockera sekvensen. Efter HA-omstart får tidigare kvitteringar inte återskapas automatiskt. ABORT har fortsatt företräde.

**25 och 50 % är pumpens inställda utilization – inte uppmätt flöde.** BA har ingen nivå- eller flödesgivare. Operatören ansvarar för att kontrollera cirkulation, vätskenivå och avrinning.

### Operatörsgränssnittet

- Svenska och engelska Brewday-kort har uppdaterats för att visa settling-/recirkulationsstatus, nedräkning och separat kvittering.
- Missvisande text om att Brewfathers FORTSÄTT skulle starta pumpen automatiskt är borttagen.
- RCL:s diagnostik för gammal processgivare och manuell strike-kvittens är kvar.
- Om YAML-kort tidigare har klistrats in i Home Assistant måste **kortet uppdateras separat**; en HACS-uppdatering av integrationen ersätter inte det.

### HLT SIM-1 från PR #212

- Integrerad **read-only HLT-simulator** med sensorer, loggning och dashboard.
- Ändringar efter första water-only-observationen förbättrar hanteringen av äldre men oförändrade BrewZilla-inställningar och tolkning av rampsteg.
- **Ingen fysisk HLT-styrning, ingen faktisk effektbegränsning av BrewZilla och ingen elektrisk lastsäkring.** Modellen kräver ett eget framtida säkerhetsarbete innan den får styra utrustning.

## Tester och valideringsstatus

- Regressionstester finns för settling utan automatisk pumpstart, två kvitteringar, temperaturfärskhet, utebliven återkoppling, fysisk stegspärr samt återhämtning efter omstart.
- CI, HACS-validering och Hassfest måste vara **gröna på exakt den commit som taggas**. Kontrollera deras resultat i GitHub Actions innan publicering.
- **Fysisk verifiering av denna patch återstår.** Den föregående körningen var uttryckligen *water-only*; detta är inte godkännande för mäskning med malt.

## Uppdatera Home Assistant för test

1. Avsluta pågående körning. Kontrollera BrewZilla värmare/pump OFF och säkerhetskopiera installerad BrewAssistant och dashboard-YAML.
2. Installera **just `v0.2.0-beta.10`** via HACS med prereleases/betaversioner aktiverade. Kontrollera att HACS verkligen väljer rätt tagg, inte repositoryts standardbranch `main`. Installera inte från äldre brancharkiv.
3. Starta om hela Home Assistant.
4. Uppdatera de YAML-kort du faktiskt använder från samma tagg: `dashboard/cards/brewassistant_brewday_runtime_flow_sv.yaml` och/eller `dashboard/cards/brewzilla_mash_in_controls_sv.yaml`. Ladda om dashboard/webbläsarcache.
5. Kontrollera `button.brewassistant_start_mash_circulation` och interlock-fälten under `sensor.brewassistant_brewzilla_control_reason`. Kontrollera att RCL-data och både faktisk pump- och värmeåterkoppling är tillgängliga. **Stoppa om entiteter saknas.**
6. Utför ett övervakat water-only-test enligt det svenska testschemat nedan. Kör ingen riktig mäskning förrän styrning och säkerhetskrav har klarat fälttestet.

## Kända begränsningar / stoppsignaler

- Ny styrlogik är ännu inte verifierad på fysisk utrustning; HA-omstart mitt i mäsken kräver säker operatörsåterhämtning, inte automatisk fortsättning.
- Spärren för fysisk 66→72 °C-överlämning i denna patch gäller den dokumenterade **Brewfather-vägen**. Andra källor och hela bryggdagens slut-till-slut-flöde kräver separat validering.
- Det saknas verklig maltbädds-, flödes- och nivåmätning. Water-only testar styrkommandon, men inte faktisk avrinning genom malt.
- Konservativ värmereglering med pump OFF och bevis på faktisk pumpåterkoppling ska granskas i fälttest. Grön CI betyder inte säker hårdvara.
- Den efterfrågade totala bryggdagsklockan ingår **inte** i denna version.
- Ändrade dashboards måste installeras separat om de ligger som manuellt inklistrad YAML. Inget automatiskt utbyte av externa JS-filer ska förutsättas.

## Dokumentation och testprotokoll

- [Svenskt testschema: fysisk mäskning och maltbäddsvila](https://github.com/Jocke1970/brewassistant-beta/blob/dev/docs/physical-mash-test-plan-2026-09-19_sv.md)
- [Engelskt original](https://github.com/Jocke1970/brewassistant-beta/blob/dev/docs/physical-mash-test-plan-2026-09-19.md)
- [Fysiskt mäskstyrningskontrakt / fynd från 19 september](https://github.com/Jocke1970/brewassistant-beta/blob/dev/docs/physical-mash-control-contract-2026-09-19.md)
- [HLT SIM-1: fältvalidering 19 september](https://github.com/Jocke1970/brewassistant-beta/blob/dev/docs/hlt-sim1-field-validation-2026-09-19.md)

**Versionsidentitet:** GitHub-tagg `v0.2.0-beta.10` · `manifest.json` `0.2.0-beta.10` · målcommit: den verifierade slutcommitten på `dev` vid publicering. Skapa release från exakt denna commit, välj **Set as a pre-release**, lämna **Set as latest release** av och låt `main` vara orörd.
