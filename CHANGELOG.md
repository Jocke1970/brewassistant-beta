# BrewAssistant Changelog

Den här filen är den praktiska ändringsloggen för BrewAssistant Beta.

Varje funktionell ändring ska ange:

- vad som ändrades,
- vilka dashboard-kort som behöver ersättas/uppdateras,
- vilka övriga filer som ändrades,
- om Home Assistant behöver startas om.

`dashboard/cards/*_sv.yaml` är svenska presentationsspeglar av motsvarande canonical engelska kort.

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

Den generella Brewday-cockpitten fick en direkt `Prepare Manual Brewday`-action när runtime är idle och BF inte äger bryggdagen.

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
