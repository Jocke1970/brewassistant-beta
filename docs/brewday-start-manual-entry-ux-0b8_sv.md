# BrewAssistant 0b8-dev: tydlig RCL-handoff och synlig Manual Brewday-start

## Operatörsflöde

### Aktiv RAPT/BrewZilla-profil

RAPT Cloud Link äger aktiv profil, recept, steg och temperaturmål.
När BA har verifierad aktiv RCL-session och alla säkerhetskontroller passerar
ska den gröna knappen säga **AKTIVERA BA-ASSISTANS**, inte STARTA BRYGGNING.

- Tryck på gröna knappen och bekräfta efter fysisk kontroll av vätskenivå,
  pumpväg och BrewZilla.
- Backend kontrollerar samma profil-/session-/steg-ID, mål och färsk BZ-telemetri
  vid själva START-transaktionen, sedan släpper den BA READ-ONLY.
- BA kan då hjälpa med godkänd heat/pump-assistans **via RCL**, inte direkt via
  en parallell BrewZilla-väg.
- RAPT-profilen startas inte av denna knapp: den **kör redan**.
- READ-ONLY-switchen är en skyddsspärr och får inte stängas av manuellt för att
  kringgå START. ABORT är alltid separat och överordnad.

### Ingen aktiv Brewfather/RCL-källa och ingen aktiv manuell session

Det manuella premiumkortet var tidigare endast synligt när
`source=Manual Brewday` **och** runtime_state inte var `idle`. Det gjorde
det omöjligt att hitta första knappen om man började utan Brewfather/RCL.

Nu har hela kortet två oberoende, source-gated delar:

1. **Manual Brewing – Förbered bryggdag** visas när
   `switch.brewassistant_show_brewday=on`,
   `sensor.brewassistant_brewday_runtime_source=None`,
   `sensor.brewassistant_brewday_runtime_state=idle` och
   `sensor.brewassistant_manual_brewday_status=idle`.
   Kräver bekräftelse och anropar enbart den **redan guardade**
   `brewassistant.manual_brewday_prepare`. Ingen fysisk aktivering.
2. Det kompletta Manual Brewday-kortet visas precis som tidigare först när
   `source=Manual Brewday` och runtime_state inte är `idle`.
   Innehåller steg, pauser, kvittenser, processdata och manuella framsteg.

Om RAPT är aktiv eller kvarhåller ownership, Brewfather kör eller ABORT är
aktiv får PREPARE inte ge styrbehörighet. Visningsvillkoren är ingen
säkerhetsspärr; backend `GuardedManualRuntimeSession` upprätthåller
external ownership.

## Känd begränsning – fysisk BA-kontroll i Manual-läge

`brewassistant.brewday_start_verified` stöder för närvarande bara
**RCL-assistans för redan aktiv och verifierad RAPT-session**.
BA READ-ONLY kan inte stängas av manuellt; backend kräver den transaktionen.
Därmed går det att **förbereda och köra Manual-processen** i BA men inte att
ge BA fysisk automatisk värme-/pumpstyrning via samma knapp i dagens version.

Att lösa den sista punkten kräver en **separat verifierad Manual START** med
source-absence/active-stop-kontroll, ABORT/resync/physical preflight, explicit
operator approval, ingen tyst övertagning, inga kommandon till BZ utanför
RCL. Spåras i issue #258.

## Leverans

Ändrade kompletta YAML-kort:

- `dashboard/cards/brewday_control_status_sv.yaml` och `.yaml`
- `dashboard/cards/brewassistant_manual_brewday_sv.yaml` och `.yaml`

Detta är en **UI-förbättring på dev**, inte en ny installerad beta.
Manuellt inklistrade Lovelace-kort behöver ersättas som **hela YAML-kort**;
en HACS-backenduppdatering byter inte automatiskt deras konfiguration.
