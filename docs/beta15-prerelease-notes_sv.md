# BrewAssistant 2026_09-24 — GF30 read-only beta (v0.2.0-beta.15)

**Repository:** `Jocke1970/brewassistant-beta`  
**Manifestversion:** `0.2.0-beta.15`  
**Releaseform:** GitHub **Pre-release**, aldrig stable/latest  
**Taggpunkt:** exakt verifierad merge-commit på `beta` efter separat `dev → beta`-PR med **Create a merge commit**

> [!WARNING]
> Beta.15 tillför GF30-diagnostik och mätunderlag, inte fysisk GF30-/pump-/frysstyrning. Gröna tester, HA-states och cloud-readback bevisar inte fysisk avstängning eller säker kylning. Använd fysisk utrustning endast under uppsikt och med separat lokal möjlighet till avstängning.

## Vad som är nytt jämfört med beta.14

### GF30 thermal preflight före full Wi-Fi-validering

`grainfather_fermenter/` har nu en persistent read-only preflight-runtime. Operatören kan mata in en manuell referenstemperatur medan BrewAssistant samtidigt fångar den konfigurerade RAPT Pill-temperaturen och dess Home Assistant-tidsstämpel.

Nya tjänster:

```text
brewassistant.gf30_record_manual_temperature
brewassistant.gf30_clear_preflight
```

Historiken sparas i Home Assistant Store och begränsas till 200 observationer. Varje checkpoint kan märkas med exempelvis `baseline`, `cooling`, `recovery` eller `cold_crash`.

### Passiv thermal learning

BrewAssistant sammanställer redan observerade mätpar och kan visa bland annat:

- Pill minus manuell referens;
- absolut delta;
- antal learning-eligible mätpar;
- observerad Pill-kyl-/värmehastighet i °C/h;
- enkel observational confidence och fasfördelning.

Learning väljer inte automatiskt en vinnande temperaturgivare, korrigerar inte sensorn och skapar inget styrkommando.

### Dual-sensor safe-point för Pill + GF30 intern temperatur

När Grainfather-integrationen exponerar en controller-/intern temperatur jämför BrewAssistant Pill och intern GF30 temperatur parallellt. Freshness kontrolleras separat. Där upstream `last_heard` finns och går att tolka används den före vanlig HA `last_updated` för intern GF30-freshness.

Diagnostiken rapporterar bland annat:

```text
dual_sensor_agree
dual_sensor_disagree
pill_only
internal_only
no_fresh_temperature
```

`gf30_safe_point = dual_fresh_agree` betyder endast att två färska temperaturer ligger inom aktuell diagnostisk tolerans. Det är **inte** ett tillstånd att aktivera pump, frys eller target-write.

### Coolant/freezer-monitor förberedd

Tre nya valfria options-fält är tomma som standard:

```text
gf30_coolant_temp_entity
gf30_freezer_air_temp_entity
gf30_coolant_thermostat_entity
```

När riktiga entiteter senare väljs kan BrewAssistant läsa köldmedietemperatur, frysluft och `generic_thermostat`-telemetri. Tomma mappings är giltiga och fail-passive.

Ägarskapet är explicit:

- GF30:s lokala regulator äger sin pump och lokala öltemperaturreglering;
- Home Assistant `generic_thermostat` är avsedd ensam ägare av frysen;
- BrewAssistant är read-only för denna krets i beta.15;
- säker coolant-setpoint, mediumets fryspunkt och fysisk fail-OFF är inte validerade.

## Nya read-only sensorer

Beta.15 registrerar bland annat sensorer för:

- GF30 backend/controller-status;
- preflight-status, Pill/manuell temperatur och temperaturdelta;
- observation/sample counts och learning confidence;
- aktuell/medel cooling-rate;
- dual-sensor status och safe-point;
- coolant-status, coolant-temp, frysluft, luft-minus-coolant och thermostat target.

Exakta entity-ID skapas av Home Assistant utifrån integrationsnamn/unique IDs; verifiera den faktiska installationen efter omstart.

## Installation / första mätprov

1. Installera exakt `v0.2.0-beta.15` via HACS först efter publicerad prerelease och verifierad tagg.
2. Starta om Home Assistant.
3. Lämna coolant/freezer-mappings tomma tills de verkliga sensorerna och termostaten finns.
4. Kör `brewassistant.gf30_clear_preflight`.
5. Registrera manuell temperatur via `brewassistant.gf30_record_manual_temperature`; använd gärna `phase: baseline`.
6. Upprepa under `cooling` och `recovery`.
7. Läs GF30 preflight/rate/safe-point-sensorerna som diagnostik.

Ingen av dessa steg ska starta GF30-pump, frys eller ändra temperaturmål.

## Test- och releasegrind

Den här filen är release-underlag, inte testbevis.

1. Kontrollera på `dev` att manifestet är `0.2.0-beta.15`, GF30-koden, testerna och denna releasefil finns.
2. Öppna separat PR `dev → beta`, granska hela diffen och merge med **Create a merge commit**. Ta inte bort `dev`.
3. Notera exakt resulterande `beta`-merge-SHA.
4. Kräv gröna CI-tester på Python 3.11/3.12/3.13, HACS, Hassfest och isolerad HA/RCL-smoke på **just den SHA:n**. Äldre gröna körningar räknas inte.
5. Läs `manifest.json`, GF30 backend, tjänster, sensorer och denna fil från samma beta-SHA.
6. Skapa ny oflyttad tagg `v0.2.0-beta.15` på exakt beta-merge-SHA.
7. Publicera GitHub **Pre-release** med denna releaseidentitet. Markera inte stable/latest.
8. Efter publicering: verifiera att taggens commit = verifierad beta-SHA och att taggens manifest = `0.2.0-beta.15`.

Vid varje mismatch eller röd check: publicera inte/stoppa test, rätta på `dev` och använd därefter en ny promotion.

## Kända gränser

- Ingen live GF30 hardware/controller-validering finns ännu.
- Ingen Grainfather target-write är implementerad i beta.15.
- Ingen BA-pumpstyrning eller direkt freezer-switching finns.
- Coolant-medium, fryspunkt, kompressorintervall och fysisk fail-OFF är ännu inte validerade.
- Dual-sensor safe-point är diagnostisk redundans, inte oberoende fysisk säkerhetsfunktion.
- Befintliga BrewZilla/beta.14 säkerhetsbegränsningar och fältacceptans påverkas inte av denna GF30-release.

**Versionsidentitet:** release-titel `BrewAssistant 2026_09-24 — GF30 read-only beta` · tagg `v0.2.0-beta.15` · manifest `0.2.0-beta.15` · taggens commit = verifierad beta-mergecommit. `main` förblir orörd.
