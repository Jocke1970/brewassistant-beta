# BrewAssistant 2026_09-02 — beta (v0.2.0-beta.13)

**Repository:** `Jocke1970/brewassistant-beta`  
**Förväntad tagg:** `v0.2.0-beta.13`  
**Manifestversion:** `0.2.0-beta.13`  
**GitHub-release:** `BrewAssistant 2026_09-02 — beta`; välj **Pre-release**, aldrig stable/latest.  
**Taggpunkt:** exakt verifierad merge-commit på `beta` efter PR `dev → beta`, inte `dev` eller ett tidigare publicerat taggobjekt. Ange slutligt SHA först efter merge och checks.

> [!WARNING]
> Denna kandidat är inte fysiskt accepterad. Grön CI, HA-status och ett godkänt molnkommando är inte bevis på att värmare eller pump faktiskt stängts av. Ingen praktisk testkörning från utvecklingsbranch; efter publicering först read-only, sedan separat godkänd övervakad vattenprovning med faktisk fysisk återkoppling. Ingen obevakad drift eller maltprovning på denna grund.

## Nytt jämfört med publicerade beta.12

- Åtgärdar issue #217 via [PR #218](https://github.com/Jocke1970/brewassistant-beta/pull/218): upptäck RCL:s faktiska profil-binärsensor med `ba_source` och följ dynamiska entitets-ID:n i stället för ett hårdkodat ID.
- Saknad, `unknown`, `unavailable`, för gammal eller ofullständig profiltelemetri spärrar nya BA-skrivningar som kräver färsk processdata och ogiltigförklarar gamla Supervised Apply-kvittenser; den utlöser **inte** automatiskt STOP, heater OFF, pump OFF eller nollställning av utilization. RCL/BrewZilla behåller autonomt ägarskap.
- Bekräftad profil-STOP kräver färsk RCL-attestering som matchar tidigare observerat sessions-ID; enbart `off`, uteblivet molnsvar eller ett övergående stegbyte räcker inte.
- En fördröjd eller externt observerad STOP uppdaterar endast BA:s status. BA skickar inte en andra serie fysiska OFF-/nollställningskommandon och gränssnittet påstår inte att utgångarna är fysiskt verifierade avstängda.
- START/END-kommandosvar och efterföljande statusavläsning hanteras åtskilt i beroende RCL-version. Explicit operatörs-ABORT/STOP ska hållas åtskild från passiv observationslogik; fullständigt beteende och faktisk fysisk verkan måste bekräftas i installationsprovet.
- Befintliga BF/BT/Manual-flöden, svenska/engelska dashboardkort, HLT-simulering och hot-side-källregler behålls från beta.12. Inga dashboardfiler ingår i PR #218; ingen ny manuell YAML inklistring krävs enbart för denna ändring.

## Beroende

Kräver publicerad RAPT Cloud Link **fork-prerelease `v0.5.0-beta.1`** från `Jocke1970/home-assistant-rapt-cloud-link`, taggad på `149d51aaa4d467fd37c932ceaf8161c9f1387314`. Original-repot och dess `main` ska inte ersättas med vår kod. HACS ska peka på rätt fork; installera inte två integrationer med samma domän `rapt_cloud_link` parallellt.

## Publiceringsgrind

1. Bekräfta att `dev` har manifest `0.2.0-beta.13`, denna release-text och ändringarna från PR #218. Kräv grön CI på Python 3.11/3.12/3.13, Hassfest och HACS på exakta slutliga `dev`-SHA:t.
2. Granska **hela** separata PR:n `dev → beta`, inklusive den historiska divergensen mellan brancherna; inga ändringar till `main`. Mergemetod **Create a merge commit**, inte squash/rebase. Ta inte bort `dev`.
3. Kräv gröna CI/Hassfest/HACS på **exakt beta-merge-SHA**; läs manifest, `brewzilla/__init__.py`, `brewzilla_rapt_link_loss_guard.py`, `brewzilla_rapt_identity_guard.py`, tester och denna fil från samma SHA.
4. Först därefter: skapa NY tagg `v0.2.0-beta.13` på beta-merge-SHA och publicera GitHub **Pre-release** med full text från detta dokument. Återanvänd/flytta aldrig beta.12-taggen. Kontrollera den publicerade taggens SHA och dess manifestversion mot beta-merge-SHA.

## Installation och acceptans (endast efter båda prereleaserna)

1. När bryggverket är inaktivt: verifiera värmare/pump fysiskt, säkerhetskopiera HA/integrationer/dashboard, installera exakt RCL-taggen och därefter exakt BA-taggen via HACS. Behåll befintlig HA-integrationspost och credentials. Starta om HA medan bryggverket är inaktivt.
2. Bekräfta installerade manifestversioner `0.5.0-beta.1` (RCL) och `0.2.0-beta.13` (BA), befintliga entiteter och faktisk RCL-profilsensor med `ba_source`. Validera session, steg, mål, färskhet och source ownership i read-only-läge.
3. Simulera tappad eller gammal status utan att skicka fysiska BA-kommandon. Verifiera noll BA-skrivningar, indragna väntande kvittenser, bibehållet RAPT-ägarskap och att återanslutning omvärderar session/steg/mål utan återspelning av kommandon.
4. Kontrollera ett verkligt, färskt STOP och ett **separat uttryckligt** STOP/ABORT under säker uppsikt. Kontrollera fysisk värme/pump separat; API-ACK och HA-entity `off` är inte hårdvarubevis. Säkerställ att inget extra OFF-/nollställningskommando triggas av fördröjd readback.
5. Eventuellt vattenprov: operatör närvarande, bara Supervised Apply med en separat kvittens per åtgärd och lokal säkerhetskontroll. Respektera RAPT:s egna session/steg/mål, vattennivå och pumpens primning. HLT SIM är inte en fysisk effektvakt. Stoppa vid avvikelse och dokumentera i en NY daterad fältrapport; rätta i `dev`, promotera ny beta-version. Ingen `main`-promotion utan fysisk acceptans och uttryckligt beslut.

## Kända gränser

- Testerna för länkbortfall och STOP är utan fysisk BrewZilla. De bekräftar kodkontrakt, inte faktiskt utgångsläge, full HA-installation eller webbkortsrendering.
- Ett redan ivägskickat molnkommando kan inte dras tillbaka av BA:s telemetry-guard.
- RCL:s STOP-attestering bygger på två rena molnavläsningar knutna till samma observerade session; det är inte en oberoende elektrisk säkerhetsfunktion.
- Explicit ABORT-vägen och eventuella återstående gamla skrivvägar ska verifieras i ett separat kontrollerat integrationsprov; inga löften om fysisk OFF följer av denna release.

**Historik:** [beta.12-releaseanteckningar](beta12-prerelease-notes_sv.md) lämnas oförändrade som dokumentation för den redan publicerade versionen.