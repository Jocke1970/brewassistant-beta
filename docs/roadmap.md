# BrewAssistant – roadmap och acceptansgrindar

**Statusdatum: 2026-09-20 · Dokumentationsgren: `dev` · senaste publicerade release: [v0.2.0-beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14).** Den här levande roadmapen ersätter äldre inaktuella rubriker om "kommande beta.12". Läs [faktabaserad status och branchskillnader](project-status-2026-09-20_sv.md) för SHA, evidens och länkar. [Föregående roadmap före synken](https://github.com/Jocke1970/brewassistant-beta/blob/94b3dbe5f9f62c76d3f847184fad9400b12d3a17/docs/roadmap.md) finns kvar som historisk snapshot.

> [!CAUTION]
> **Publicerad ≠ installerad ≠ automatiskt testad ≠ fysiskt accepterad.** Beta.14 innehåller observe-only-behörighet, ABORT-försök och separat manuellt RCL-kort, men fysisk funktion är ännu inte verifierad i användarens HA. Det finns ingen verifierad tillåtelse till obevakad bryggning eller maltprovning utifrån dessa kontroller. `dev` har fortfarande manifest `0.2.0-beta.13` och saknar beta.14:s observe-only-kod; den här doc-synken backportar den inte. BZ:s faktiska värmare, pump och effekt måste alltid kontrolleras lokalt; ABORT-ACK är inget OFF-bevis.

## Aktuell release- och branchmatris

| Del | Implementerat/verifierat | Nästa grind |
| --- | --- | --- |
| **BA beta.14** | Tagg `v0.2.0-beta.14` → PR #221:s exakta beta-merge-SHA `1a956c04044df870e005392b6bfe946097b9d440`, manifest matchar. CI Python 3.11–3.13, HACS och Hassfest gröna på merge-SHA; isolerat HA/RCL-prov på kodidentisk kandidat. | Fysisk acceptans, verifierad install/tagg och faktisk readback i HA. `beta` har efter tagg en separat engångsworkflow-städning, inte en ny publicerad version. |
| **`dev`** | HLT SIM-1, september-19-diagnostik och separata doc-synkposter. Pre-sync HEAD `94b3dbe`, manifest `0.2.0-beta.13`. | Granskad **beta → dev-rekonciliering**, utan att gömma omergat arbete eller förutsätta identisk kod. Före sync var brancherna divergerade (beta 67 commits före, dev två egna); uppdatera jämförelse vid faktisk integration. |
| **`main`** | Äldre stabil branch, ingen beta.14-promotion. | Ingen promotion förrän godkänd fältvalidering och uttryckligt beslut. |
| **HLT** | Endast läsande simulering; 19/9 och 20/9 fältutdrag dokumenterade. | Definiera avsedd HLT-beredskap, hantera `Heat Strike` och omtesta virtuellt innan något fysiskt HLT-arbete. |

## Prioritet 0 – säkert och entydigt BA/RCL-samspel

**Levererat i publicerad beta.14, ännu inte fysisk acceptans:**

- `switch.brewassistant_brewzilla_observe_only` **PÅ** förhindrar BA:s *ordinarie* automatiska skriverier till BrewZilla och ska fail-closed vid HA-start. PÅ skickar inte automatiskt OFF eller 0 %. **AV** kräver färsk källa och flera färska enhets-readbacks. Den gamla inerta `brewzilla_orchestration_enabled` är borttagen; migrera referenser i användarens egna kort, skript och automationer.
- **ABORT är separat ovillkorlig nödlane:** försöker stoppa RAPT-profil och skicka OFF/0 även i observe-only. Bevis för skickat kommando får inte döpas om till fysisk OFF-verifikation. Kontroller av verklig värme, pump, huvudström och effekt kvarstår.
- **Manual Brewday:** separat [SV](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only_sv.yaml)/[EN](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only.yaml) observationskort med direkta RCL-operatörsreglage bredvid ordinarie Manual-kort. Visa reglagen endast vid observerande BA, Manual-källa, bekräftad inaktiv RAPT-profil och ingen ABORT. Det är UI-villkor, inte ett globalt skydd för andra direkt-RCL-ytor.
- RAPT-profil ger processteg/mål; BA-automationsbehörighet är separat. BF/BT och Manual har egna ägarregler; ingen tyst BT-fallback vid RAPT-bortfall, ingen dubbelreglering. BF-fermentering är oberoende. [Käll- och driftkontrakt](brewday-execution-modes.md), [beta.14-releaseanteckningar](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/beta14-prerelease-notes_sv.md).

**Acceptanschecklista för nästa övervakade vattenprov:**

1. Bekräfta fysisk inaktivitet, lokalt säkert bryggverk och backup. Läs exakt installerad BA-tagg/manifest `0.2.0-beta.14` och RCL-fork `v0.5.0-beta.1` (inte två `rapt_cloud_link`-installationer). Sätt BA observe-only PÅ och verifiera att den faktiskt registreras; avsaknad av en switch betyder **inte** read-only.
2. Starta BA/RCL i verklig HA och logga både BA-begäranden och RCL:s verkliga moln-/enhetsreadback. Bekräfta att BA varken återsätter operatorns manuella target/heat/pump eller skickar gamla väntande kommandon. Läs- och lärfunktioner ska fortsätta passivt.
3. Montera det separata observationskortet för vald språkvariant och prova UI-under uppsikt: endast när RAPT-profil är bekräftat stoppad och rätt Manual-källa är aktiv. Direkt-RCL-kommandon är operatörsåtgärder; kortet är inte en elektrisk spärr.
4. Prova uttrycklig ABORT med möjlighet att bryta strömmen fysiskt. Kontrollera självständigt faktisk värmare, pump, huvudström/effekt och att ingen gammal BA-reglering startar igen. Om status eller readback är okänd: avbryt och använd lokal fysisk kontroll.
5. Verifiera restart/reload och byte PÅ/AV utan oförutsedd återstart. Dokumentera utfallet i en **ny daterad fältrapport** och uppdatera [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220); markera inte fält-PASS utifrån mockade HA-tjänster eller grön GitHub Actions.

**Beroende och ordning:** fysisk BA-kontroll är inte grundlagd genom HLT-simulatorn. HLT behöver inte driftsättas för att kunna utvärdera BA observe-only. Ändra ingen aktiv HA-installation från gamla feature-arkiv under bryggning.

## Prioritet 1 – branch-/kodrekonciliering utan releaseförväxling

1. Jämför `dev` och `beta` **på filnivå**, med speciell uppmärksamhet på observe-only-write boundary, ABORT, switchregistrering, direkta Manual-kort, manifest, tester, CI-workflows och HLT. Dokumentera vilka commits som redan har gemensamt innehåll trots olik historik.
2. Återför beta.14-funktionerna till `dev` i ett **separat granskat kodarbete**. Varken denna roadmap, ändrade dokument eller en `dev`-manifestetikett får räknas som backport. Bevara SG-/CFC-/andra parallella BA-moduler och undvik helkatalogbyte.
3. Nästa framtida version följer [CONTRIBUTING](../CONTRIBUTING.md): sammanhängande kandidat, granskad `dev → beta` PR med **Create a merge commit**, CI/HACS/Hassfest på *exakt merge-SHA*, ny tagg/version, läs tillbaka taggad kod/manifest och gör nytt kontrollerat installationstest. Flytta aldrig en publicerad tagg. `beta → main` kräver separat fältbevis och beslut.
4. Automatiska `dev`-testtriggers togs bort 20/9 från CI/HACS/Hassfest; kontroller gäller releasebrancher, promotion, `beta`, `main` eller explicit manuell körning. Dokumentera en faktisk körning och dess SHA; anta inte att nya dev-doc-commits testats av en gammal grön beta-körning.

## Prioritet 2 – HLT SIM-1 och Brewday-källkontrakt

**Historik 19/9:** 94 JSONL-poster, mätarverifiering och rättningar för ålder på oförändrade `number`-setpoints och explicit `Ramp to 72°C`-veto dokumenterade i [fältöverlämningen](hlt-sim1-field-validation-2026-09-19.md). Detta var dåvarande test, inte en fullständig efterhandsacceptans.

**Ny observation 20/9:** [44-posters delrapport](hlt-sim1-field-validation-2026-09-20.md) innehåller fem simulerade HLT-värmeprover under RAPT `Heat Strike`, tre **virtuella** konflikter på ~3,7 kW mot 2,5 kW scenario och inga fysiska HLT-skrivningar eller BZ-caps i dessa loggrader. Allt under `stage=Mash`; nuvarande runtime `dev` saknar ett ramp-veto för det exakta `step=Heat Strike`, även om det accepterar `heat strike` som stage. HLT har alltså fått virtuell grant innan ett källaoberoende **positivt HLT-beredskapskontrakt** definierats. Kodfix och accepterad hel fältkörning saknas.

1. Samordna Brewday-/HLT-ägare: definiera explicit HLT-förvärmningsbehov, positiv startberedskap, rampintention och stopptid i RAPT, BrewTracker och Manual. Stage-namn eller låg BZ-watt räcker inte som trigger. Okänd källa/intent ska fail-closed.
2. Lägg till riktade regressionstester för `Heat Strike`, `Heat Strike Water`, `Ramp to ...`, Mash In, Mash Out, mismatch/stale sensor, positiv HLT-start och BZ autonomt återtag. Rätta parser/gating i kod **först efter** avtalad semantik, utan att ändra BZ:s absoluta prioritet eller ge fysisk HLT tillstånd.
3. Verifiera installerad kort-YAML, exakt `sensor.brewassistant_hlt_virtual_energy_recipient` och eventuell `_2`-suffix. `none` → `Ingen`, `hlt` → `HLT (virtuell)`; loggen kan ligga en HA coordinator-cykel före den publicerade sensorn. Den *fysiska* mottagaren förblir okänd utan båda effektmätarna.
4. Kör ett helt nytt kontrollerat **read-only** JSONL-prov och verifiera ramp → väntan → avsedd virtuell ON → yield/off och tid/temperaturmodell. Tidigare delutdrag räcker inte som acceptans. [HLT-kod](../custom_components/brewassistant/hlt/README.md), [sensoravtal](hlt-dashboard-backend.md), [kortguide](hlt-dashboard-card.md).
5. En eventuell framtida **fysisk** HLT är ett eget hårdvaruprojekt med snabb fristående fail-OFF-interlock, bekräftad fysisk OFF, korrekt elsäkring/kablar och torrkokningsskydd. En 30 s HA-simulator och hypotetisk 2 500 W-budget är inget sådant skydd. BZ stryps aldrig.

## Prioritet 3 – övriga moduler, inte tappade av HLT-arbetet

- **Fermentation:** SG-styrd utveckling och Brewfather-jässcheman är separat arbetsström; Climate Supervisor kräver fullcykeltest. Ingen oavsiktlig utrensning vid beta→dev-rekonciliering.
- **Cooling/CFC/kylspiral:** Boil→Chill, sanitering, kylmetod, pump och extern sensor som vört-ut under Chill/Transfer behöver test, inklusive observerande BA och att ingen skrivrätt läcker genom kylmodulen.
- **BrewZilla Equipment Learning:** enbart läsa och föreslå tills särskilt accepterad; kontrollera energi, temperaturkurva och session efter HA-omstart. Inget automatiskt APPLY under observe-only.
- **Manual/BF/BT/RAPT:** håll receptkälla, tidsägare och fysisk styrbehörighet åtskilda. BrewTracker PAUS och Mash-In-fältacceptans från beta.11 är inte retroaktivt godkända av senare code tests.
- **Dashboard:** matcha SV/EN, gamla entity-ID, aktuell releaseversion och manuellt inklistrade kort. Putsning av stora runtime-kort efter att ägarskap/read-only verifierats.
- **Grainfather GF30:** read-only upptäckt/arkitektur parkerad, ingen fysisk skrivstyrning godkänd.
- **Dokumentationsbrancher:** [PR #211](https://github.com/Jocke1970/brewassistant-beta/pull/211) är en öppen gammal HLT-plan med en effektarbiter som inte beskriver SIM-1:s ostrypta BZ-prioritet. Markera/hantera som ersatt; merge:a inte direkt. Säkra egna Brew Analytics-/HLT-dokument innan eventuell branchstädning.

## Historik och underlag (bevaras, inte omskrivna till PASS)

- 2026-08-29–09-11: Brewday/BrewZilla source/ABORT, Heatstrike/Mash-In, BrewTracker PAUS, fysiska tidsmätningar och RAPT-profilutveckling. [Tidigare roadmap-snapshot](https://github.com/Jocke1970/brewassistant-beta/blob/94b3dbe5f9f62c76d3f847184fad9400b12d3a17/docs/roadmap.md), [äldre valideringar](physical-validation-2026-09-06.md).
- 2026-09-17: SG-driven fermentation som egen modul.
- 2026-09-19: HLT SIM-1 mergad i `dev` via [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212); beta.11-water-only Mash-In-test avbrutet och **ej accepterat**. [BA-paus/incident](ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md); senare source-scoped BA-controller [PR #215](https://github.com/Jocke1970/brewassistant-beta/pull/215) och publicerade beta.12/beta.13 är separata evolutioner, inte ändringar av incidentens historik.
- 2026-09-20: HLT-fältutdrag och dokumentationsåtgärder; beta.14 observe-only/ABORT/Manual-direktreglage via [PR #221](https://github.com/Jocke1970/brewassistant-beta/pull/221), publicerad prerelease men **ingen dokumenterad fysisk acceptans**. [Aktuell status](project-status-2026-09-20_sv.md).

**Källprincip:** Kod på en branch, taggad release, publicerad GitHub-release, faktisk HA-installation, grön isolerad CI och fysiskt validerat utfall är *olika tillstånd*. Skriv aldrig över en gammal fältrapport för att få den att se godkänd ut. Nya händelser ska få en ny daterad rapport och, när det finns kodändringar, en separat ny version/tagg.
