# BrewAssistant 2026_09-20 — fix-beta (v0.2.0-beta.14)

**Repository:** `Jocke1970/brewassistant-beta`  
**Kandidattagg:** `v0.2.0-beta.14` (NY; får inte flytta tidigare taggar)  
**Manifestversion:** `0.2.0-beta.14`  
**GitHub-release:** `BrewAssistant 2026_09-20 — fix-beta`; välj **Pre-release** i GitHub/HACS, aldrig stable/latest.  
**Taggpunkt:** slutligt granskat och CI-verifierat **beta-merge-SHA** efter PR `dev → beta`. Mergemetod **Create a merge commit**, inte squash eller rebase. Tagga inte feature-/release-branchen eller ett äldre SHA.

> [!WARNING]
> Detta är en kandidat, inte ett påstående om fysisk eller installerad säkerhet. Kodtester kan inte verifiera att värmare och pump är fysiskt avstängda. Ingen obevakad körning eller maltprovning före godkänt praktiskt vattenprov. En BA-observationsswitch kan inte återkalla ett redan skickat molnkommando och blockerar inte BrewZillas reglage, RCL:s egna oberoende automatik eller direktstyrning av RCL-entiteter utanför BA.

## Fix jämfört med publicerade beta.13

- Ny operatörsswitch `switch.brewassistant_brewzilla_observe_only`: **PÅ = Endast observation, styr BrewZilla lokalt**. Uppstart är fail-closed; vid HA-omstart återställs switchens val men återaktiverad skrivbehörighet återges aldrig automatiskt.
- Backendspärr mot BA:s hot-side-utgångar och policyrouter: även OFF, 0 %, huvudström och prefixed entity-ID:n nekas. Inga kommandon skickas enbart för att gå in i observationsläget. Befintliga kvittensplaner, BA-ägd utilization och lokal kontrolllease rensas.
- Nya BA-policyförfrågningar för BrewZilla nekas redan före skapande av ny kvittens. Senare direktverkställning kontrolleras också. Logg, återläsning, diagnostik och passiv learning fortsätter; Learning APPLY tillåts inte i observationsläget.
- Att slå AV switchen räcker inte för att återuppta BA-reglering. Separat operatörsbekräftelse via `brewassistant.brewzilla_rearm_after_observe` kräver en aktiv, identitetsverifierad RAPT-session och färsk läsning av temperatur, mål, värme, pump och utilization. ABORT och andra befintliga spärrar gäller fortfarande. Gamla planer spelas inte upp igen.
- Nya operatörskort `dashboard/cards/brewzilla_observe_only_sv.yaml` respektive engelsk spegel. Lägg svenska kortet överst i bryggdagsvyn. Visar effektiv observationsspärr, källstatus och vad operatören ska göra. Att direkt styra RCL-entiteter i äldre dashboardkort är **inte** BA-styrning och blockeras inte av denna switch.
- Behåller beta.13:s passiva länkförlust-/STOP-kontrakt och befintlig RCL-fork `v0.5.0-beta.1`; ändrar inte RCL.

## Genomförda tester 2026-09-20

- **376/376 regressionstester godkända** på Python 3.11, 3.12, 3.13; kvalitetskontroller, HACS och Hassfest godkända.
- **Isolerad HA/RCL smoke godkänd:** verklig Home Assistant Core 2026.9.3 på Python 3.14.2 och fastlåst RCL beta.1-kod. Testet kör BA/RCL-funktioner mot HA:s riktiga StateMachine och ServiceRegistry, med falska tjänstemottagare som registrerar BA-försök utan att kontakta moln eller hårdvara. Kontrollerade dynamisk profilidentifiering, mål/värme/pump inkl. OFF/0, RAPT STOP, fortsatt spärr efter switch AV utan rearm, oberoende direkta tjänsteanrop och ofullständigt profilkontrakt. Se `tests/integration/ha_rcl_observe_smoke.py` och körningen https://github.com/Jocke1970/brewassistant-beta/actions/runs/35518259462.
- **Begränsning:** smoke-testet startar inte riktiga BA/RCL config entries, anropar inte RAPT Cloud, mäter inte fysiska utgångar och omfattar inte full Flight Recorder/learning/energi via reload, CFC/handoff eller redan påbörjade asynkrona kommandon. Detta är kvarstående acceptanskrav, inte godkända tester.

## Återstående verifiering innan denna kandidat får publiceras

1. Verifiera komplett CI, Hassfest, HACS och HA/RCL smoke på samma slutliga SHA. Ändra inte publicerade beta.12/beta.13-filer.
2. Verifiera full Home Assistant-dispatch med autentiska registrerade BA/RCL-config entries och tjänster samt fångade utgående molnkommandon: manuell BA-service, Heatstrike/Mash-in, Sparge, ABORT, direkt policy, Supervised Apply, RAPT STOP och CFC/överlämning. Med observation PÅ: **noll BA-anrop till BrewZilla** för både ON och OFF/0. Skilj redan utgående anrop från nya.
3. Granska befintliga UI-kort: BA:s hårdvaruknappar ska vara dolda/inaktiva i observation; RCL:s direkta entiteter ska förklaras tydligt som oberoende av BA. Verifiera att endast faktiskt väntande kvittenser visas.
4. Kontrollera att Flight Recorder, passiv learning och energilogging fungerar även vid stale RCL, omstart och växling mitt i väntande plan. Kontrollera återaktiveringen utan automatisk återspelning.
5. Skapa PR `dev → beta`, granska all divergens, välj **Create a merge commit**, kör CI igen på exakt beta-merge-SHA. Först sedan skapa ny tagg/release `v0.2.0-beta.14` på det SHA:t, markera **Pre-release** och kontrollera manifestversionen på taggen. Ingen promotion till `main`.

## Installation och praktiskt vattenprov efter publicerad release

Verifiera att BrewZilla är i känt och säkert läge med lokala reglage och användaren närvarande. Installera ny exakt taggad BA-beta via HACS medan bryggverket är inaktivt, behåll rätt RCL-fork och befintliga integrationsposter. Starta om HA, kontrollera observer-switchens effektiva tillstånd och att ingen BA-tjänst skickat någon BrewZilla-åtgärd vid uppstart. Aktivera därefter en kontrollerad RAPT-testprofil och ändra temperatur/pump/värme **endast lokalt på BrewZilla**. Bekräfta att BA läser och loggar, men inte återställer dina lokala val. Kontrollera Flight Recorder och separat fysisk effekt/utgångar. Slå inte AV switchen eller kör återaktivering under det rena observationsprovet. Stoppa testet vid oväntade kommandon eller avvikande värme/pump.

**Kända begränsningar:** Kod-, CI- och isolerade HA/RCL-tester är inte komplett live HA/RCL-end-to-end eller fysiskt prov. RCL och fysiska reglage arbetar oberoende av BA; observation får aldrig tolkas som en nödstoppfunktion. Bekräfta faktisk avstängning med bryggverkets lokala reglage och fysisk mätning när det behövs.

**Historik:** `docs/beta13-prerelease-notes_sv.md` och redan publicerad `v0.2.0-beta.13` lämnas oförändrade.
