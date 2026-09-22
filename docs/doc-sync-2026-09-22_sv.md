# BrewAssistant – dokumentationssynk 22 september 2026

## Verifierat versions- och branchläge

- Publicerad, oförändrad prerelease: [`v0.2.0-beta.14`](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14), tagg på `1a956c04044df870e005392b6bfe946097b9d440`. Taggen skrivs aldrig om.
- [`PR #223`](https://github.com/Jocke1970/brewassistant-beta/pull/223) mergade `beta` till `dev` den 22 september med merge-commit `2d8f2c0fdb1d609e39ca71d24c0f581c653c4c7e`. Därmed finns beta.14-koden även i `dev`, och befintliga HLT SIM-1-/dokumentationsändringar behölls. Tidigare dokument från 20 september om att `dev` saknar beta.14 är historiska, inte längre aktuella.
- Dokumentationssynken förs separat till `dev` och därefter `beta` med PR, utan ny releasetagg, ny hårdvarukod eller promotion till `main`. `main` ska fortsätta vara stabil/fältaccepterad. GitHub-merge uppdaterar inte användarens HA-installation.
- CI/HACS/Hassfest på ursprunglig beta.14-release och isolerad HA/RCL-smoke är inte fysisk acceptans eller nya testresultat för senare branchcommits.

## Fynd från riktig Home Assistant 20–22 september

- Användaren har installerat beta.14 och hittade observationsswitchen under Home Assistants autogenererade svenska entitets-ID `switch.brewassistant_endast_observation_brewzilla_styrs_lokalt`, inte det avsedda `switch.brewassistant_brewzilla_observe_only`. Omdöp via HA:s entitetsinställningar, eller anpassa lokalt YAML-kort efter verkligt ID. Automatiserad kanonisk ID-migrering är **inte implementerad eller testad** i beta.14 och är en framtida kodfråga. Redigera aldrig `.storage` manuellt.
- I inskickat orchestration-snapshot var `orchestration_mode: observe-only`, `observe_only_enabled: true`, `observe_only_effective: true`, `hot_side_actuator_writes_allowed: false` och `has_pending_action: false`. Detta stöder att BA:s ordinarie skrivspärr var aktiv i HA, men verifierar inte enhetsutgångarna eller frånvaro av alla fysiska kommandon.
- Samma snapshot hade `connected: false`, `connection_state: Disconnected`, `brewday_state: aborted`, `runtime_source: None`, och `hot_side_outputs_physically_off_verified: false`. Inga värme-/pumpresultat får betraktas som fysisk bekräftelse från frånkopplad RCL.
- Operatören använde `button.brewassistant_rearm_brewday_control` och rapporterade sedan `operator_control_state: armed`, `operator_abort_active: false`, `runtime_state: idle`, `source: None`, `operator_rearmed_at: 2026-09-22T20:13:41.147396+00:00`. Detta återställer ABORT-latchen, **inte** observe-only och **inte** valet av bryggkälla.
- Försök att slå AV observe-only medan ABORT/källa var ogiltig nekades. Den faktiska koden validerar källbehörighet (RAPT-controller eller villkorsstyrd Manual Brewday), ABORT och sex färska RCL-readbacks vid switch-AV; den återgår till PÅ vid misslyckande. Förväxla inte separat `button.brewassistant_rearm_brewday_control` efter ABORT med kompatibilitetstjänsten `brewassistant.brewzilla_rearm_after_observe`: vanlig observe-only-AV är en enda atomisk switchåtgärd.

## Säker rutin till nästa vattenprov

1. Kontrollera vattennivå, maskinens faktiska värmare/pump/huvudström och tillgänglig lokal fysisk avstängning. Endast vatten, operatör närvarande.
2. Kontrollera aktiv BA beta.14 och rätt RCL-fork/version; se till att RCL återansluter och telemetrin är färsk. En `Disconnected`-status innebär stopp för försök att ge BA automatisk skrivbehörighet.
3. Låt observe-only vara **PÅ** för manuellt vattenprov; välj/förbered Manual Brewday i användargränssnittet och verifiera att RAPT-profilen är uttryckligen stoppad innan några direkta RCL-reglage visas/används.
4. Kontrollera `observe_only_effective: true`, `hot_side_actuator_writes_allowed: false` och att BA inte skriver tillbaka manuellt ändrade target/heat/pump-värden. BA:s äldre Manual-setpoints skickas inte i observe-only; det separata observationskortet använder uttryckliga direkta RCL-anrop som ligger utanför BA-spärren.
5. ABORT är ett separat nödkommando även under read-only. Det försöker STOP/OFF/0 men skickat HA-anrop eller visat OFF är inte fysisk verifikation. Efter fysisk kontroll: `button.press` på `button.brewassistant_rearm_brewday_control`; verifiera `operator_abort_active: false`. Ingen automatisk styrrätt uppstår av detta.
6. Om automatisk BA-kontroll senare provas: välj behörig källa, säkerställ sex färska readbacks, att ABORT är återställd och gör explicit switch-AV under uppsikt. Vid nekat försök förblir read-only PÅ. Testa fysiska utgångar och loggar innan någon acceptans.

## Återstående uppgifter

- Fixa och regressionstesta stabilt entitets-ID/migrering för observationsswitchen i **en ny kodrelease**, inte genom att ändra beta.14-taggen.
- Fysisk vattenacceptans, fullständig HA/RCL-end-to-end, fysiskt kvitterat ABORT, loggad frånvaro av oväntade BA-skrivningar och kontroll av dashboards återstår. Ingen malt-/obevakad acceptans.
- HLT SIM-1 är fortsatt en virtuell läskonsument. Ramp/`Heat Strike`-beredskapskontrakt och fysisk elsäkerhet är separat oavslutat arbete. Se [roadmap](roadmap.md) och [HLT-rapport 20 september](hlt-sim1-field-validation-2026-09-20.md).

**Historik:** [projektstatus 20 september](project-status-2026-09-20_sv.md) är ett daterat ögonblick, inte den senaste branchmatrisen. [Issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) hålls öppen tills fysisk acceptans.