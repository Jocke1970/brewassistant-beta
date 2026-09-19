# BrewAssistant: pausad hot-side-styrning och överlämning till RAPT – 2026-09-19

**Status:** Beslut efter avbrutet water-only-test den 19 september 2026. **BA:s aktiva BrewZilla-styrning är pausad som utvecklings- och driftbeslut; det är INTE en implementerad eller verifierad teknisk spärr i beta.11.** RAPT Cloud Link-utveckling och beslut om faktisk RAPT-styrning fortsätter i separat RAPT-chatt. Detta dokument är BA-sidans överlämning, inte en instruktion att starta bryggverket.

> [!CAUTION]
> **Ingen ny BA-styrd fysisk körning.** Operatören har uppgett att dagens test är avbrutet, men fysisk OFF-status för värmare och pump efter sista meddelandet är inte här verifierad. Kontrollera på själva BrewZilla före annan drift. Ett BA-ABORT eller `recovery_required` innebär inte att redan aktiva utgångar nödvändigtvis stängs av. Slå inte på två konkurrerande regulatorer. Att välja en RAPT-profil eller att BA visar `monitor` i en sensor är inte i sig bevis för att alla BA-skrivvägar är avstängda.

## Överenskommen ansvarsfördelning tills vidare

| Del | Avsedd roll | Status |
| --- | --- | --- |
| RAPT/BrewZilla | Enda auktoritet för hot-side-profil och temperaturstyrning; verklig inställning och funktion verifieras i RAPT-chatten. | **Målbild, ej ännu verifierad säker överlämning.** |
| BrewAssistant | Läsning, översikt, loggar, fysisk tidsdiagnostik och lärande *utan* aktuatorskrivningar till BrewZilla. | **Önskat framtida monitor-only-läge; kodbasens skrivvägar finns kvar.** |
| Operatör | Inmäskning, kontroll av pump/flöde och lokala åtgärder. | Manuell kontroll förblir nödvändig. |
| Brewfather | Recept-/metadatafunktion utan parallell fysisk BA-styrning. | Kräver verifierad isolering före samtidig aktiv profil. |
| HLT SIM-1 | Endast read-only-simulering. | Ingen fysisk HLT-effektstyrning eller elektrisk interlock. |

**Ändra INTE RAPT-kod eller profiler i detta BA-arbetsspår.** Utvecklingsdiskussion, verifiering och eventuell implementation av RCL-/RAPT-kontroll sker i den dedikerade RAPT-chatten. Synka sedan fastställda gränssnitt hit, utan att skapa ännu en regulator i BA.

## Versions- och releasefakta

- PR [#213](https://github.com/Jocke1970/brewassistant-beta/pull/213) promoterade `dev` till `beta` med merge-commit `c989cde6dbebe769c2f4ff9575c78b532718f8eb`.
- Publicerad [v0.2.0-beta.11](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.11) är en GitHub **Pre-release** från exakt denna beta-commit. Taggat manifest har `0.2.0-beta.11`; interlock-modulen och dess installation finns i taggen. Distributionen är verifierad, **beteendet i HA inte godkänt**.
- Den äldre beta.10-releasen pekar på fel gammal kod och ska inte användas för nytt styrtest. Ingen publicerad tagg flyttas.
- Den här statusanteckningen skrivs enbart på `dev`. `beta`, `main` och publicerade releaser ändras inte av dokumentationen. Fortsatt versionsflöde är `dev` → PR/merge till `beta` → verifierad ny prerelease; `main` endast för senare stabilt godkänd kod.

## Observerat water-only-förlopp 19 september

**Källor:** operatörens HA-skärmbilder/Jinja-resultat och Brewday Flight Recorder-exporten `Inklistrad text(20260919-115529).txt` i projektchatten. Loggen är en historisk delmängd fram till cirka 11:54 UTC och inte en liveavläsning av HA. Tider nedan är UTC om inte annat anges.

**Verifierat i observationerna:**

1. Vid sessionens start runt `11:27:46` såg BA Brewfather Brew Tracker som `running`, Mash/Ramp to 71.8 °C, `resolved_step_index: 1`, med Mash-In-gate `idle`.
2. `11:28:18` visar Flight Recorder en `brewzilla_action` med `direct_applied`: `set_target:71.8`, `set_heat_utilization:100.0`, `set_pump_utilization:70.0`, `heater_on`, `pump_on`; **gate fortfarande `idle`**. Under senare pre-mash/strike-ramp utfärdades även `set_pump_utilization:100.0`. Före inmäskning kan rampblandning i sig vara avsedd; problemet är att styrning och fysisk Mash-In-auktoritet inte senare kom överens, inte att varje pumpstart före malt är bevisat fel.
3. Operatörens första Jinja-avläsning gav `sensor.brewassistant_brewzilla_control_reason = unavailable`. Från en `unavailable`-sensor får ett saknat attribut **inte** tolkas som att modulen saknas. En senare avläsning visade `physical_mash_interlock_active: True`, `mash_recirculation_phase: recovery_required`, `mash_physical_hold_target: None`, gate `idle` och styrtext `Physical mash authority unknown; ABORT or operator recovery required; no BA writes.` Detta **bekräftar att modulen installerats, inte att dess aktiva styrkedja fungerar**.
4. Samtidigt rapporterades mål `71.8 °C`, pump `on` vid `80 %` och värmare `on`. `recovery_required` hindrade alltså nya BA-kommandon men var ingen dokumenterad fysisk avstängning av redan aktiva utgångar.
5. Fysiska timerkortet visade efter rampen `Hold 66°C · 5 min`, medan styrkortet visade `Gate idle`, `recovery_required` och inget fysiskt mål. **Receptbaserad timervisning är inte bevis för att operatören kvitterat Mash-In eller att styrningen äger 66 °C.**
6. Loggen visar senare att Brewfather blev `inactive`, BA Runtime `aborted` och att värmare sedan pump rapporterades `off` ungefär `11:53:14–11:53:16 UTC`. Det är en historisk avläsning; användarens senare 'Testet avbrutet' bekräftar stopp av testet men inte aktuell fysisk utgångsstatus vid framtida drift.

**Kodfynd att verifiera:** I beta.11 finns en `_runtime`-regel i `brewzilla_physical_mash_interlock.py` som kan sätta `recovery_required` när den interna interlock-staten är tom, Brewfather redan är i Mash med sent steg och gate inte har `completed_once`. Regeln prövar inte explicit ett observerat HA-restart-event. Detta är en plausibel felklassificering av ny/återupptagen session – **exakt kausalkedja är inte ännu fastställd**.

## Viktig arkitekturkollision: nuvarande RAPT-adapter är INTE passiv

Den befintliga BA-filen [`brewzilla_rapt_profile_control_bridge.py`](../custom_components/brewassistant/brewzilla/brewzilla_rapt_profile_control_bridge.py) anger uttryckligen `control_owner: brewassistant`, `brewassistant_role: hot_side_controller` och `heat_pump_owner: brewassistant` vid aktiv RAPT-profil. Den bygger BA-orchestration och kan transportera/återhäva mål och värme-/pumpinställningar. Även [`rapt-brewzilla-profile-runtime.md`](rapt-brewzilla-profile-runtime.md) beskriver den äldre modellen **RAPT som directives → BA som regulator**.

**Därför är det inte säkert att bara starta en RAPT-profil i beta.11 medan BA-integrationen är aktiv.** Den överenskomna målbilden *RAPT äger styrning → BA observerar* är en **arkitekturändring som ännu inte är implementerad och testad end-to-end**. En dashboardknapp, en övervakningsetikett eller en ändrad README är ingen effektiv spärr. För praktisk bryggning innan spärren finns måste varje BA-skrivväg till BrewZilla/RCL isoleras på ett verifierbart sätt, exempelvis genom att inte köra den aktuatorstyrande BA-integrationen och använda oberoende RAPT/BrewZilla-funktioner. Verifiera vilka övriga BA-funktioner som då uteblir; anta inte att avstängning av ett enskilt kort, en modulflagga eller bara Brewfather räcker.

## Parkerat i BA, utan att dölja fel

- Ny fysisk Mash-In/settling/25→50 %-pumpinterlock: **ej fältgodkänd**. Förlorad/otydlig auktoritet och återhämtning behöver isolerade tester innan BA åter får skriva till hot-side.
- Gemensam sessionsmodell: tydlig skillnad mellan `READY`, `Started`, `Complete`, `hold`, `recovery_required`, `ABORT` och källans steg; ingen timer får representera fysisk kvittens som saknas.
- Skrivgräns: central fail-closed monitor-only-/external-owner-gate som blockerar **alla** BA-vägar till mål, heater ON/OFF, värmeprocent, pump ON/OFF/procent, reassert, auto-handoff, STOP och direkta knapp-/servicekommandon, inklusive ordinarie ABORT-semantik som måste definieras om när BA inte äger hårdvaran. Inga automatiska writes vid uppstart eller återanslutning. Kräver kodinventering, regression och verifiering i HA utan aktiv utrustning före användning.
- Dashboard: de stora timer-/maltaxikonerna och vilseledande status prioriteras först efter säker ägarisolering; manuellt inklistrad YAML uppdateras inte av HACS.
- HLT SIM-1 förblir simulering; ingen samtidig fysisk HLT-automation.

## Återstartskriterier och överlämning

**Nästa arbete i BA:** granska samtliga skrivvägar och skapa ett verkligt, verifierbart passivt läge; prioritera sedan läsbara RAPT-data, historik och kompakt UI. Inga nya fysiska BA-actuator-tester, ingen ny betarelease bara för att ändra dokumentation. Om BA någonsin ska återfå aktiv kontroll krävs separat teknisk design, regressionstester och nytt water-only-godkännande.

**Att ta upp i RAPT-chatten:** bekräfta att RAPT/BrewZilla ensamt kan köra den avsedda profilen, vilka steg och manuell kvittens som stöds, hur pump/uppvärmning hanteras lokalt och hur BA:s existerande skrivrätt isoleras innan samtidig integration. Utveckla inte detta parallellt här.

**Gällande princip:** en styrenhet per fysisk aktuator; BA:s observerade data får aldrig användas som bevis på att ett eget skrivförbud redan är implementerat.
