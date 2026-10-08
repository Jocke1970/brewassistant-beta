# BrewAssistant – roadmap och acceptansgrindar

**Uppdaterad 2026-10-01.** [Aktuell beta.15 release-/doc-sync-checkpoint](doc-sync-2026-09-24_sv.md), [beta.15 release notes](beta15-prerelease-notes_sv.md), [HA-fynd 22/9](doc-sync-2026-09-22_sv.md), [historisk status 20/9](project-status-2026-09-20_sv.md), [publicerad beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14).

> [!CAUTION]
> Publicerad ≠ installerad ≠ automatiskt testad ≠ fysiskt accepterad. Beta.14 är publicerad och användaren har installerat den; i HA har read-only-attribut kontrollerats och ABORT-latch återställts separat. Fysiskt vattenprov, fysisk OFF-verifiering och full HA/RCL-end-to-end är **inte godkända**. Varken obevakad drift eller maltprov följer av gröna CI-kontroller.

## Branch- och releaseläge

| Del | Verifierat läge | Nästa grind |
| --- | --- | --- |
| Publicerad `v0.2.0-beta.14` | Tagg låst vid `1a956c04044df870e005392b6bfe946097b9d440`, manifest `0.2.0-beta.14`, CI Python 3.11–3.13/HACS/Hassfest och isolerad HA/RCL-smoke för releasekandidat. | Kontrollerat faktiskt vattenprov, inga oväntade BA-skrivningar och fysisk ABORT-verifiering. |
| `dev` | Beta.15-kandidat med manifest `0.2.0-beta.15`: GF30 read-only thermal/preflight, persistent manuell/Pill-historik, passiv learning, dual-sensor safe-point och valfri coolant/freezer-telemetri. Ingen fysisk GF30-/pump-/frysstyrning. | Granska `dev → beta`, promota med merge commit och validera därefter den faktiska beta-SHA:n. |
| `beta` | Innehåller före promotion beta.14-baslinjen. | Ta emot beta.15 via granskad `dev → beta`-PR med merge commit; kräv CI/HACS/Hassfest och isolerad HA+RCL-smoke på exakt beta-merge-SHA innan tagg/release. |
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
- [PR #223](https://github.com/Jocke1970/brewassistant-beta/pull/223) återförde beta.14-koden till `dev`; [PR #225](https://github.com/Jocke1970/brewassistant-beta/pull/225) slutförde föregående doc-sync `dev → beta`. 24/9-checkpointen är nästa separata granskade promotionspaket och ska gå `dev → beta` innan watchdog-/fältvalidering.
- CI, HACS, Hassfest och isolerad HA+RCL-smoke: `dev` är exkluderad som release-acceptans; efter promotion körs watchdogs på den faktiska beta-SHA:n. Releasebrancher och manuella körningar kan användas vid behov. Bekräfta faktisk workflow-körning och SHA – gamla gröna kontroller är inte nya testbevis. Säkerhetskritiska flöden måste ha separat HA-integrations-/regressionstest.
- [Installationsguide](INSTALLATION.md) ska peka på exakt beta.14-tagg, inte `main`. [CHANGELOG](../CHANGELOG.md) dokumenterar UI-migrering och HA-omstart. Äldre daterade fältrapporter och originalreleaseanteckningar skrivs inte om retroaktivt.

## Prioritet 2 – HLT SIM-1, energi och Brewday-kontrakt

- Fältutdrag 19/9: 94 JSONL-poster, mätarverifiering, ålder för oförändrade setpoints och `Ramp to 72°C`-veto. [Rapport](hlt-sim1-field-validation-2026-09-19.md).
- Fältutdrag 20/9: 44 giltiga JSONL-poster, fem virtuella HLT-ON-prover under RAPT `Heat Strike`, tre hypotetiska effektkonflikter cirka 3,7 kW mot 2,5 kW scenario. `physical_writes=false` och BZ-cap `null` ger inget bevis för andras fysiska utgångar. [Rapport](hlt-sim1-field-validation-2026-09-20.md).
- **Öppen logikavvikelse:** dev:s HLT-parser accepterar `heat strike` som stage men inte exakt `step=Heat Strike` som ramp; explicit positiv källoberoende HLT-beredskap saknas. Definiera avsedd förvärmningsintention, start- och stopptid för RAPT, BrewTracker och Manual. Okänt → fail-closed. Lägg tester för Heat Strike/Water, ramp, Mash In/Out, missmatchad eller stale temperatur, BZ återtag och fysisk mottagare. Rätta kod först när semantiken är beslutad; gör om helt virtuellt read-only-prov.
- HLT SIM-1 är 30 s läskonsument; den begränsar inte BZ. Virtual energy recipient `none`/`hlt` kan ha en coordinator-cykels fördröjning; verifiera faktisk sensor, `_2`-suffix och kortets översättningar `Ingen`/`HLT (virtuell)`. Fysisk mottagare okänd utan verifierade mätare.
- Eventuell framtida fysisk HLT kräver självständig snabb fail-OFF, fysisk OFF-verifikation, rätt eldimensionering och torrkokningsskydd. Simulerad budget är inget elsäkerhetsskydd.

## Prioritet 3 – behåll övriga parallella moduler

- **Fermentation:** SG-styrning/Brewfather-jässcheman separat. Jässtrategi och fysisk jäsutrustning är oberoende val. Provider-runtime/select/persistence, exklusiv chamber/GF30-arbitration, normaliserad read-only provider-snapshot och provider-conditional fermentation-UI är implementerade på `dev`; provider-aware Brewfather Custom Stream-handoff och full acceptance/CI återstår. [Provider-kontrakt](fermentation-provider-selection.md). [Tvålägeskontrakt, redigerbara SG-/timparametrar och återstående UI/integration](sg-driven-fermentation.md); den rena SG-regelmotorn är ännu inte inkopplad. Climate Supervisor kräver fullcykeltest.
- **Cooling/CFC/kylspiral:** Boil→Chill, sanitering, kylmetod, pump, extern processsensor och vört-ut under Chill/Transfer. Säkerställ observe-only i skrivvägarna.
- **Equipment Learning:** läsning/råd/historik utan automatiskt APPLY i observe-only; kontrollera energi, temperatur och HA-omstart.
- **Manual/BF/BT/RAPT:** håll receptkälla, timer och fysisk styrbehörighet åtskilda. Tidigare paus- och Mash-In-incidenter är inte retroaktivt godkända.
- **Dashboard:** SV/EN-paritet, migrerade entity-ID, villkor, versionshänvisningar och användarens egna kort utan automatisk överskrivning.
- **Grainfather GF30:** live GF30 är nu Wi-Fi-/cloud-länkad och intern temperatur når HA. Grainfather history är verifierad att även bära `target_temperature`, vilket nu är första planerade utökningen av upstream-integrationen. Integrationsstrategin följer RCL-mönstret: fork `Jocke1970/grainfather_integration` finns nu, `main` hålls upstream-ren och BA-utveckling sker på `brewassistant-grainfather`. Första read-only-patchen för `target_temperature` är implementerad och en separat Particle-probe finns för nästa fältgrind. Historiska `gfFermentation` och `grainfather_exporter` används som protokollreferenser för möjlig realtime `target`/`heatStatus`/`coolStatus`/online-data, inte som kod som mergas rakt in. Particle-vägen är nu testad live och Grainfather returnerade 0 Particle-sessioner för den länkade GF30:n. Den historiska Particle-vägen är därför bortvald som runtime-spår; research fortsätter mot den moderna ESP/Grainfather-backenden. Ingen Grainfather-targetwrite, pump-, frys- eller coolant-setpoint-write är ännu godkänd. [Integrationsroadmap](backends/grainfather-integration-extension.md), [cloud-link recovery](backends/gf30-cloud-link-recovery.md), [fältnotering 26/9](gf30-coolant-field-note-2026-09-26.md).
- **Dokumentationsbrancher:** [gamla PR #211](https://github.com/Jocke1970/brewassistant-beta/pull/211) beskriver föråldrad effektarbiter; hantera som historik utan direkt merge. Bevara egna Brew Analytics/HLT-filer.

## Historik och referenser

2026-08-29–09-11: käll-/ABORT-arbete, Heatstrike/Mash-In, BrewTracker PAUS och tidigare RAPT-fälttest. 2026-09-17: SG-styrning separat. 2026-09-19: HLT SIM-1 på dev via PR #212, beta.11 Mash-In-test avbrutet (inte PASS), senare source-scoped BA-controller och beta.12/13 är separata utvecklingssteg. 2026-09-20: beta.14 via [PR #221](https://github.com/Jocke1970/brewassistant-beta/pull/221), publicerad utan fysisk acceptans; HLT-fältrapport. 2026-09-22: beta.14 återförd till dev via [PR #223](https://github.com/Jocke1970/brewassistant-beta/pull/223), och dokumentation synkad till beta via [PR #225](https://github.com/Jocke1970/brewassistant-beta/pull/225); verklig HA-observer-ID/ABORT-kontroll dokumenterad. 2026-09-24: beta.15-kandidat och doc-sync med GF30 read-only thermal/preflight, persistent observations, diagnostics och förberedd coolant entity mapping; ingen ny fysisk styrning. 2026-10-01: GF30 Wi-Fi/cloud/account-link verifierad, intern temperatur synlig i HA, `target_temperature` verifierad i Grainfather history och separat BA-Grainfather integrationsroadmap definierad enligt RCL-branchmönstret. [Tidigare roadmap före 20/9](https://github.com/Jocke1970/brewassistant-beta/blob/94b3dbe5f9f62c76d3f847184fad9400b12d3a17/docs/roadmap.md) och [projektstatus 20/9](project-status-2026-09-20_sv.md) bevaras som historik.