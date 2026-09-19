# Fermentation mode selection and SG-driven fermentation: contract and implementation status

Status: **pure SG decision engine and tests only** on `dev`; the two-mode selector, editable controls, persistence, active arbitration, and cold-crash confirmation UI are **not implemented yet**. Keep the installed fermentation test on its existing recipe schedule; do not promote to `beta` or `main` without explicit approval and runtime validation.

## Two explicit, per-batch modes

- `recipe_schedule` (UI: **Dagar / Brewfather-schema**) is the backward-compatible default. Brewfather provides read-only recipe fermentation steps, temperatures, `actualTime`, and ramps. BrewAssistant interprets them; the fork never owns BA-specific control.
- `sg_control` (UI: **SG-styrd**) is opt-in for each batch and uses only validated new Pill observations for stage progression. The Brewfather schedule remains visible as a *plan*, but must not alter the active SG target or trigger a date-based cold crash.
- Expose the **active mode**, active target source, selected batch identity, latest valid SG/timestamp and reason for holding a stage in the dashboard. Switching modes requires an explicit operator action and must never silently enable the chamber supervisor.
- On loss of Pill readings, **hold the last confirmed SG target** and notify/show stale data. Never silently fall back to recipe dates, jump stages or start a cold crash. The operator may explicitly switch to day mode or continue manually after checking the fermentation.
- Persist selected mode and its parameters **per batch**, not as global inputs that overwrite another batch. On first load, make a proposed SG profile editable before activation; do not auto-enable SG mode just because a recipe has fermentation steps.

## UI: editable configuration before SG mode can be enabled

Expose one coherent configuration panel on the fermentation/batch view (not hardcoded Julöl parameters). Use decimal SG values, not gravity points or Brix. Pre-fill known recipe temperatures/FG where available, clearly label them as imported defaults; Brewfather does not provide SG trigger thresholds or a stable-FG verification period. BA owns user edits and must not overwrite them on subsequent recipe refreshes.

| UI field | Example/default for Julöl 2026 V2 | Notes |
| --- | --- | --- |
| Styrningsläge | Dagar / Brewfather-schema | Explicit switch to SG-styrd; day mode retained |
| Initial temperatur | 18.0 °C | First SG stage |
| SG-gräns steg 2 | 1.035 | Only validated fresh Pill readings count |
| Temperatur steg 2 | 19.0 °C | Target when threshold confirmed |
| Temperaturändring steg 2 | 4 hours, editable | Optional gradual rise; zero only when explicitly requested; never use old recipe ramp during SG mode |
| SG-gräns steg 3 | 1.020 | Must be below the preceding threshold |
| Temperatur steg 3 | 20.5 °C | Final fermentation target |
| Temperaturändring steg 3 | 6 hours, editable | Optional gradual rise; configurable per batch |
| Förväntat FG | 1.014 | User-editable; imported recipe FG may be a suggested starting value |
| Stabil SG i minst | 72 hours | Explicitly configurable 48–72 hours |
| Stabilitetstolerans | 0.001 SG | User-editable within validated safe bounds |
| Cold-crash-mål | 2.0 °C | Proposal only until independent operator confirmation |

Hours must have distinct labels: **ramp duration per temperature step** versus **hours of stable FG**. Day mode uses Brewfather schedule durations; SG mode does not require the user to reproduce Brewfather's date plan. Show the calculated ramp/hold status and the last confirmed stage.

Validate all entered settings as one profile before applying (SG thresholds must descend, known OG/FG must be consistent where available, temperatures and durations plausible, and stable-hours between 48 and 72). Apply configuration changes atomically; warn/require explicit confirmation before changing an already running profile. A profile edit must not reset the stage latch or retroactively skip stages. Manual SG measurement entry can remain available as a tracking observation, but must not impersonate a Pill reading or silently advance the automated SG stage.

## Initial target profile for Julöl 2026 V2

| Latched stage | Trigger | Temperature |
| --- | --- | --- |
| 0: primary | initial | 18.0 °C |
| 1: rise | two credible Pill readings at SG <= 1.035 | 19.0 °C |
| 2: finish | two credible Pill readings at SG <= 1.020 | 20.5 °C |

For each threshold, require two distinct fresh measurements at least five minutes apart. Re-polls of the same observation do not count; confirmation expires after two hours. A stage must never regress or skip from SG noise. Persist confirmed stage, pending confirmation, source timestamp and batch identity across Home Assistant restarts. No default-on migration of an active session.

## Validity and source boundaries

The existing pure engine in `sg_control_rules.py` currently has **hardcoded example thresholds and targets**, which must be parameterized from the validated per-batch UI profile before it can be connected to runtime. It rejects readings older than 20 minutes, more than one minute in the future, outside SG 0.980–1.150, or above a known OG by more than 0.005. Integration still needs to prove that accepted readings come from the configured Pill and persist actual Pill observation history. An invalid/stale source holds the last confirmed target and explains why.

`fermentation_tracking` owns observations, profile, mode arbitration, and target recommendation. `fermentation_chamber` consumes the selected recommended beer target behind the existing supervised-apply boundary. No new direct heater, compressor, or climate calls. Neither mode nor profile editing switches climate supervisor ON.

## FG and cold crash

Default stable FG verification: 72 hours (48–72 explicitly configurable), SG range <= 0.001, at least six observations, no gap > 12 hours, fresh newest observation, and newest SG <= expected FG plus configurable tolerance (default 0.002). Insufficient history or absent FG is NOT READY; current SG alone never proves stability. Persist actual automatic Pill history.

Readiness is **advisory only**. Notify once when stable and ask for explicit user confirmation. Before starting cooling, separately require operator acknowledgement that protection against air/oxygen suck-back has been arranged; an ordinary airlock is not sufficient evidence. The actual cold-crash start must remain behind existing supervised control. Neither days nor SG can start cold crash automatically.

## Integration work still required

1. Parameterize pure SG rules from validated, per-batch UI fields; add tests for profile validation, stage latch and editable times/thresholds.
2. Persist selected mode, batch-scoped settings, confirmed stage, pending confirmation, and Pill history in Home Assistant Storage; reset only on explicitly starting a new batch.
3. Build select/number controls and a complete fermentation dashboard configuration panel; import sensible recipe defaults but never overwrite explicit user edits.
4. Process only new authenticated/configured Pill readings in a coordinator/event flow, not as a side effect of a sensor property. Add an explicit mode arbitration to the tracking snapshot; keep `recipe_schedule` the default.
5. Add readiness notification and separate suck-back-protection/starting confirmation. Add persistence, restart, source-staleness, mode-switch and supervised-apply tests; test on a real batch before promotion.

Current SG code remains an isolated pure decision engine and tests only. The installed fermentation control stays on the existing recipe schedule until a new implementation is deployed and explicitly opted in.