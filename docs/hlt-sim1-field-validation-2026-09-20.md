# HLT SIM-1 – fältlogg och överlämning, 2026-09-20

**Status:** Delrapport från ett pågående, enbart virtuellt HLT-prov; **inte** en accepterad full bryggdag, kodrättning eller fysisk HLT-validering. Föregående [19 september-rapport](hlt-sim1-field-validation-2026-09-19.md) är separat historik och ändras inte. Den här rapporten bygger på den uppladdade JSONL-filen `Obekräftade 401935.crdownload`, inte en verifierad slutlogg eller direkt åtkomst till operatörens HA-installation.

## Underlag och verifierade observationer

- 44 giltiga JSONL-poster, schema 2, **2026-09-20 07:21:56–07:43:27 UTC** (09:21:56–09:43:27 svensk sommartid). Samtliga poster har `stage=Mash`, källa `RAPT BrewZilla Profile`: 28 poster med `step=Heat Strike`, 10 med `Mash In`, 6 med `Malt Rest`.
- Status: 35 × `WAITING_FOR_POWER`, 5 × `HEATING`, 4 × `YIELDING`. Händelser: 4 × `virtual_hlt_on`, 4 × `virtual_hlt_off_requested`, 4 × `virtual_hlt_off_confirmed` och 3 × `simulation_budget_conflict`.
- Alla fem `HEATING`-poster inträffade under **`Heat Strike`**, omkring 07:28:57–07:34:57 UTC. Observerad BZ-effekt var 13,8–14,0 W, fysisk enhetstarget och normaliserad Brewday-target 40,0 °C, uppmätt BZ-temperatur ungefär 39,67–40,46 °C. Simulatorn rapporterade `cruise_power_opportunity_simulated` och tilldelade HLT virtuell effekt.
- Tre **hypotetiska** scenariokonflikter uppstod i `YIELDING`: 1 922,7 + 1 800 = 3 722,7 W; 1 898 + 1 800 = 3 698 W; 1 902,4 + 1 800 = 3 702,4 W, jämfört med scenariobudget 2 500 W. Reservationen kvarstår virtuellt under OFF-övergången. Dessa siffror är **inte uppmätt fysisk samtidighet**.
- `physical_writes=false` och `bz_power_cap_w=null` i **samtliga 44 loggrader**. De är logguppgifter, inte bevis för att inga andra integrationer eller fysiska enheter gjorde något. HLT var inte fysiskt inkopplad för BA-styrning i SIM-1.
- Den publicerade virtuella HA-mottagaren i loggen är `none` (39 poster) eller `hlt` (5 poster). Under fyra av fem simulerade ON-poster är den publicerade sensorn ännu `none`; kort och runtime kan alltså ligga olika uppdateringscykler. Inget `unknown`-värde finns i just detta utdrag. Detta **förklarar inte ensamt** den tidigare skärmbilden med `Okänt`: verifiera installerad YAML, exakt entity-ID inklusive eventuellt suffix och HA:s faktiska tillstånd vid tidpunkten.

## Identifierad avvikelse – ej rättad eller accepterad

HLT:s [aktuella runtime på `dev`](../custom_components/brewassistant/hlt/runtime.py) tillåter `heat strike` i sin förberedande **stage-allowlist**, medan `_RAMP_STEP_NAMES` endast listar `mash out` och `heat strike water`. Prefixkontrollen träffar `Ramp to ...`, inte det här observerade **steget** `Heat Strike`. Därmed kan matchande temperatur och kortvarigt låg BZ-effekt ge en virtuell HLT-grant under detta steg. Kodjämförelsen förklarar hur de fem grants kunde uppstå; det återstår att definiera om/precis när Brewday faktiskt begär HLT-förvärmning i varje processkälla.

**Ändra inte styrpolicy baserat enbart på låg effekt eller på ett tvetydigt stegnamn.** Nästa kodarbete ska först fastslå explicit HLT-behov/beredskap från Brewday och en fail-closed ramp-veto för `Heat Strike` när det betyder uppvärmning. Lägg sedan till källspecifika/regressionsfall för RAPT, BrewTracker och Manual samt omtest med JSONL. Varken fysisk HLT eller effektbegränsning av BZ får aktiveras som del av detta.

## Separata acceptans- och UI-punkter

1. **HLT/Brewday-kontrakt (blockerande):** skilj `Mash`-stage, processens exakta `step`, rampintention och positiv HLT-beredskap åt. Dokumentera exakt aktiveringspunkt; `stage=Mash` ensamt får inte tolkas som ett bekräftat startkommando.
2. **Diagnostik:** schema-2-fälten `bz_temperature_ha_c`, `bz_device_target_ha_c`, `bz_brewday_target_ha_c` och deras ålder samt `hlt_virtual_recipient_ha_state` gör nästa prov mer förklarbart. Kontrollera sensorfärskhet och korrelera mot riktiga BZ-mätningar; saknat värde är inte 0.
3. **UI:** kontrollera `sensor.brewassistant_hlt_virtual_energy_recipient` i HA. `none` ska visas `Ingen`; `hlt` ska visas `HLT (virtuell)`. En eftersläpning mellan runtime och sensor får inte maskeras som fysisk säkerhet. Läs [kortguiden](hlt-dashboard-card.md).
4. **Fältvalidering:** samla avslutande logg och granska ramp → väntan → avsedd cruise/explicit HLT-behov → virtuell ON → BZ-återtag/yield/off. Den här filen slutar 09:43 och styrker inte ett helt lyckat förlopp.
5. **Fysisk gräns:** 30 s HA-loop och 2 500 W-scenario är **inte** ett elsäkerhetsinterlock. All fysisk HLT kräver separat snabb oberoende fail-OFF, fysisk OFF-readback och dokumenterat elektriskt/torrkokningsskydd. BZ stryps aldrig för HLT.

**Implementeringsstatus vid synken 2026-09-20:** HLT:s `Heat Strike`-rampveto och ett explicit källaoberoende HLT-startkontrakt är **inte implementerade** i `dev`. Rapporten är dokumentation, inte kodfix. Jämför alltid exakt installerad/taggad version med `dev` innan ett nytt test. [Aktuell projektstatus](project-status-2026-09-20_sv.md).