# RAPT-källkontext i befintliga Brewday Audit och HLT JSONL

Status: kodutökning på feature-branchen till PR #215. **Ingen ny logg, ingen fysisk styrning och ingen ändring av BF/BT-sensorerna.** BF=jäsning, BT=brygginformation från samma Brewfather-källa och RAPT=alternativ vald brygginput. Befintliga fält och loggfilernas sökvägar bevaras.

## Brewday Audit

`brewday_rapt_audit_context.install_rapt_audit_context()` utökar befintliga `RUNTIME_FIELDS` och `BREWZILLA_RESULT_FIELDS` med metadata från den **redan valda normaliserade Brewday-snapshoten** och befintligt orchestration-resultat. Tillägget loggar bl.a. `source_status`, `target_temperature_source`, `profile_session_id`, `profile_step_id`, `profile_step_number`, `profile_source_available`, `profile_stop_guard_active`, `operator_abort_active`, `requested_target_source`, `rapt_sparge_phase`, `rapt_sparge_local_target_c` och `rapt_sparge_local_target_agrees`. Händelsesignaturen omfattar RAPT-session/steg och säkerhetsstatus så skilda steg inte slås samman till en tickrad. Tidigare lagrade auditposter behålls och deras fält omtolkas inte.

Audit har redan `source`, `stage`, `step`, `target_temperature`, `requested_target`, `applied_target`, BrewZillas separata device-/effective-target och uppmätta värden. En saknad RAPT-uppgift loggas inte som en påhittad siffra eller som bekräftat OFF. BF:s jäsningsmodul väljer aldrig bryggkälla på grund av dessa loggfält.

## HLT JSONL

Nya nycklar per loggrad: `brewday_source`, `brewday_runtime_state`, `brewday_source_status`, `brewday_target_c`, `brewday_target_source`, `rapt_profile_session_id`, `rapt_profile_step_id`, `rapt_profile_step_number`, `rapt_profile_source_available`, `rapt_profile_stop_guard_active`, `brewday_operator_abort_active`.

Alla nycklar kommer via `_brewday_trace_context(brewday)` från **exakt den normaliserade snapshot som HLT använder under aktuell tick**. Inga direkta BF-/BT-sensorläsningar görs för källidentiteten; BT får ändå fortsätta läsa och visa all data separat. Okända nyckelvärden blir JSON `null`. De sedan tidigare separata HA-publicerade diagnoserna (`*_ha_c`, `*_ha_age_s`) kan ligga en coordinator-uppdatering efter och får aldrig bli auktoritativ HLT- eller BrewZilla-styrinput.

`schema_version` är fortsatt 2 eftersom fälten är additiva; gamla loggrader kompletteras inte retroaktivt. Samma `hlt-sim-*.jsonl` per Brewday-session används. `record_type=transition` skrivs vid ändring av HLT-beslut eller vald source/session/step/target-context **vid nästa ordinarie HLT-tick**, även om 30-sekundersgränsen annars hade undertryckt provet. Det är **inte** en separat omedelbar HA-eventlyssnare; vid STOP/ABORT kan HLT-runtime avsiktligt avslutas utan ny JSONL-rad. Audit-loggens egna operator-/stopp-händelser är separat tidslinje. En fullständig eventdriven källbyteslogg återstår att verifiera före release.

HLT är fortfarande SIM-1: inga fysiska serviceanrop, ingen BrewZilla-effektbegränsning. Scenarioeffekt är inte godkänd elsäkerhetsgräns. En HA-avläsning av OFF bevisar inte fysisk frånskiljning. Ändringen ersätter inte sammanhängande HA- eller vatten-only-test efter installerad beta.
