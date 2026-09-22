# Brewday backend – källor, processtid och HLT-överlämning

**Dokumentationscheckpoint: 2026-09-20, `dev`.** Brewday är den normaliserade processmodellen, **inte** hårdvarubackend för BrewZilla. Fysisk target/heat/pump-aktuation ligger i [`../brewzilla/`](../brewzilla/) och beror på vald kod-/releaseversion. Läs [projektstatus](../../../docs/project-status-2026-09-20_sv.md) och [roadmap](../../../docs/roadmap.md) först: publicerad beta.14 har observe-only, ABORT och separata Manual-direktreglage som fortfarande **saknas i `dev`**. Detta dokument beskriver Brewday-koden på `dev`, inte en uppdaterad HA-installation eller en godkänd fysisk beta.14.

## Ansvar och gränser

`brewday` normaliserar Brewfather Brew Tracker, RAPT BrewZilla-profil och Python-ägd Manual Brewday till ett gemensamt snapshot. Det skiljer receptkälla, runtime-/timerägare och rätt att påverka fysisk utrustning; hanterar steg/tid, operatörens ABORT-latch, refresh-/source-policy, processfaser, additionspåminnelser, Audit/Event Log och Brewday Flight Recorder. Det exponerar läsbar processintention för fristående **read-only-consumers** såsom HLT SIM-1. Brewday ska aldrig bli beroende av att HLT finns, aldrig tyst styra en fysisk HLT och aldrig ge BZ ett effekt-cap för HLT:s skull.

### Källprioritet på `dev`

```text
Operator ABORT-latch -> explicit aborted / ingen ägande runtime
aktiv/osäker/stoppad RAPT-handoff -> RAPT processkälla
aktiv Brewfather Brew Tracker -> Brewfather runtime
aktiv Manual Brewday -> Python Manual runtime
annars -> normaliserad idle/core snapshot
```

Aktiv RAPT paus-ar aktiv Manual för överlämning. Efter faktiskt RAPT-ägarskap ska signalförlust eller stoppguard inte obemärkt byta till Brewfather. `Brewing` i bred BF-batchfas eller generellt `active: true` bevisar inte BrewTracker-start; positiv tracker-start/progress krävs. När tracker väl startat legitimt kan det behålla ägarskap under vanliga pauser. Se [`brewday-execution-modes.md`](../../../docs/brewday-execution-modes.md).

### Brewfather PAUS och fysisk target

I historiskt BF/BT supervised-läge äger Brewfather tracker/timer, BA tolkar checkpoint och har fysisk target-/heat-/pump-policy via separat BrewZilla-backend och dess spärrar. En framtida BA-ägd importerad receptplan kan låta BF vara receptkälla men lägga timerägandet på BA; det är ännu framtida arbete. En verifierad PAUS/0-min-kontroll 11/9 visade frusen tracker-status/step/progress/tid tills operatören återupptar. BA ska endast arbeta mot **nuvarande** target under PAUS, aldrig förvärma `next_step`; fältfynd 40→45→55 °C kräver separat fysisk återvalidering. Normaliserad tid/step är inte bevis på uppnådd fysisk temperatur.

### Operatörens ABORT och BA observe-only

`brewday_operator_abort.py` innehåller en persistent, högprioriterad ägarskapslatch som gör runtime icke-ägande och tar bort positiv väntande intention. Fysisk ABORT-väg är en **separat** fråga: varken latch, HA-serviceanrop eller `recovery_required` garanterar faktisk fysisk OFF. Publicerad **beta.14** har separat ABORT-nödlane och `switch.brewassistant_brewzilla_observe_only`, men dessa beta.14-funktioner är **inte återförda till `dev`** av denna doc-sync. Jämför verklig installationsversion/HA-readbacks och [taggade beta.14-instruktioner](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/beta14-prerelease-notes_sv.md); gör inga antaganden om switchens existens i äldre kod.

## Manual och stage-normalisering

`manual_brewday_runtime.py` är UI-oberoende med `idle`, `prepared`, `running`, `paused`, `awaiting_confirm`, `completed`; store/adapter håller state och normaliserar en Setup → Mash → Sparge → Boil → Whirlpool → Chill/Transfer-plan med steg, mål, tider och bekräftelser. Detta är en riktig Python-runtime, inte YAML-simulering. `brewday_runtime_core.py` normaliserar BF/core, `brewday_runtime.py` arbiterar vald källa, `brewday_ramp_target_gate.py` bevakar fysisk ramp, och `brewday_stage_engine.py` är **read-only** presentation, inte ett HLT- eller Cooling-kommando.

```text
Idle -> Prepare -> Heating Strike / Strike Water -> Mash In -> Mash
-> Mash Out -> Heating To Boil -> Boiling / Hop Addition -> Whirlpool
-> Wort Cooling -> Pitch Ready / Transfer -> Cleaning -> Completed
```

Stage-enginens namn, runtime-snapshotets `stage` och exakta källsteget `step` är **inte automatiskt ekvivalenta**. En HLT-policy som bara tittar på `stage=Mash` har inte därigenom fått en positiv begäran om lakvattenuppvärmning.

## HLT SIM-1 – verifierat kontrakt och öppet fynd 20/9

HLT SIM-1 från [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212) kör en egen avlastningsbar **30 s läsande simulator** via [`../hlt/`](../hlt/). Den läser `build_brewday_runtime_snapshot(hass)` (`source`, `stage`, `step`, `target_temperature`, runtime, ABORT), aktiv Brewday Audit och effektiv `sparge_water_l` från BrewZilla Batch Context. Den styr aldrig fysisk HLT, skapar ingen BZ-capping och lägger inte till HLT-hårdvaruservice.

Nuvarande konservativa HLT-policy på `dev` kräver aktiv icke-terminal session, positiv känd sparge-volym, stage ur `Setup`, `Heat strike`, `Heat strike water`, `Mash`, `Mash in`, `Mash out`, `Sparge`, färsk fysisk BZ-watt/temperatur, giltig heat utilization, överensstämmande target, observerad cruise utan explicit ramptext och utrymme för hela virtuella HLT-värmaren i **scenariot**. Noll lakvatten = No Sparge; okänd data fail-closed. `number.*`-setpoints behöver inte uppdateras kontinuerligt för att vara giltiga, men fysisk telemetri måste vara färsk.

**19/9-historik:** fysisk BZ-watt omkring 2,3 kW och 11,38 L sparge-volym verifierades; ett falskt virtuellt grant under `Ramp to 72°C` upptäcktes och parsern kompletterades i `dev`, med kodtester. [Daterad rapport](../../../docs/hlt-sim1-field-validation-2026-09-19.md).

**20/9-nytt fältutdrag, ännu ÖPPET:** [44 JSONL-poster](../../../docs/hlt-sim1-field-validation-2026-09-20.md), fem virtuella HLT-värmeprover under `step=Heat Strike`, tre *simulerade* effektkonflikter, ingen fysisk HLT-skrivning i de dokumenterade raderna. Runtime tillåter stage `heat strike` men `_RAMP_STEP_NAMES` fångar **inte** det exakta RAPT-steget `Heat Strike`, och explicit källaoberoende positiv HLT-beredskap saknas. Detta kan ge simulerad HLT-grant när BZ tillfälligt når 40 °C och drar ~14 W. **Ingen kodfix eller accepterad hel fältkörning finns ännu.**

**Överlämning till nästa Brewday/HLT-kodarbete:** definiera varifrån/vid vilken tidpunkt HLT-behovet kommer, tydlig positiv readiness och ramp-intent för RAPT, BT och Manual; skilj stage/step från verklig target/readback. Besluta semantik för `Heat Strike`, `Heat Strike Water`, Mash In, Mash Out och okänt steg. Därefter inför separat kodfix och regressionsfall i rätt branch, full read-only provkedja ramp → vänta → avsedd virtuell ON → BZ återtar/yield/OFF. BZ har alltid absolut ostrypt prioritet. HLT:s 30 s-policy eller 2 500 W-scenario är **aldrig** elektrisk safety/interlock; fysisk HLT kräver separat oberoende fail-OFF/hårdvarugranskning. Se [HLT README](../hlt/README.md), [sensoravtal](../../../docs/hlt-dashboard-backend.md) och [kortguide](../../../docs/hlt-dashboard-card.md).

## Tider, Audit och JSONL

`brewday_physical_timing.py` och `brewday_physical_timing_phase_patch.py` skiljer uppmätt fysisk fas-/targettid från externa schema-/PAUS-klockor. En eventuell framtida BA-ägd timer för importerade recept ska starta hold först efter vald fysisk sensors temperaturkriterium. Stage-engine och timing ger inte fysisk energibehörighet.

`brewday_audit.py` lagrar kompakta events via HA Storage `brewassistant_brewday_audit_log` (schema 2, högst 250 events) och följer ownership, status, plan/åtgärd, säkerhet och freshness. `brewday_audit_autostart.py` och session boundary/continuity bevarar sessioner genom BF pre-start och legitima stegbyte. HLT har separat JSONL per Brewday-session under `/config/brewassistant/logs/hlt-sim-<session-hash>.jsonl`, med aktuell serversökväg i `sensor.brewassistant_hlt_trace_path` (HA-suffix möjligt). JSONL har uppmätta kontra virtuella watt, temperatur/källa, stage/step och från 19/9 på dev extra BZ-target/temperatur/ålder och publicerad virtuell mottagare. HLT-tider/Wh i minnet nollställs vid HA-omstart; filer på disk kvarstår. Dashboard kan släpa en coordinator-tick och kan inte ersätta Audit/bevis från fysisk hardware.

## Nyckelfiler och tjänster

| Fil/grupp | Roll |
| --- | --- |
| `manual_brewday_runtime.py`, `manual_brewday_store.py`, `manual_brewday_adapter.py` | Manual-plan, state/timer och normalisering |
| `rapt_profile_runtime.py`, `brewfather_ownership.py` | RAPT-profilkällan och faktisk BT-start/ägarskap |
| `brewday_operator_abort.py` | Persistent operatörs-ABORT-latch, separat från fysisk off-verifikation |
| `brewday_refresh.py`, `brewday_refresh_policy.py` | Källsäker BF-refresh |
| `brewday_addition_alerts.py`, `brewday_*_sensor.py` | Alerts och read-only HA-presentation |
| `brewday_audit_autostart.py`, `brewday_audit_session_boundary.py`, `brewday_audit_session_continuity.py` | Recorder lifecycle, sessionsgräns och kontinuitet |

Integrationens serviceyta omfattar `brewassistant.force_brewfather_refresh`, `brewday_audit_start`, `brewday_audit_stop`, `brewday_audit_clear`, `brewday_audit_snapshot` och Manual Brewday `manual_brewday_prepare`, `start`, `pause`, `next`, `start_mash`, `start_boil`, `start_whirlpool`, `start_cooling`, `finish`, `reset` under `brewassistant.`. HLT SIM-1 lägger **inte** till en offentlig aktuatortjänst. Exakta HA-entiteter registreras i integrationens plattformar, inte i denna dokumentation.

**Ändra inte oavsiktligt:** ägarskapsordning, operatörens separata ABORT, BF PAUS-current-target-gate, Manual Python-runtime, Audit-kontinuitet, HLT:s read-only-gräns, BZ-prioritet eller andra modulers SG/CFC-kod i samma branchstädning. En doc-sync är inte release eller fysisk kontrollacceptans.
