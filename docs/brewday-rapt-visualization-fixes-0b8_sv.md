# BrewAssistant 0b8-dev: RAPT-profilkort och Brewday-tid

Status: **UI-kandidat för dev**. Det här är inte en fysisk
verifiering eller en ändring av RCL/BrewZillas styrkontrakt.

## Fältobservation – 2026-10-10

Operatören såg i RAPT Profile Runtime-kortet:

- `RAPT-target: 0.0 °C`
- `runtime-target: 31.0 °C`
- `profilsteg: 0/0`
- aktuellt direktiv: `Mash In`
- Brewday Control: `TID KVAR: —`, trots att RCL ägde en aktiv profil.

RAPT:s verifierade profilkontrakt omfattade sex steg. Den modernare
`rapt_profile_runtime_sv.yaml` visade redan okänt profilindex som `—`,
**aldrig `0/0`**. Därför talar skärmbilden starkt för en äldre laddad
dashboardkort-definition eller stale frontend-innehåll. Rätt backendversion
ensam garanterar inte att en gammal Lovelace-kort-YAML automatiskt byts ut.

## Ändringar

### RAPT Profile Runtime (EN/SV)

- Visar `RAPT-target` från RCL `step_target_temperature` (inte ett
  lokalt BA-kontrollmål).
- Visar separat `runtime-target` från BA, och separat **BZ aktuell**
  direkt från `sensor.brewzilla_temperature`.
- Uppmätt BZ-temperatur visas bara vid ett rimligt 0–105 °C-värde med
  senaste registrerade mätvärde högst 90 sekunder gammalt; annars `—`
  med diagnostisk förklaring.
- `0 °C` som falskt hot-side-RAPT-mål för värmesteg (Heatstrike,
  Mash In, Mash Rest etc) visas som okänt/`—` med RCL-varning. Ett
  explicit ChillOut-värde på 0 °C behålls som processmarkör, inte ett
  nytt värmekommando.
- `0/0` är inte ett giltigt profilsteg och visas som `—`.
- RCL `step_length` anges som sekunder: planerad Duration visas i
  minuter efter division med 60. Det är **planerad längd**, inte
  `tid kvar` eller en autentiserad realtidstimer.
- Layouten växlar antal kolumner efter tillgänglig bredd.

### Brewday Control / Status (EN/SV)

- För aktiv RCL med `profile_step_end_type == Manual`: `TID KVAR`
  visar **MANUELLT** och `Väntar på manuellt RAPT-stegbyte` i stället
  för ett svårtolkat streck. Ingen gissad nedräkning.
- För `profile_step_end_type == Duration` utan verifierad aktiv
  timertid: `—` + *Planerat XX min · tid kvar ej verifierad*.
- För verifierad realtidsåterstående tid: använd fortsatt befintlig
  BA-sensor. Annars `—`; RAPT har inte lämnat en godkänd lokal
  timer-start/paus/fortsättningskvittens.
- Den föråldrade hårdkodade UI-rubriken `0b6 UI` har tagits bort.

## Uppdatera dashboarden utan att fastna i frontend-cache

1. Kontrollera backendversion i HACS (0b7 testbeta eller nyare) och
   tillstånd på `binary_sensor.*_profile_active`, framför allt
   `ba_source`, `profile_contract_complete`, `step_name`,
   `step_target_temperature`, `step_number` och `step_count`.
2. **Ersätt hela Lovelace-kortdefinitionen** med
   `dashboard/cards/rapt_profile_runtime_sv.yaml` från rätt branch,
   och motsvarande `dashboard/cards/brewday_control_status_sv.yaml`.
   En uppdatering av HACS-integrationen byter inte nödvändigtvis YAML som
   redan kopierats till en egen dashboard.
3. Kontrollera att den gamla texten `0b6 UI` inte syns längre och att
   RAPT-kortet visar en separat ruta för **BZ aktuell**.
4. Vid frontend-cacheproblem: kontrollera att rätt dashboard och eventuella
   separata resurser laddas om; ändra inte BZ-styrning som cacheåtgärd.

## Säkerhetskontrakt

Inga ändringar av ABORT, read-only, START-preflight, källägarskap,
värme-/pumputgångar eller RCL-kommandon i denna UI-fix.
Oavsett färg är kortet **inte** bevis för fysisk OFF.
