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


## Fältuppföljning 2026-10-10: reconnect/HA-omstart

Flight recorder visade aktiva RCL-profilidentiteter medan Brewday låg
`resync_required`. Första fallet började 15:40:36 UTC och släpptes
först efter `brewday_reconnect_ack` 15:57:23 UTC, alltså en manuell
kvittens. Det var **inte** belagd långsam RAPT Cloud Link-pollning.
En HA-initialisering syns 15:56:12 UTC, med enhetssensorer återlästa
15:56:58 UTC. En senare omstart 16:29 UTC följdes av ny
`resync_required`, men ingen kvittens syns före ABORT 16:36:55 UTC.

Nuvarande backend gör detta avsiktligt:
`async_load_brewday_recipe_context` återställer receptkontext men
lägger på `ha_restart_requires_external_reconciliation` och kräver
`acknowledge_external_reconnect` med live RCL session + steg. Återanslutning
ska inte automatiskt återaktivera aktuatorer från gammal snapshot.
Däremot bör UI uttryckligen visa **VÄNTAR PÅ OPERATÖRSKVITTENS**,
aktuellt RCL-session/steg, och korrekt kvittensknapp med detaljerad
blockerande orsak. Det är separat framtida UI/backend-arbete,
inte en anledning att ta bort spärren eller nollställa sessionen.

### Korrigerad Manual YAML-struktur

PR för komplett YAML-reparation är separat: första och andra
`conditional`-kortet måste vara två poster (`- type: conditional`)
under samma `vertical-stack.cards`. Tidigare dev-kort innehöll
`type: conditional` direkt under listan utan listmarkör och visade
`Ingen typ angiven`. Regressionstest parsar nu båda fullständiga
korten som YAML och verifierar två kortposter.
