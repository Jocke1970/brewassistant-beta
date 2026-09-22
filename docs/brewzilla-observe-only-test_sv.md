# BrewZilla – endast observation och lokal styrning: testkontrakt

**Uppdaterat 2026-09-22.** Funktionen finns i publicerad [v0.2.0-beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14), men fysisk acceptans återstår. Senaste [fältfynd och branchstatus](doc-sync-2026-09-22_sv.md). Använd endast vatten, närvarande operatör och möjlighet till lokal fysisk avstängning.

## Vad read-only faktiskt gör

`switch.brewassistant_brewzilla_observe_only` **PÅ** blockerar BA:s ordinarie BrewZilla/RAPT-skrivningar, inklusive mål, värmare, pump, nyttjandegrad och ordinarie OFF/0. BA kan fortsätta läsa/logga och generera passiva råd. Switchen stoppar **inte** befintlig fysisk värme/pump, RAPT-profil, BrewZillas lokala reglage eller direkta RCL-anrop från andra HA-kort. Learning APPLY får inte orsaka BA-output i observerande läge. Separat operatörs-ABORT är **alltid tillgänglig** och försöker skicka profil-STOP och OFF/0; kontrollera alltid faktisk fysisk respons.

Efter installation/start ska BA vara read-only PÅ (fail-closed). Beta.14:s HA-entitetsregistrering har i verklig installation skapat `switch.brewassistant_endast_observation_brewzilla_styrs_lokalt` från det svenska visningsnamnet. Omdöp i **HA:s entitetsinställningar** till det kanoniska ID:t ovan, eller anpassa lokalt kort efter faktiskt registrerat ID; ändra inte `.storage` manuellt. En framtida kodfix för stabil ID-migrering återstår.

## Två skilda återställningar

**1. Operatörs-ABORT:** efter kontroll av fysiska utgångar används `button.press` på `button.brewassistant_rearm_brewday_control` eller kortets **ÅTERAKTIVERA EFTER ABORT**. Verifiera `sensor.brewassistant_brewday_operator_control_state`: `operator_control_state: armed` och `operator_abort_active: false`. Detta ger inte automatiskt BA rätt att skriva och aktiverar inte en bryggkälla.

**2. Read-only AV:** själva switch-AV validerar atomiskt aktuell behörig bryggkälla, frånvaro av ABORT och sex färska (max 90 s) BrewZilla-readbacks: temperatur, temperaturmål, värmarswitch, pumpswitch, heat utilization och pump utilization. Antingen behörig RAPT-kontroller eller villkorsstyrd Manual Brewday med bekräftad RAPT-STOP krävs. Okänd källa (`source: None`), `Disconnected`/gammal telemetri eller aktiv ABORT ska ge nekad övergång med switchen kvar PÅ. En äldre kompatibilitetstjänst `brewassistant.brewzilla_rearm_after_observe` finns, men **ingen separat tjänst krävs vid normal switch-AV**. Inga gamla väntande åtgärder får återspelas. Vid HA-omstart återgår switchen till PÅ.

## Verifierat hittills, inte fysisk PASS

Beta.14:s automatiska releasegrindar rapporterade 387 tester och CI på Python 3.11–3.13, HACS/Hassfest samt isolerad HA/RCL-smoke. Det isolerade provet använder simulerade servicehanterare, inte riktiga molnkommandon eller fysiska utgångar. Statisk Lovelace-kontroll är inte ett klicktest av användarens dashboard.

I användarens HA rapporterade orchestration-sensorn `observe_only_enabled: true`, `observe_only_effective: true`, `hot_side_actuator_writes_allowed: false`, inga väntande åtgärder och `hot_side_outputs_physically_off_verified: false`. RCL rapporterade samtidigt `Disconnected`; detta är inte bevis för fysisk avstängning. Separat ABORT återställdes 2026-09-22 (`operator_abort_active: false`, `operator_control_state: armed`); källan var därefter fortfarande `None`, runtime `idle`. Inget praktiskt beta.14-vattenprov är godkänt.

## Acceptansprov under uppsikt

1. Bekräfta installerad tagg/manifest beta.14 och RCL-fork, backup, rätt vattennivå, fysisk avstängningsmöjlighet och faktiska inaktiva utgångar. Kontrollera att inga gamla RAPT-profiler körs.
2. Verifiera switch PÅ och `sensor.brewassistant_brewzilla_orchestration_mode` med `observe_only_effective: true` och `hot_side_actuator_writes_allowed: false`. Dessa beskriver BA-behörighet, inte fysisk OFF.
3. Montera manuellt `dashboard/cards/brewzilla_observe_only_sv.yaml` bredvid Manual Brewday-kortet. Välj/förbered Manual Brewday och verifiera uttryckligt profil-STOP innan direkt-RCL-reglagen visas/används. Direkt RCL ligger utanför BA-spärren; de äldre BA-ägda Manual-setpoints transporteras inte i read-only.
4. Under kontrollerad vattenkörning, justera lokalt/direkt RCL temperaturmål och nyttjandegrad, logga readback samt verifiera att BA inte skriver tillbaka. Kontrollera passiv audit, Flight Recorder, learning och energi. Tyst logg ensam bevisar inte avsaknad av skrivning.
5. Testa ABORT separat med möjlighet till fysisk strömbrytning; kontrollera faktisk värmare, pump, huvudström och effekt oberoende av HA-ACK. Återställ ABORT med separat knapp först efter kontroll.
6. Om automatisk BA-styrning ska provas: välj behörig källa, verifiera sex färska readbacks och testa explicit switch-AV under uppsikt. Kontrollera att gammal plan inte återspelas, och att ogiltig källa/telemetri nekar kontroll. Gör även säkra omstarts-/reloadtest och följ upp CFC/handoff samt övriga BA-vägar.
7. Avbryt om BA återställer manuella val, utgångar inte stämmer fysiskt, telemetri är gammal eller någon okänd skrivväg upptäcks. Dokumentera nytt fälttest och uppdatera [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) först med faktiska resultat.

**Ej godkänt:** fysisk end-to-end, utgångsoff-verifikation, heltäckt UI/klicktest, loggad molntrafik, omstarter och obevakad användning. Ändra inte den publicerade beta.14-taggen för att rätta dessa dokument.