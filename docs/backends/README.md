# BrewAssistant Backend Documentation

Status: active development / documentation index  
Last HLT sync: 2026-09-19  
GF30 DIY thermal/learning and Brewfather export designs captured: 2026-09-22 (planned, not implemented)

Canonical short-form documentation lives beside each backend under `custom_components/brewassistant/<backend>/README.md`. These code-local READMEs describe the *implemented* ownership/control contract. This `docs/backends/` directory remains useful for deeper architecture notes, roadmaps and field evidence. Historical documents must not be retroactively rewritten to claim later fixes were already physically tested.

## Canonical backend READMEs

| Area | Current README |
| --- | --- |
| Integration/backend map | [`../../custom_components/brewassistant/README.md`](../../custom_components/brewassistant/README.md) |
| Brewday Runtime / Manual / Flight Recorder | [`../../custom_components/brewassistant/brewday/README.md`](../../custom_components/brewassistant/brewday/README.md) |
| BrewZilla hot side | [`../../custom_components/brewassistant/brewzilla/README.md`](../../custom_components/brewassistant/brewzilla/README.md) |
| **HLT SIM-1 (read-only virtual secondary heater)** | [`../../custom_components/brewassistant/hlt/README.md`](../../custom_components/brewassistant/hlt/README.md) |
| Cooling | [`../../custom_components/brewassistant/cooling/README.md`](../../custom_components/brewassistant/cooling/README.md) |
| Fermentation Tracking | [`../../custom_components/brewassistant/fermentation_tracking/README.md`](../../custom_components/brewassistant/fermentation_tracking/README.md) |
| Fermentation Chamber | [`../../custom_components/brewassistant/fermentation_chamber/README.md`](../../custom_components/brewassistant/fermentation_chamber/README.md) |
| Grainfather Fermenter / GF30 preparation | [`../../custom_components/brewassistant/grainfather_fermenter/README.md`](../../custom_components/brewassistant/grainfather_fermenter/README.md) |
| Fermentation compatibility layer | [`../../custom_components/brewassistant/fermentation/README.md`](../../custom_components/brewassistant/fermentation/README.md) |
| Carbonation | [`../../custom_components/brewassistant/carbonation_backend/README.md`](../../custom_components/brewassistant/carbonation_backend/README.md) |
| Kegerator Climate Supervisor | [`../../custom_components/brewassistant/climate_backend/README.md`](../../custom_components/brewassistant/climate_backend/README.md) |
| Kegerator / fan / legacy guard | [`../../custom_components/brewassistant/kegerator/README.md`](../../custom_components/brewassistant/kegerator/README.md) |
| Module/capability registry | [`../../custom_components/brewassistant/modules/README.md`](../../custom_components/brewassistant/modules/README.md) |
| Shared utilities | [`../../custom_components/brewassistant/shared/README.md`](../../custom_components/brewassistant/shared/README.md) |

## Longer reference documents

| Document | Role |
| --- | --- |
| [`brewzilla-backend.md`](./brewzilla-backend.md) | Detailed BrewZilla design and test baseline. Read alongside the evolving code-local README. |
| [`../brewzilla-control-profile.md`](../brewzilla-control-profile.md) | BrewZilla heat/pump tuning and control-profile history. |
| [`../brewzilla-equipment-learning.md`](../brewzilla-equipment-learning.md) | Passive equipment-learning design/history. |
| [`../hlt-dashboard-backend.md`](../hlt-dashboard-backend.md) | **Current HLT sensor contract:** actual versus virtual watts, temperature provenance, timer fidelity and strict BZ priority. |
| [`../hlt-dashboard-card.md`](../hlt-dashboard-card.md) | High-contrast EN/SV read-only card deployment and test instructions. |
| [`../hlt-sim1-field-validation-2026-09-19.md`](../hlt-sim1-field-validation-2026-09-19.md) | Dated physical BZ-water test/JSONL findings, corrections made afterward and Brewday handoff. Latest HLT field evidence, **not** evidence of final post-fix HA validation. |
| [`cooling-backend.md`](./cooling-backend.md) | Cooling v2 architecture/roadmap; its older implementation-pending sections are historical. |
| [`fermentation-tracking.md`](./fermentation-tracking.md) | Fermentation Tracking MVP details/examples. |
| [`grainfather-fermenter.md`](./grainfather-fermenter.md) | GF30 cloud-adapter preparation, ownership, live-hardware validation gate and future supervised target plan. |
| **[`gf30-thermal-control-learning.md`](./gf30-thermal-control-learning.md)** | **Proposed GF30 DIY cooling architecture:** Pill/internal/frysluft/köldmedium, freezer via generic_thermostat, controller ownership, thermal learning, safety and validation gates. Documentation only; no new control code. |
| **[`gf30-brewfather-upstream.md`](./gf30-brewfather-upstream.md)** | **New planned outbound Brewfather Custom Stream:** 5-minute GF reads, max one POST per 15 minutes/device, existing BF-fork sender, HTTPS/freshness/duplicate guards and temperature-channel mapping. Documentation only; no new sending. |
| [`../roadmap.md`](../roadmap.md) | Current integrated status, remaining acceptance criteria and promotion gates. |

## HLT ownership boundary (2026-09-19)

HLT SIM-1 is a **read-only simulator** running every 30 s from Brewday Audit and normalized BrewZilla Batch Context `sparge_water_l`. BZ has absolute electrical priority; HLT may receive only hypothetical scenario capacity in verified cruise. No BZ heat-utilization caps, no physical HLT service calls and `power_budget_verified=false`. The 2,500 W scenario is not a circuit rating. The September water test found incorrect held-setting freshness and one virtual HLT grant during explicit `Ramp to 72°C`; fixes are integrated on `dev` and require new HA field verification. A 30-second loop cannot be used as an electrical safety interlock. Physical HLT requires independent fast fail-OFF load-shedding, verified OFF feedback, dry-fire protection and circuit inspection. See dated evidence above.

## Grainfather naming boundary

Two distinct concepts remain:

```text
reserved module: grainfather
  future Grainfather hot-side adapter (e.g. G30/G40)

grainfather_fermenter/
  fermenter hardware adapter (initial GF30 Conical Fermenter)
```

Do not reuse the hot-side `grainfather` reservation for GF30 fermenter work. The proposed DIY freezer/reservoir/learning behavior extends `grainfather_fermenter/` as a *separate coolant-control loop* owned physically by `generic_thermostat`, not a new duplicate GF30 provider. The optional Brewfather outbound stream is an independent **logging export**, not a temperature controller: use one transport owner and respect its 15-minute rate limit.

## Documentation pattern

Every backend README should answer: owner and non-owner; source/readback; physical writes (or **none**); safety and confirmation boundary; persisted vs in-memory; public entities/services; authoritative files; compatibility gaps; invariants not to change casually.

Source-of-truth order during active development:

```text
current executable code
  -> code-local backend README
  -> current architecture/index docs
  -> dated roadmap/test/history docs
```

Resolve contradictions rather than allowing concurrent outdated descriptions. Brewday Flight Recorder/JSONL evidence is preferred over dashboard appearance when evaluating behavior. Document actual states, guards, hardware actions and absent readbacks explicitly; keep historical observations separate from fixes verified only in CI.
