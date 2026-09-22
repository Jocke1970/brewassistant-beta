# BrewAssistant – roadmap och acceptansgrindar

**Uppdaterad 2026-09-22.** [Aktuell status och verifierade HA-fynd](doc-sync-2026-09-22_sv.md), [historisk status 20/9](project-status-2026-09-20_sv.md), [publicerad beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14).

> [!CAUTION]
> Publicerad ≠ installerad ≠ automatiskt testad ≠ fysiskt accepterad. Beta.14 är publicerad och användaren har installerat den; i HA har read-only-attribut kontrollerats och ABORT-latch återställts separat. Fysiskt vattenprov, fysisk OFF-verifiering och full HA/RCL-end-to-end är **inte godkända**. Varken obevakad drift eller maltprov följer av gröna CI-kontroller.

## Branch- och releaseläge

| Del | Verifierat läge | Nästa grind |
| --- | --- | --- |
| Publicerad `v0.2.0-beta.14` | Tagg låst vid `1a956c04044df870e005392b6bfe946097b9d440`, manifest `0.2.0-beta.14`, CI Python 3.11–3.13/HACS/Hassfest och isolerad HA/RCL-smoke för releasekandidat. | Kontrollerat faktiskt vattenprov, inga oväntade BA-skrivningar och fysisk ABORT-verifiering. |
| `dev` | [PR #223](https://github.com/Jocke1970/brewassistant-beta/pull/223) mergade `beta` → `dev` 22/9, merge-commit `2d8f2c0fdb1d609e39ca71d24c0f581c653c4c7e`. Beta.14-kod finns nu i dev, HLT SIM-1 och tidigare sep-20-docs finns kvar. | För över korrigerad dokumentation till `beta` via separat granskad PR; ny kod måste utvecklas och testas i dev. |
| `beta` | Publicerad beta.14-kod. Efter release finns endast separat borttagning av engångsworkflow före doc-sync. | Dokumentationssynk utan ny tagg eller ändring av beta.14-releasen; CI för faktiskt nytt branch-SHA. |
| `main` | Föregående stabil branch, ingen beta.14-promotion. | Separat beslut efter dokumenterad fältacceptans. |
| HLT SIM-1 | Endast läsande simulator; 19/9 och 20/9-fältutdrag bevarade. | Fastställ källoberoende `Heat Strike`/ramp-startberedskap och omtesta virtuellt; ingen fysisk koppling. |

## Prioritet 0 – BA/BrewZilla säkerhet och vattenacceptans

**Levererat men inte fysiskt accepterat:** BA:s observationsswitch PÅ blockerar ordinarie BA-skrivningar, inte enhetsutgångar/direkt-RCL; AV validerar behörig källa och sex färska BrewZilla-readbacks. ABORT är separat och försöker STOP/OFF/0 även under read-only men HA-ACK bevisar inte fysisk OFF. RAPT-profil, BrewTracker och Manual är olika källor/ägare; ingen tyst fallback eller dubbelreglering. BF-fermentering är oberoende. [Detaljerat uppdaterat testkontrakt](brewzilla-observe-only-test_sv.md).

**Nya riktiga HA-fynd 20–22/9:** observationsswitchens svenska auto-ID matchade inte kanoniskt YAML-ID, vilket löstes manuellt i HA. Orchestration-attribut verifierade read-only aktivt samtidigt som RCL rapporterade `Disconnected`; enhetens fysiska status kunde inte styrkas. ABORT-latch återställdes separat 22/9 (`operator_control_state: armed`), men källa var fortsatt `None`/runtime `idle`. Återställning av ABORT ger inte automatiskt BA kontroll. Ingen vattenacceptans gjord.

**Provplan:**

1. Kontrollera säker vattennivå, faktiska utgångar, fysisk avstängning, rätt HA-installation/releasetagg och RCL `v0.5.0-beta.1`. Ha backup och operatör på plats.
2. Slå observe-only PÅ, verifiera `observe_only_effective: true`, `hot_side_actuator_writes_allowed: false`; försäkra att BA inte återställer operatörens manuella target, värme eller pump. `Disconnected`/stale betyder inget styrprov.
3. Använd separat Manual/observationskort först med bekräftat profil-STOP och giltig Manual-källa. Direkta RCL-knappar går utanför BA-spärren och Lovelace-villkoren är ingen global säkerhetsgräns.
4. Testa ABORT under uppsikt: verkligt profil-STOP, värmare, pump, huvudström och effekt måste verifieras fysiskt. Återställ separat med `button.brewassistant_rearm_brewday_control` först efter kontroll.
5. Om BA:s automatiska styrning testas: behörig källa, frånvaro av ABORT, sex färska readbacks och explicit switch-AV; kontrollera ingen gammal planreplay eller oväntad aktivering. Testa säkra omstarter/reload, RCL-bortfall och CFC-handoff.
6. Arkivera ny daterad testlogg och uppdatera [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220). Inget PASS av enbart simulator, UI-ikon, ack eller kodtester.

**Nästa kodfix:** gör stabilt entity-ID och migration för observe-only-switchen, med integration-/registry-test som motsvarar verklig HA-start. Ska gå genom `dev` och bli ny tagg/version efter test, inte patchas in i beta.14-taggen.

## Prioritet 1 – branchdisciplin, CI och docs

- Normal releaseväg: `dev → beta → main` med granskad PR och **Create a merge commit**, test på exakt resulterande SHA, separat tagg och prerelease för nästa kodversion. Publicerade taggar flyttas aldrig. En branchmerge uppdaterar inte HA.
- Efter #223 återstår en separat `dev → beta`-PR för doc-sync. Kontrollera att diffen inte medför oavsiktliga ändringar av integrationskod/manifest och att dev:s HLT-/CI-ändringar överförs med rätt innehåll. Ingen `main`-promotion eller ny prerelease enbart för dokumentation.
- CI, HACS, Hassfest: automatiska dev-triggers exkluderade 20/9; releasebranch, beta, main och manuella körningar gäller. Bekräfta faktisk workflow-körning och SHA – gamla gröna kontroller är inte nya testbevis. Säkerhetskritiska flöden måste ha separat HA-integrations-/regressionstest.
- [Installationsguide](INSTALLATION.md) ska peka på exakt beta.14-tagg, inte `main`. [CHANGELOG](../CHANGELOG.md) dokumenterar UI-migrering och HA-omstart. Äldre daterade fältrapporter och originalreleaseanteckningar skrivs inte om retroaktivt.

## Prioritet 2 – HLT SIM-1, energi och Brewday-kontrakt

- Fältutdrag 19/9: 94 JSONL-poster, mätarverifiering, ålder för oförändrade setpoints och `Ramp to 72°C`-veto. [Rapport](hlt-sim1-field-validation-2026-09-19.md).
- Fältutdrag 20/9: 44 giltiga JSONL-poster, fem virtuella HLT-ON-prover under RAPT `Heat Strike`, tre hypotetiska effektkonflikter cirka 3,7 kW mot 2,5 kW scenario. `physical_writes=false` och BZ-cap `null` ger inget bevis för andras fysiska utgångar. [Rapport](hlt-sim1-field-validation-2026-09-20.md).
- **Öppen logikavvikelse:** dev:s HLT-parser accepterar `heat strike` som stage men inte exakt `step=Heat Strike` som ramp; explicit positiv källoberoende HLT-beredskap saknas. Definiera avsedd förvärmningsintention, start- och stopptid för RAPT, BrewTracker och Manual. Okänt → fail-closed. Lägg tester för Heat Strike/Water, ramp, Mash In/Out, missmatchad eller stale temperatur, BZ återtag och fysisk mottagare. Rätta kod först när semantiken är beslutad; gör om helt virtuellt read-only-prov.
- HLT SIM-1 är 30 s läskonsument; den begränsar inte BZ. Virtual energy recipient `none`/`hlt` kan ha en coordinator-cykels fördröjning; verifiera faktisk sensor, `_2`-suffix och kortets översättningar `Ingen`/`HLT (virtuell)`. Fysisk mottagare okänd utan verifierade mätare.
- Eventuell framtida fysisk HLT kräver självständig snabb fail-OFF, fysisk OFF-verifikation, rätt eldimensionering och torrkokningsskydd. Simulerad budget är inget elsäkerhetsskydd.

## Prioritet 3 – behåll övriga parallella moduler

- **Fermentation:** SG-styrning/Brewfather-jässcheman separat, Climate Supervisor kräver fullcykeltest.
- **Cooling/CFC/kylspiral:** Boil→Chill, sanitering, kylmetod, pump, extern processsensor och vört-ut under Chill/Transfer. Säkerställ observe-only i skrivvägarna.
- **Equipment Learning:** läsning/råd/historik utan automatiskt APPLY i observe-only; kontrollera energi, temperatur och HA-omstart.
- **Manual/BF/BT/RAPT:** håll receptkälla, timer och fysisk styrbehörighet åtskilda. Tidigare paus- och Mash-In-incidenter är inte retroaktivt godkända.
- **Dashboard:** SV/EN-paritet, migrerade entity-ID, villkor, versionshänvisningar och användarens egna kort utan automatisk överskrivning.
- **Grainfather GF30:** read-only arkitektur förbereds separat, ingen fysisk styrning godkänd.
- **Dokumentationsbrancher:** [gamla PR #211](https://github.com/Jocke1970/brewassistant-beta/pull/211) beskriver föråldrad effektarbiter; hantera som historik utan direkt merge. Bevara egna Brew Analytics/HLT-filer.

## Historik och referenser

2026-08-29–09-11: käll-/ABORT-arbete, Heatstrike/Mash-In, BrewTracker PAUS och tidigare RAPT-fälttest. 2026-09-17: SG-styrning separat. 2026-09-19: HLT SIM-1 på dev via PR #212, beta.11 Mash-In-test avbrutet (inte PASS), senare source-scoped BA-controller och beta.12/13 är separata utvecklingssteg. 2026-09-20: beta.14 via [PR #221](https://github.com/Jocke1970/brewassistant-beta/pull/221), publicerad utan fysisk acceptans; HLT-fältrapport. 2026-09-22: beta.14 återförd till dev via [PR #223](https://github.com/Jocke1970/brewassistant-beta/pull/223), verklig HA-observer-ID/ABORT-kontroll dokumenterad. [Tidigare roadmap före 20/9](https://github.com/Jocke1970/brewassistant-beta/blob/94b3dbe5f9f62c76d3f847184fad9400b12d3a17/docs/roadmap.md) och [projektstatus 20/9](project-status-2026-09-20_sv.md) bevaras som historik.