## DEV PREVIEW — inför 2026.10.0b6 — premium Brewday UI och stale-varningar (ingen release)

- Nya kompletta Lovelace-paneler `dashboard/cards/brewday_control_status_sv.yaml` och `dashboard/cards/brewday_control_status.yaml`: källägare, läge, timer, target, fallback, `resync_required`, read-only, ABORT, manuell kvittens.
- Ny read-only-toggle och hårt villkorad `brewday_reconnect_ack`-knapp; backend verifierar alltid källan igen. Inget UI-bevis på fysisk OFF.
- Varningar för saknade, okända och inaktuella Pill-/SG-observationer återställda i `fermentation*.yaml` och `fermentation_cockpit_v2*.yaml` med röd ikon/text och 1-minuts refresh. Trösklar: 15 min gult, 20 min rött.
- `tests/test_b6_brewday_control_status_ui.py` och `docs/brewday-control-status-b6-preview_sv.md` tillagda.
- **Manuell åtgärd:** kopiera hela svenska panel-YAML:n till dashboarden; byt också jäsningskortens hela YAML för att få tillbaka stale-varningarna. Kräver inget HA-backendbyte utöver 0b5, ingen omstart för enbart Lovelace-ändring.
- **Releasestatus:** endast `dev`, `beta` (0b5) och `main` opåverkade.

## 2026-10-09 — v2026.10.0b5 — Brewday three-mode / RCL Assist

- Brewday får tre normala exekveringslägen: Manual Brewing, Brewfather Brewing och RCL Brewing.
- RCL/BrewZilla äger recept, steg, timer och target i RCL Brewing; BA skriver inte target eller normal heater-switch.
- Equipment Learning/Advice får automatiskt assistera heat-utilization samt pump ON/OFF/% när RCL authority är verifierad och observe-only är av.
- RCL- eller BF/BT-bortfall växlar temporärt till Manual Brewing med retained recipe context; återanslutning kräver identitetskontroll och kan låsas med `resync_required`.
- Retained extern timeline/profil konverteras nu till befintlig ManualPlan-motor så operatören kan fortsätta samma batch lokalt under avbrottet; extern cache ligger kvar som reconnect-referens.
- Global STOP/ABORT ligger kvar över samtliga källor.
- Fallback-recept sparas till HA Store; efter HA-omstart återskapas kontexten i pausat, fail-closed läge. `brewassistant.brewday_reconnect_ack` möjliggör operatörskvitterad återanslutning.
- Normal BA-actuation blockeras under källbortfall. Okänd remaining presenteras inte som en nystartad timer.
- Publicerad beta/main ändras inte av dev-arbetet; fysisk vattenacceptans återstår.

# BrewAssistant Changelog

Den här filen är den praktiska ändringsloggen för BrewAssistant Beta.

Varje funktionell ändring ska ange:

- vad som ändrades,
- vilka dashboard-kort som behöver ersättas/uppdateras,
- vilka övriga filer som ändrades,
- om Home Assistant behöver startas om.

`dashboard/cards/*_sv.yaml` är svenska presentationsspeglar av motsvarande canonical engelska kort.

---

## 2026-10-08 — v2026.10.0b4 — fermentation provider + Brewfather Custom Stream handoff

### Sammanfattning

Jässtrategi och fysisk jäsutrustning separeras nu explicit. BrewAssistant lagrar
per-session provider `fermentation_chamber` eller `grainfather_gf30`, exponerar
ett nytt provider-select och gate:ar chamber/GF30 så endast vald provider kan
skapa eller verkställa provider-specifik temperaturintention.

Providerbyte rensar stale pending action utan att ändra processmål, SG-stage eller
recipe schedule. GF30 återvaliderar provider även precis före confirmed write.

### Dashboard

Nytt gemensamt providerkort:

- `dashboard/cards/fermentation_provider.yaml`
- `dashboard/cards/fermentation_provider_sv.yaml`

Befintliga chamber- respektive GF30-kort är provider-conditional och använder
stabila maskin-ID:n, inte översatta labels.

### Brewfather Custom Stream

BrewAssistant exponerar nya read-only, provider-neutrala streamkällor för
temperatur, SG, processmål, target FG och semantiskt korrekt `aux_temp`.

- chamber -> `aux_temp` = chamber/fridge air;
- GF30 -> `aux_temp` = coolant/reservoar;
- GF30 intern beer-temp felmärks aldrig som Fridge Temp;
- primär temperatur måste vara färsk, max 20 minuter;
- stale valfria measurements utelämnas;
- BrewAssistant gör inga HTTP-POST:ar.

Companion `Jocke1970/brewfather` äger fortsatt HTTPS-transport, 15-minuters
rate-limit och delivery diagnostics.

### Nya entiteter

- `select.brewassistant_fermentation_provider`
- `sensor.brewassistant_fermentation_provider`
- `sensor.brewassistant_fermentation_provider_status`
- `sensor.brewassistant_brewfather_stream_status`
- `sensor.brewassistant_brewfather_stream_temperature`
- `sensor.brewassistant_brewfather_stream_gravity`
- `sensor.brewassistant_brewfather_stream_temp_target`
- `sensor.brewassistant_brewfather_stream_gravity_target`
- `sensor.brewassistant_brewfather_stream_aux_temperature`

### Säkerhetsgräns

- exakt en fermentation-provider är control-eligible;
- ingen automatisk fallback till den andra providern;
- providerbyte återanvänder inte gammal pending/confirmation;
- GF30 äger fortsatt heater/cooling-pump;
- coolant thermostat äger fortsatt frysen;
- Custom Stream är logging och kan aldrig ge control permission.

### HA-åtgärd

**Home Assistant-omstart krävs** efter HACS-uppdatering eftersom nya
integration-owned select-/sensor-entiteter tillkommer.

---

## 2026-10-03 — v2026.10.0b3 — GF30 Liquid Cooler read-only readiness

### Sammanfattning

GF30 coolant-backenden utökas med full read-only observation av den externa
Liquid Cooler-kedjan utan att BrewAssistant får någon ny fysisk styrbehörighet.

Nya valfria mappings:

- `gf30_cooler_power_entity`
- `gf30_cooler_switch_entity`

De kompletterar befintliga:

- `gf30_coolant_temp_entity`
- `gf30_freezer_air_temp_entity`
- `gf30_coolant_thermostat_entity`

Backenden observerar nu coolant-temperatur, frysluft, termostatens target och
`hvac_action`, cooler power samt cooler switch state.

### Nya sensorer

- `sensor.brewassistant_gf30_cooler_power`
- `sensor.brewassistant_gf30_cooler_switch_state`

### Readiness boundary

`monitor_ready` betyder endast att den nödvändiga coolant-telemetrin är färsk.
Det betyder **inte** att kylsystemet är verifierat säkert för aktiv kylning.

Snapshoten exponerar därför separat:

- `monitoring_ready`
- `cooling_readiness: not_validated`
- `safe_setpoint_known: false`
- `coolant_mixture_verified: false`

BrewAssistant gissar inte kompressordrift från effektvärdet och ändrar varken
cooler switch eller thermostat setpoint.

### Säkerhetsgräns

- GF30 controller äger fortsatt beer-temperature control och sin cooling pump.
- Home Assistant climate/thermostat äger Liquid Cooler/frys.
- BrewAssistant observerar endast.
- Ingen direkt cooler-switching.
- Ingen automatisk thermostat-target.
- Ingen kompressorstatus infereras från watt innan fältdata finns.

### HA-åtgärd

Home Assistant-omstart krävs efter integration update eftersom två nya
integration-owned sensorer tillkommer.

---

## 2026-10-03 — v2026.10.0b2 — GF30 profile-authority + focused supervised card

### Sammanfattning

GF30:s supervised target-flöde följer nu strikt den aktiva jäsprofilens/receptschemats
temperaturmål. BrewAssistants interna `tracking_rule` är fortsatt tillgänglig för
fermentation tracking men är uttryckligen **inte** en auktoritativ GF30-styrkälla.

Tillåten GF30-profilkälla i denna release:

- `brewfather_recipe_schedule`

Saknas en profile-backed target visas `waiting_for_profile` och ingen GF30-write kan
förberedas eller bekräftas. Vid Confirm återvalideras både targetvärdet och profilkällan.

### Dashboard

Det fokuserade GF30-kortet använder nu BrewAssistant-layouten och visar endast:

- Profilmål
- GF30 target
- avvikelse/synkstatus
- GF30 online/offline
- Apply Mode
- supervised apply-state
- Prepare / Reject / Confirm

Teknisk Grainfather-diagnostik som MQTT subscription, RSSI, firmware, OTA,
hysteresis, coolant och preflight hör fortsatt hemma i Grainfather/diagnostikytor.

### Nya/ändrade entiteter

- `sensor.brewassistant_gf30_profile_target`
- `sensor.brewassistant_gf30_target_apply_state`
- `sensor.brewassistant_gf30_controller_target`
- `sensor.brewassistant_gf30_target_delta`

Den äldre `sensor.brewassistant_gf30_recommended_target` behålls endast för
bakåtkompatibilitet/diagnostik och används inte som GF30-kortets targetyta.

### Säkerhetsgräns

- GF30 äger heater och cooling-pump.
- BrewAssistant direktstyr inte heater/cooling.
- Profile-backed target + Supervised Apply + explicit Confirm krävs.
- Ändrad profilkälla eller profile target mellan Prepare och Confirm stoppar write.
- Verifierad Grainfather MQTT-readback krävs innan åtgärden räknas som klar.

### Dashboard/cards att ersätta

- `dashboard/cards/gf30_supervised_target.yaml`
- `dashboard/cards/gf30_supervised_target_sv.yaml`

### HA-åtgärd

**Home Assistant-omstart krävs** efter uppdatering eftersom
`sensor.brewassistant_gf30_profile_target` tillkommer.

---

## 2026-10-03 — v2026.10.0b1 — GF30 supervised target adapter

### Sammanfattning

BrewAssistant kopplas nu till den fältverifierade GF30-targetytan i
`Jocke1970/grainfather_integration`. `fermentation_tracking` fortsätter äga
önskad öltemperatur, medan `grainfather_fermenter` endast adapterar den
rekommendationen till GF30.

Ny operatorväg:

- `button.brewassistant_gf30_prepare_target` skapar endast en pending action;
- befintlig `button.brewassistant_confirm_supervised_apply` krävs för faktisk write;
- executorn återvaliderar live-rekommendationen före write;
- write går endast via
  `grainfather.set_controller_target_temperature(confirm=true)`;
- Grainfather-integrationen äger command 0, MQTT och readback;
- BA betraktar åtgärden som utförd först när extern readback rapporterar
  `target_write_last_result: verified`.

GF30 får inte skriva över en pending Supervised Apply-action från annan backend.

### Nya sensorer

- `sensor.brewassistant_gf30_target_apply_state`
- `sensor.brewassistant_gf30_recommended_target`
- `sensor.brewassistant_gf30_controller_target`
- `sensor.brewassistant_gf30_target_delta`

### Säkerhets-/ägarskapsgräns

- GF30-controllern äger lokal heater och cooling-pump.
- Direkt heater/cooling-styrning från BA är fortsatt DISABLED.
- GF30-target är deklarerad CONFIRM-capability i modulregistret.
- Coolant/freezer-backenden är oförändrad och fortsatt read-only.
- Ingen automatiskt verkställd temperaturändring införs.

### HA-åtgärd

**Home Assistant-omstart krävs** efter uppdatering eftersom nya integration-owned
sensorer/button och supervised executor registreras.

---

## 2026-09-24 — v0.2.0-beta.15 — GF30 read-only thermal foundation + doc-sync

### Sammanfattning

Den här prerelease-kandidaten gör `grainfather_fermenter/` användbar redan före full GF30-Wi-Fi-/controller-validering, utan att ge BrewAssistant fysisk styrbehörighet. RAPT Pill kan paras med manuella referenstemperaturer i en persistent preflight-runtime. BrewAssistant exponerar read-only diagnostik för temperaturdelta, freshness, passiv kyl-/värmehastighet, dual-sensor safe-point och framtida coolant/freezer-monitorering.

När Grainfather-controllerdata finns används upstream `last_heard` före vanlig HA-`last_updated` för intern GF30-freshness när den går att tolka. Köldmedium, frysluft och coolant-`generic_thermostat` kan mappas genom tre valfria, tomma config/options-fält. Tomma mappings är giltiga; inga entity-ID gissas.

Två nya manuella tjänster finns:

- `brewassistant.gf30_record_manual_temperature`
- `brewassistant.gf30_clear_preflight`

Den persistenta preflight-historiken lagrar upp till 200 observationer. Fasetiketter som `baseline`, `cooling`, `recovery` och `cold_crash` kan användas för passiv learning. Learning ger statistik och °C/h från redan observerad data men korrigerar inga givare och skickar inga kommandon.

### Säkerhets-/ägarskapsgräns

- GF30:s lokala controller äger fortsatt sin pump och lokala öltemperaturreglering.
- En framtida Home Assistant `generic_thermostat` är ensam avsedd ägare av frysen.
- BrewAssistant ändrar inte GF30 target, pump, frys, coolant-setpoint eller climate-läge i denna release.
- `gf30_safe_point` är diagnostik, inte tillstånd att aktivera hårdvara.
- Safe coolant-setpoint och faktisk fail-OFF är uttryckligen okända tills verkligt medium och fysisk installation har testats.

### Dashboard/cards att ersätta

- Inga nya dashboardkort krävs för GF30-funktionen. Första mätprovet kan köras via Home Assistant Developer Tools / Actions.

### Nya/ändrade entiteter och konfiguration

Bland de nya read-only sensorerna finns GF30 backend/preflight-status, controller-tempkandidat, Pill/manual-delta, sample counts, learning confidence/rates, dual-sensor-status/safe-point samt coolant/freezer-diagnostik.

Nya valfria entity-mappings:

- `gf30_coolant_temp_entity`
- `gf30_freezer_air_temp_entity`
- `gf30_coolant_thermostat_entity`

### Övriga ändrade filer

- `custom_components/brewassistant/grainfather_fermenter/*`
- `custom_components/brewassistant/__init__.py`
- `custom_components/brewassistant/sensor.py`
- `custom_components/brewassistant/coordinator.py`
- `custom_components/brewassistant/config_flow.py`
- `custom_components/brewassistant/const.py`
- `custom_components/brewassistant/services.yaml`
- `tests/test_grainfather_fermenter_backend.py`
- GF30/backend/roadmap/release-dokumentation

### HA-åtgärd

**Home Assistant-omstart krävs** efter installation eftersom nya integration-owned sensorer, tjänster och options-fält tillkommer. Ingen fysisk GF30-/frysstyrning ska aktiveras på grund av denna release.

---

## 2026-08-29 — PR #152 — Slå ihop BrewZilla Advice + Learning till Bryggråd

### Sammanfattning

De två BrewZilla-korten `brewzilla_advice_auto*` och `brewzilla_learning*` visade i praktiken samma rådgivningsdomän i två detaljnivåer. Det separata Advice-kortet pensioneras nu och `brewzilla_learning*` blir ensam operatörsyta för **Brewing Advice / Bryggråd**. Kortet innehåller redan aktuell rekommendation, temperatur/trend, risk och confidence, föreslagen värme, `APPLY/DENY` / `VERKSTÄLL/AVVISA` samt expanderbar learning-/diagnostikdata.

Safety/RCL förblir separat eftersom det svarar på en annan fråga: om data och fysisk styrning är säker/frisk, inte vad BrewAssistant rekommenderar.

### Dashboard/cards att ersätta

- Ta bort `dashboard/cards/brewzilla_advice_auto.yaml` / `_sv.yaml` från lokala dashboards.
- Behåll/reloada `dashboard/cards/brewzilla_learning.yaml` / `_sv.yaml` som enda Bryggråd-kort.

### Övriga ändrade filer

- `tests/test_brewzilla_advice_learning_consolidation.py`
- `dashboard/README.md`
- `docs/dashboard-baselines.md`
- `CHANGELOG.md`

### HA-åtgärd

Ingen backend eller entity ändras. **Ingen Home Assistant-omstart krävs**; dashboarden behöver bara uppdateras/reloadas så det gamla Advice-kortet tas bort.

---

## 2026-08-29 — PR #151 — BrewTracker/Brewfather UI efter processfas

### Sammanfattning

BrewTracker och Brewfather visas nu efter vilken del av batchens livscykel som är relevant i stället för som två stora parallella kort med överlappande runtime-data. En ny integration-owned `sensor.brewassistant_brewfather_batch_phase` exponerar samma normaliserade `planning` / `brewing` / `fermenting` / `inactive`-fas som Brewfather ownership-backenden redan använder.

`brewtracker_runtime*` är bryggdagskortet under Planning och Brewing. Planning visas som redo utan hot-side ownership, och Brewing innan Play visas explicit som pre-start/väntar på BrewTracker Play. Detta bevarar #147-regeln att batchfasen Brewing i sig inte är startbevis.

`brewfather_feed*` behåller filnamnet för kompatibilitet men är nu ett kompakt Brewfather batch-/receptkort som endast visas under Fermenting. Det duplicerar inte Jäsningscockpitens temperatur/Pill/klimatstyrning; teknisk feed-hälsa hör fortsatt hemma i Source Health.

### Dashboard/cards att ersätta

- `dashboard/cards/brewtracker_runtime.yaml`
- `dashboard/cards/brewtracker_runtime_sv.yaml`
- `dashboard/cards/brewfather_feed.yaml`
- `dashboard/cards/brewfather_feed_sv.yaml`

### Ny entitet

- `sensor.brewassistant_brewfather_batch_phase`

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewday_runtime_sensor.py`
- `tests/test_brewfather_hot_side_ownership.py`
- `tests/test_brewfather_process_phase_ui.py`
- `dashboard/README.md`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom en ny integration-owned sensor skapas. Ersätt/reloada därefter de fyra BrewTracker/Brewfather-korten ovan.

---

## 2026-08-29 — PR #150 — Brewday operator-ABORT + doc-sync

### Sammanfattning

Brewday-cockpitens tidigare `AVBRYT` bredvid Supervised Apply-kvittensen var endast ett avslag av väntande plan, medan BrewZilla-cockpitens `AVBRYT` körde riktig fysisk ABORT. De två betydelserna separeras nu tydligt: väntande plan heter `REJECT ACTION` / `AVVISA ÅTGÄRD`, medan en separat röd `ABORT BREWDAY` / `ABORT BRYGGDAG` kör BrewZillas auktoritativa safe-down, avvisar väntande positiv intention, återställer Manual Brewday och latchar BrewAssistants hot-side ownership i `aborted`.

Operator-ABORT-latchen sparas i Home Assistant storage och laddas före coordinator/orchestration-beslut. En HA-omstart får därför inte tyst återaktivera en aborterad Brewday. Brewfather ownership-gaten respekterar latchen även om samma Brew Tracker fortfarande är running. `REARM CONTROL` / `ÅTERAKTIVERA STYRNING` släpper endast Brewday-latchen; BrewZillas separata hårdvaru-ABORT-lockout förblir auktoritativ.

Doc-syncen uppdaterar samtidigt Brewday/BrewZilla-arkitektur, Flight Recorder-regressioner, dashboardbaseline och roadmap med fysisk #147–#149-validering samt det fasta sensorägarskapet: extern processgivare ägs av Brewday från Heat strike till Pre-boil, släpps vid Boil och används därefter av CFC som outlet/wort-out under Chill/Transfer.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_brewday.yaml`
- `dashboard/cards/brewassistant_brewday_sv.yaml`

### Nya/ändrade entiteter

- `sensor.brewassistant_brewday_operator_control_state`
- `button.brewassistant_abort_brewday`
- `button.brewassistant_rearm_brewday_control`

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewday_operator_abort.py`
- `custom_components/brewassistant/brewday/brewfather_ownership.py`
- `custom_components/brewassistant/brewday/brewday_runtime.py`
- `custom_components/brewassistant/brewday/brewday_runtime_sensor.py`
- `custom_components/brewassistant/button.py`
- `custom_components/brewassistant/coordinator.py`
- `tests/test_brewday_operator_abort.py`
- `docs/brewday-brewzilla.md`
- `docs/brewday-audit.md`
- `docs/dashboard-baselines.md`
- `docs/roadmap.md`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom nya integration-owned sensor/button-entiteter och den persistenta ABORT-latchen tillkommer. Ersätt/reloada även Brewday-dashboardkortet.

---

## 2026-08-29 — PR #149 — RCL readback-grace + samma Flight Recorder-logg vid BF Play

### Sammanfattning

Fysisk validering av Supervised Apply visade att en korrekt bekräftad BrewZilla-plan kunde följas av ett gammalt RAPT Cloud Link-readback, exempelvis heat utilization `100 → 0`, och därmed skapa en ny kvittens för samma redan godkända intention. En tidsbegränsad 240 s confirmed-plan readback-grace minns nu endast target/heat/pump-number-ökningar som både uttryckligen bekräftades och faktiskt skickades. Samma runtime/source/step/target/ownership får under grace-fönstret ignorera en stale kopia av just dessa konfigurationsvärden utan ny write och utan ny pending-plan. Heater/pump ON omfattas medvetet inte; verklig åter-energisering kräver fortfarande ny kvittens. ABORT bryter gracen omedelbart.

Samma test visade att Flight Recorder kunde roteras när Brewfather gick från `Brewing` pre-start till faktisk Play. Den äldre autostart-heuristiken såg senaste `idle`/no-source-raden som en avslutad föregående bryggdag, trots att #147:s pre-start är en del av samma session. Legacy-heuristiken accepterar nu `idle`/`inactive` utan owner som terminal endast när #146:s deterministiska session-boundary faktiskt är armad. `completed`/`finished` förblir explicita terminala lägen.

### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/__init__.py`
- `custom_components/brewassistant/brewday/brewday_audit_session_continuity.py`
- `custom_components/brewassistant/brewzilla/__init__.py`
- `custom_components/brewassistant/brewzilla/brewzilla_supervised_readback_grace.py`
- `tests/test_brewday_audit_session_continuity.py`
- `tests/test_brewzilla_supervised_readback_grace.py`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom båda runtime-guards installeras under package-initiering.

---

## 2026-08-29 — PR #148 — Tydlig device-target i Flight Recorder + pulserande CONFIRM

### Sammanfattning

Fysisk Brewfather/Supervised Apply-validering visade att Flight Recorder-fältet `brewzilla_device_target` var felmärkt: det hämtades från BrewAssistants normaliserade/effective target och kunde därför gå till exempelvis 71.8 °C när Brewfather-runtime blev aktiv, trots att BrewZillas råa RAPT-target fortfarande låg kvar på 45 °C och den positiva planen väntade på kvittens. Flight Recorder skiljer nu explicit på `brewzilla_effective_target` och `brewzilla_device_target`, där device-fältet kommer från `sensor.brewassistant_brewzilla_device_target_temperature`.

Den generella Brewday-cockpitens CONFIRM/BEKRÄFTA-knapp blir samtidigt tydligt pending-styrd. När `sensor.brewassistant_brewzilla_pending_action` innehåller en väntande plan ändras texten till `CONFIRM ACTION` / `BEKRÄFTA ÅTGÄRD`, knappen får starkare visuell vikt och en långsam 1.4 s puls. `CANCEL` / `AVBRYT` förblir statisk. `prefers-reduced-motion` behåller den starka statiska pending-markeringen men stänger av animationen.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_brewday.yaml`
- `dashboard/cards/brewassistant_brewday_sv.yaml`

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewday_audit.py`
- `tests/test_brewday_flight_recorder.py`
- `tests/test_dashboard_language_parity.py`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update för den korrigerade Flight Recorder-backenden. Ersätt/reloada även Brewday-dashboardkortet för pending-pulsen.

---

## 2026-08-29 — PR #147 — Brewfather tar över först när Brew Tracker faktiskt startar

### Sammanfattning

Rättar skillnaden mellan Brewfather-batchens fas `Brewing` och en faktiskt startad Brew Tracker. En batch kan vara `Brewing` och samtidigt exponera `active: true` medan trackern fortfarande står pausad på `Start / Starta mäsktimer`, steg 0, 0 % progress och full återstående stage-tid. Det läget är nu visible/ready men äger inte hot-side.

Brewfather får hot-side ownership först när det finns positivt startbevis, exempelvis running/active-status, avancerat steg/progress eller nedräknad stage-tid. Starten latchas per tracker/batch-id så en legitim paus efter start behåller ownership. Samma fysiska payload avslöjade även ett equal-time-anchor-fel där pausat `Start` och följande ramp hade samma tidsankare; medan trackern är pausad respekteras nu Brewfathers explicita live-step i stället för att timerheuristiken hoppar fram till rampen.

### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewfather_ownership.py`
- `tests/test_brewfather_hot_side_ownership.py`
- `CHANGELOG.md` backfillades i PR #148 eftersom #147 mergades utan egen changelog-post.

### HA-åtgärd

**Omstart krävs** efter integration update eftersom Brewfather ownership-policy och runtime step-resolution ändras.

---

## 2026-08-29 — PR #146 — Deterministisk flight-recorder-rotation vid ny bryggdag

### Sammanfattning

Rättar racet som kunde göra att PR #143 missade att rensa föregående bryggdags logg. Ett separat session-boundary-guard armar nu en bryggdagsgräns när Brewday verkligen når terminalt läge utan aktiv Manual/Brewfather-owner. Gränsen sparas utanför den rullande eventloggen, så ett senare orchestration-/transition-event kan inte skriva över kunskapen om att föregående bryggdag är avslutad.

När nästa Manual-session går `idle/completed → prepared`, eller en ny Brewfather-session går in i Planning/Brewing, roteras flight recordern innan den nya sessionen får fortsätta använda loggen. Guardens `started_at`-kontroll upptäcker om den äldre autostart-logiken redan hunnit rotera och förhindrar dubbel rotation. Manual ↔ Brewfather-handoff inom samma pågående bryggdag armar ingen terminal boundary och behåller därför samma logg.

### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/__init__.py`
- `custom_components/brewassistant/brewday/brewday_audit_session_boundary.py`
- `tests/test_brewday_flight_recorder.py`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom Brewday audit-autostartens setup-väg patchas vid integrationens initiering.

---

## 2026-08-29 — PR #145 — Improve BrewZilla heater and pump visualization

### Sammanfattning

BrewZilla-kortets heat- och pumpsektioner visar nu live utilization tydligare, med separata ON/OFF/PÅ/AV-lägen, utilization-bars samt diskret animation när heater respektive pump är aktiva. Svenska och engelska kort hålls synkade och animationerna respekterar reduced-motion.

### Dashboard/cards att ersätta

- `dashboard/cards/brewzilla.yaml`
- `dashboard/cards/brewzilla_sv.yaml`

### Övriga ändrade filer

- Inga backendfiler.
- `CHANGELOG.md` backfillades i PR #146 eftersom #145 mergades parallellt utan changelog-post.

### HA-åtgärd

Ingen backend-omstart krävs enbart för #145. Uppdatera/reloada BrewZilla-dashboardkortet.

---

## 2026-08-29 — PR #144 — AVBRYT suppressar oförändrad Supervised Apply-plan

### Sammanfattning

`AVBRYT` betyder nu att den exakta positiva BrewZilla-planen avvisas, inte bara att det aktuella pending-objektet tas bort. Samma plan skapas därför inte om av nästa coordinator-tick och heater/pump förblir säkra medan runtime får fortsätta.

Avvisningen är bunden till planens runtime- och intention-context. När source/owner, runtime-state, stage/step, target eller själva positiva AUTO-planen ändras betraktas det som ny intention och Supervised Apply får skapa en ny kvittens. Flight recorder visar under tiden `cancelled_plan_suppressed` i stället för ett nytt `pending_confirmation`.
### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `custom_components/brewassistant/supervised_apply.py`
- `custom_components/brewassistant/brewzilla/brewzilla_supervised_runtime_guard.py`
- `tests/test_brewzilla_supervised_runtime_actions.py`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom Supervised Apply-backendens cancellation-state ändras.

---

## 2026-08-29 — PR #143 — Ny flight-recorder-logg per bryggdag

### Sammanfattning

Flight recordern roteras nu automatiskt när en ny bryggdag börjar. Om föregående logg fortfarande är aktiv men senaste runtime-läget visar att bryggdagen är avslutad (`completed`/`finished`, eller `idle`/`inactive` utan aktiv runtime-källa) rensas gamla events innan nästa Manual/Brewfather-session börjar loggas.

Manual ↔ Brewfather-handoff inom samma bryggdag räknas inte som en ny session och behåller därför samma sammanhängande flight-recorder-logg.

### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewday_audit_autostart.py`
- `tests/test_brewday_flight_recorder.py`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom flight-recorder-autostarten ändras.

---

## 2026-08-29 — PR #142 — Explicit och hårdlåst Supervised Apply

### Sammanfattning

Manual Brewday visar nu tydligt när en positiv AUTO-plan mot BrewZilla väntar på operatörens kvittens. `Heat strike` har en separat startdialog som förklarar att runtimen går vidare direkt, medan positiva AUTO-åtgärder kräver efterföljande `BEKRÄFTA`. Den väntande planen visas i Manual Brewday-cockpit med sammanfattning samt `BEKRÄFTA`/`AVBRYT`.

BrewZilla-planer körs nu via en registrerad Supervised Apply-exekutor som endast anropas från den explicita bekräftelseknappen. Vid kvittens byggs live-planen om och måste fortfarande matcha exakt plan-ID, runtime och säkerhetsläge. Vanliga coordinator-ticks kan inte konsumera kvittensen eller öppna den positiva exekveringsvägen. Flight recordern loggar dessutom `supervised_confirmed`, `supervised_executed`, `supervised_not_executed` och `supervised_cancelled` så nästa testlogg visar exakt vad operatören gjorde.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_manual_brewday.yaml`
- `dashboard/cards/brewassistant_manual_brewday_sv.yaml`

### Övriga ändrade filer

- `custom_components/brewassistant/supervised_apply.py`
- `custom_components/brewassistant/brewzilla/brewzilla_supervised_runtime_guard.py`
- `tests/test_brewzilla_supervised_runtime_actions.py`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom Supervised Apply-backendens exekveringsväg ändras. Ersätt/reloada även Manual Brewday-kortet.

---

## 2026-08-29 — PR #141 — Supervised BrewZilla runtime actions

### Sammanfattning

Manual Brewday och Brewfather fortsätter styra runtime/timers som tidigare, men positiva AUTO-åtgärder mot BrewZilla går nu genom en samlad Supervised Apply-plan innan fysisk verkställning. Target-up, utilization-up, heater ON och pump ON kräver kvittens enligt befintlig sektionspolicy. Safe-down och operatörsägda MAN-setpoints får fortfarande verkställas direkt. Vid BEKRÄFTA räknas den aktuella runtime-planen om; en gammal/stale plan körs inte om BF/Manual hunnit avancera.

Manual Brew `prepared` är samtidigt en explicit safe-down boundary: `Förbered` får aldrig energisätta BrewZilla. Först `Heat strike` flyttar Manual runtime till ett aktivt steg som får skapa positiv styrintention.

### Dashboard/cards att ersätta

- Inga.

Den befintliga `BEKRÄFTA`/`AVBRYT`-kontrollen i Brewday-cockpit används för den nya samlade orkesterplanen.

### Övriga ändrade filer

- `custom_components/brewassistant/brewzilla/__init__.py`
- `custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py`
- `custom_components/brewassistant/brewzilla/brewzilla_no_positive_gate.py`
- `custom_components/brewassistant/brewzilla/brewzilla_supervised_runtime_guard.py`
- `tests/test_brewzilla_supervised_runtime_actions.py`
- `CHANGELOG.md`

### HA-åtgärd

**Omstart krävs** efter integration update eftersom BrewZilla backendens exekveringskedja ändras.

---

## 2026-08-29 — PR #140 — Correct BLE card targets and restore temperature gauge

### Sammanfattning

Korrigerar #139: det var BLE-indikatorn, inte den generella dual-temperature-gaugen, som skulle döljas när extern processgivare saknas. Temperatur-gaugen återställs så BrewZillas interna temperatur fortfarande visas utan BLE/extern givare. Både BLE-indikator och BLE-status följer nu den BA-owned externa temperaturtillgängligheten.

### Dashboard/cards att ersätta

- `dashboard/cards/brewzilla_ble_indicator.yaml`
- `dashboard/cards/brewzilla_ble_indicator_sv.yaml`
- `dashboard/cards/brewzilla_dual_temperature_gauge.yaml`
- `dashboard/cards/brewzilla_dual_temperature_gauge_sv.yaml`

### Övriga ändrade filer

- `tests/test_brewzilla_external_temperature_visibility.py`
- `CHANGELOG.md`

### HA-åtgärd

Ingen ny backend-entitet tillkommer i #140. Efter att #139 redan installerats räcker integration/dashboard update; full HA-omstart är inte nödvändig enbart för denna korrigering.

---
## 2026-08-29 — PR #139 — External temperature card visibility

### Sammanfattning

BLE-/extern temperaturdiagnostik visas bara när BrewZilla faktiskt har en användbar extern processgivare. En ny BA-owned connectivity-sensor skiljer "extern givare tillgänglig" från vilken temperaturkälla operatören för tillfället valt.

**Korrigering:** PR #139 råkade gate:a `brewzilla_dual_temperature_gauge*` i stället för `brewzilla_ble_indicator*`. Detta rättas i PR #140.

### Dashboard/cards att ersätta

- `dashboard/cards/brewzilla_ble_status.yaml`
- `dashboard/cards/brewzilla_ble_status_sv.yaml`
- `dashboard/cards/brewzilla_dual_temperature_gauge.yaml`
- `dashboard/cards/brewzilla_dual_temperature_gauge_sv.yaml`

### Övriga ändrade filer

- `custom_components/brewassistant/brewzilla/brewzilla_temperature.py`
- `custom_components/brewassistant/binary_sensor.py`
- `tests/test_brewzilla_external_temperature_visibility.py`
- `.github/pull_request_template.md`
- `CHANGELOG.md`

### Ny entitet

- `binary_sensor.brewassistant_brewzilla_external_temperature_available`

### HA-åtgärd

**Omstart krävs** efter uppdatering eftersom en ny integration-owned binary sensor skapas.

---

## 2026-08-29 — PR #138 — Fix Brewfather Planning ownership and handoff

### Sammanfattning

Brewfather/BrewTracker `Planning` betyder inkopplad/redo men äger inte hot-side. Först `Brewing` får ta över Brewday runtime och pausa Manual Brew. När BF lämnar Brewing ligger Manual kvar pausad och safe-down begärs direkt. BF-korten får samtidigt synas redan i Planning med tydlig ready/not-authoritative presentation.

### Dashboard/cards att ersätta

- `dashboard/cards/brewfather_feed.yaml`
- `dashboard/cards/brewfather_feed_sv.yaml`
- `dashboard/cards/brewtracker_runtime.yaml`
- `dashboard/cards/brewtracker_runtime_sv.yaml`

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/__init__.py`
- `custom_components/brewassistant/brewday/brewfather_ownership.py`
- `custom_components/brewassistant/brewday/manual_brewday_store.py`
- `tests/test_brewfather_hot_side_ownership.py`
- `tests/test_manual_brew_owned_setpoints.py`

### HA-åtgärd

**Omstart krävs** efter integration update.

---

## 2026-08-29 — PR #137 — Auto-start Brewday flight recorder

### Sammanfattning

Brewday flight recorder startar automatiskt för Manual Brewday och Brewfather och loggar högsignalövergångar för runtime, ownership, setpoints, BZ-readback samt heater/pump-state.

### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewday_audit_autostart.py`
- `tests/test_brewday_flight_recorder.py`

### HA-åtgärd

**Omstart krävs** efter integration update.

---

## 2026-08-28 — PR #136 — Force Manual Brew safe-down while paused

### Sammanfattning

Pausad Manual Brew överordnar MAN-ownership för fysiska outputs: heater och pump drivs OFF, utilization till 0 och target reassert stoppas. Operatörens sparade MAN-setpoints finns kvar till explicit återupptagning.

### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/manual_brewday_store.py`
- `custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py`
- `tests/test_manual_brew_owned_setpoints.py`

### HA-åtgärd

**Omstart krävs** efter integration update.

---

## 2026-08-28 — PR #135 — State-aware Manual Brewday controls

### Sammanfattning

Manual Brewday-knapparna speglar state machine. `Start` ersattes av `Heat strike`; valbara actions visas tydligt, aktuellt steg markeras separat och otillåtna actions är grå/inaktiva. Pause växlar till Resume/Continue när relevant.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_manual_brewday.yaml`
- `dashboard/cards/brewassistant_manual_brewday_sv.yaml`

### Övriga ändrade filer

- Inga.

### HA-åtgärd
Ingen backend-omstart krävs enbart för kortändringen; uppdatera/reload dashboard-korten.

---

## 2026-08-28 — PR #134 — Manual Brewday prepare action in Brewday cockpit

### Sammanfattning

Den generella Brewday-cockpitten fick en direkt `Prepare Manual Brewday`-action när runtime är idle och BF inte blockerar Manual.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_brewday.yaml`
- `dashboard/cards/brewassistant_brewday_sv.yaml`

### Övriga ändrade filer

- Inga.

### HA-åtgärd

Ingen backend-omstart krävs enbart för kortändringen; uppdatera/reload dashboard-korten.

---

## 2026-08-28 — PR #133 — Expose Manual Brewday session status sensors

### Sammanfattning

Manual Brewday-sessionens status och stage exponeras som riktiga HA-sensorer så Hub/diagnostik kan läsa Manual-state även när en annan normaliserad runtime-källa vinner.

### Dashboard/cards att ersätta

- Inga filer ändrades i PR:n, men tidigare Hub-kort kan nu använda sensorerna korrekt.

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewday_runtime_sensor.py`

### HA-åtgärd

**Omstart krävs** för att skapa/uppdatera integration-owned sensorer.

---

## 2026-08-28 — PR #132 — Hide Manual Brewday cockpit while inactive

### Sammanfattning

Full Manual Brewday cockpit döljs när Manual är idle. Hubben visar i stället en kompakt Prepare-launcher när BF inte blockerar Manual.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_hub.yaml`
- `dashboard/cards/brewassistant_hub_sv.yaml`
- `dashboard/cards/brewassistant_manual_brewday.yaml`
- `dashboard/cards/brewassistant_manual_brewday_sv.yaml`

### Övriga ändrade filer

- Inga.

### HA-åtgärd

Ingen backend-omstart krävs enbart för kortändringen; uppdatera/reload dashboard-korten.

---

## 2026-08-28 — PR #131 — Manual Brew operator-owned setpoints

### Sammanfattning

Manual target/heat/pump separerades från RAPT/BrewZilla readback genom BA-owned setpoints. Target stegar 1 °C; heat/pump 5 %. Orkestern transporterar och reassertar operatorns setpoints tills BZ-readback matchar.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_manual_brewday.yaml`
- `dashboard/cards/brewassistant_manual_brewday_sv.yaml`

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/manual_brewday_adapter.py`
- `custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py`
- `custom_components/brewassistant/number.py`
- `tests/test_manual_brew_owned_setpoints.py`

### HA-åtgärd

**Omstart krävs** eftersom nya/ändrade integration-owned number entities används.

---

## 2026-08-21 — PR #130 — Document Manual Brew Control v2 ownership

### Sammanfattning

Dokumentationen synkades med Manual Brew Control v2, BF/Manual exclusion, ownership per kanal, säkerhetsordning och fysisk valideringsplan.

### Dashboard/cards att ersätta

- Inga.

### Övriga ändrade filer

- `README.md`
- `docs/backends/brewzilla-backend.md`
- `docs/brewday-brewzilla.md`
- `docs/brewzilla-control-profile.md`

### HA-åtgärd

Ingen.

---

## 2026-08-21 — PR #129 — Manual Brew Control v2

### Sammanfattning

Manual Brew fick verkligt operator-ownership för target, heater/heat utilization och pump/pump utilization, med Safety/ABORT överordnat. Brewfather och Manual gjordes ömsesidigt exklusiva som aktiva runtime-källor.

### Dashboard/cards att ersätta

- `dashboard/cards/brewassistant_manual_brewday.yaml`
- `dashboard/cards/brewassistant_manual_brewday_sv.yaml`

### Övriga ändrade filer

- `custom_components/brewassistant/brewday/brewday_runtime.py`
- `custom_components/brewassistant/brewday/manual_brewday_adapter.py`
- `custom_components/brewassistant/brewday/manual_brewday_store.py`
- `custom_components/brewassistant/brewzilla/__init__.py`
- `custom_components/brewassistant/brewzilla/brewzilla_manual_brew_control.py`

### HA-åtgärd

**Omstart krävs** efter integration update.