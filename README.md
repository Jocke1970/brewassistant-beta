# BrewAssistant v0.2.0-beta.11 candidate

**BrewAssistant** is a modular Home Assistant brewing assistant for supervised Brewday intelligence, BrewZilla/RAPT hardware control, cooling, carbonation, serving/climate, fermentation tracking, dashboards and notifications.

> [!WARNING]
> BrewAssistant is an actively developed hobby beta, not unattended brewing automation. Verify heat/pump actions, electrical safety, sanitation, pressure and fermentation decisions manually. HLT power sharing is **simulation only** and cannot protect an electrical circuit. The published `v0.2.0-beta.10` tag points to old code without the new physical mash interlock: do not use it for the next control test.

BrewAssistant is moving from YAML-heavy Home Assistant packages to a Python integration. Runtime normalization, ownership, calculations, safety and hardware orchestration live in `custom_components/brewassistant/`; dashboard YAML presents state and explicit operator actions.

```text
Python integration = runtime + ownership + logic + safety + hardware decisions
Dashboard YAML     = presentation + explicit operator actions
```

---

## Development / release flow

Three permanent branches, **no invented project branches**:

```text
dev (develop) -> beta (integrated test + GitHub Pre-release) -> main (validated/stable)
```

Normal work is committed to `dev`. Promote the coherent candidate with a `dev -> beta` pull request using **Create a merge commit**, not squash/rebase. Require CI, HACS and Hassfest on the actual `beta` merge commit. Create prerelease tag `v0.2.0-beta.11` from **that exact beta SHA**, target `beta` in GitHub Releases, paste the entire release Markdown and mark **Pre-release**. Read back the tag SHA, tagged manifest and tagged `brewzilla/__init__.py` before HACS installation. Carry out supervised water-only validation after installing that exact prerelease. If it fails, fix on `dev`, repromote and create a NEW version; do not move published tags. Promote validated code `beta -> main` later for a separate stable release from the resulting `main` merge commit. Do not create beta releases directly from `dev` or use `main` to distribute unvalidated code. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [beta.11 release Markdown](docs/beta11-prerelease-notes_sv.md).

**Combined development status, 2026-09-19:** read-only HLT SIM-1 [PR #212](https://github.com/Jocke1970/brewassistant-beta/pull/212) is merged to the common `dev`, alongside SG-driven fermentation and the physical Mash-In interlock. The beta.11 candidate is being promoted by [PR #213](https://github.com/Jocke1970/brewassistant-beta/pull/213). A GitHub merge does **not** update the Home Assistant installation. Compare actual installed files with the intended version, preserve backups, and verify the tag before updating. Passing tests do not prove physical safety.

---

## Repository watchdogs

CI compiles Python, checks fatal Ruff errors, validates JSON and runs pytest on Python 3.11/3.12/3.13. HACS validation, Hassfest, Dependabot and promotion-source guard are present. CI/HACS/Hassfest run on `dev`, `beta` and `main`; Dependabot targets `dev`. The promotion guard requires PRs to `beta` from `dev` and to `main` from `beta`. The release checklist additionally verifies exact tag SHA and manifest because CI passing on a different commit does not validate a release archive.

---

## Documentation map

| Area | Document |
| --- | --- |
| Workflow / promotion / release rules | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Current beta.11 release Markdown + HACS safety checks | [`docs/beta11-prerelease-notes_sv.md`](docs/beta11-prerelease-notes_sv.md) |
| Swedish physical mash test plan | [`docs/physical-mash-test-plan-2026-09-19_sv.md`](docs/physical-mash-test-plan-2026-09-19_sv.md) |
| Roadmap and outstanding validation gates | [`docs/roadmap.md`](docs/roadmap.md) |
| HLT SIM-1 field evidence and Brewday handoff | [`docs/hlt-sim1-field-validation-2026-09-19.md`](docs/hlt-sim1-field-validation-2026-09-19.md) |
| HLT operating/safety contract | [`custom_components/brewassistant/hlt/README.md`](custom_components/brewassistant/hlt/README.md) |
| HLT sensor/source contract and dashboard | [`docs/hlt-dashboard-backend.md`](docs/hlt-dashboard-backend.md), [`docs/hlt-dashboard-card.md`](docs/hlt-dashboard-card.md) |
| Brewday ↔ BrewZilla operator/control architecture | [`docs/brewday-brewzilla.md`](docs/brewday-brewzilla.md) |
| Physical validation 2026-09-06 and earlier | [`docs/physical-validation-2026-09-06.md`](docs/physical-validation-2026-09-06.md), [`docs/physical-validation-2026-09-05.md`](docs/physical-validation-2026-09-05.md), [`docs/physical-validation-2026-08-31.md`](docs/physical-validation-2026-08-31.md) |
| Brewday Event Log / Flight Recorder | [`docs/brewday-audit.md`](docs/brewday-audit.md) |
| BrewZilla backend | [`docs/backends/brewzilla-backend.md`](docs/backends/brewzilla-backend.md), [`custom_components/brewassistant/brewzilla/README.md`](custom_components/brewassistant/brewzilla/README.md) |
| Cooling backend | [`docs/backends/cooling-backend.md`](docs/backends/cooling-backend.md) |
| BrewZilla control / equipment learning | [`docs/brewzilla-control-profile.md`](docs/brewzilla-control-profile.md), [`docs/brewzilla-equipment-learning.md`](docs/brewzilla-equipment-learning.md) |
| Dashboard / localization | [`docs/dashboard-baselines.md`](docs/dashboard-baselines.md), [`docs/localization.md`](docs/localization.md) |

Historical physical-validation documents are evidence snapshots. Do not rewrite them retroactively to make later fixes look like they were already tested; create a new dated report.

---

## Current hot-side architecture

BrewAssistant is an operator-supervised hot-side controller. Brewfather Brew Tracker, Manual Brewday or a RAPT BrewZilla profile supplies normalized source/step/target intent; BrewAssistant manages runtime interpretation, source ownership, guards and target/heat/pump control through RAPT Cloud Link; BrewZilla supplies physical readback. Brewday Flight Recorder and Equipment Learning record evidence.

```text
Brewfather Brew Tracker / Manual Brewday / RAPT profile
          ↓ normalized Brewday Runtime + ownership
BrewZilla orchestration + phase/safety guards
          ↓ physical target / heat / pump
BrewZilla / RAPT hardware
          ↓
Flight Recorder + diagnostics + passive learning
```

Safety precedence:

```text
operator or hardware ABORT / hard safety
  > runtime source ownership
  > dedicated phase authority
  > generic supervised positive control
  > local-regulation preservation
  > advice / learning / presentation
```

**Brewfather ownership:** Planning or batch phase Brewing at initial Start without positive tracker-start evidence is visible/ready but does not own hot-side. Ownership begins on positive start evidence; a subsequent legitimate pause retains it. `active: true` alone does not prove tracker start. See [Brewday/BZ architecture](docs/brewday-brewzilla.md).

**Heatstrike / Mash-In:** Brewfather Play authorizes the dedicated bounded pre-mash controller. Outside that authority, generic positive actions use Supervised Apply where applicable. External MASH/process probe is readiness authority; BZ internal/WORT is kettle/limiter/safety context. The 2026-09-06 refined Heatstrike gradient-relief rule requires MASH below strike, real gradient >=1.5 °C and hottest-view overshoot >+0.5 °C through +2.0 °C: heat authority is capped at 5 %, heater master remains available to local regulation and pump is 100 % for equalization. Above +2.0 °C hottest-view overshoot the explicit heat stop remains authoritative. This is a **Heatstrike safety guard**, not permission to throttle BZ for HLT.

**Strict Mash-In handoff (candidate; physical retest pending):** `ready -> Mash-In Started -> mash target release -> pump OFF/0 % during grain addition -> post-start Brewfather PAUSED observed -> later BF RUNNING -> Mash-In Complete -> pump OFF/0 % during 10 min settling -> operator-confirmed ~25 % low flow -> after 5 min and a second confirmation ~50 % normal flow`. Brewfather's next target must not supersede an unfinished physical hold. No timer callback may energize the pump. An old running state or target change cannot count as Mash-In completion evidence; manual completion remains fallback. See the [dated 2026-09-19 physical evidence](docs/physical-mash-control-contract-2026-09-19.md) and [test plan](docs/physical-mash-test-plan-2026-09-19_sv.md).

**ABORT:** BrewZilla hardware ABORT shuts down heater/pump/utilization and blocks new positive actions. Brewday operator ABORT adds a persistent ownership latch; same Brewfather tracker cannot silently reclaim hot-side after abort. Explicit rearm releases Brewday ownership latch but does not bypass separate hardware lockout.

**Process thermometer:** Brewday/BZ owns the external process sensor from Heat strike through Mash, Mash out, Sparge and Pre-boil; hot side releases it at Boil. Cooling/CFC acquires it for outlet/wort-out during Chill/Transfer where applicable. Internal BZ probe remains kettle context throughout.

---

## HLT SIM-1 — integrated on dev, not a hardware controller

The secondary HLT simulator consumes Brewday Audit/session, effective sparge volume and BZ readback. It has an independent 30-second timer, 31 read-only sensors, virtual HLT water temperature/energy/timers, per-session JSONL and English/Swedish high-contrast standalone dashboard cards. Positive sparge water is required; No Sparge stays idle. Real and virtual watts, receiver and measured/model temperatures are deliberately separate.

**BrewZilla always has absolute power priority.** HLT receives only a hypothetical opportunity when BZ is observed cruising at matching targets, physical data are fresh, no ramp is requested and the entire HLT heater fits within the *scenario* budget. Unknown/new stages fail closed; explicit ramp steps veto virtual HLT. The model **never** caps BZ or switches a real HLT. A 30-second polling loop and example 2,500 W budget are not an electrical load-shed/interlock. A future physical phase requires separate, independent fast fail-OFF HLT isolation and confirmed real OFF feedback, plus circuit and dry-fire safety validation.

The 2026-09-19 water test verified wattmeter identity, volume propagation and conservative wait, and exposed held-setting freshness and ramp-step interpretation defects corrected on `dev`. The final ramp-policy code is regression-tested but awaits a second HA field test. See [dated findings and exact next steps](docs/hlt-sim1-field-validation-2026-09-19.md). Never treat a GitHub promotion as a new live installation.

---

## Other integrated areas

Manual runtime; Brewday Stage Engine, deterministic Flight Recorder, source ownership and operator ABORT; physical ramp/hold timing telemetry; RCL recovery and readback grace; passive Equipment Learning; Cooling Runtime v2/CFC and coil/manual water; carbonation; Climate Supervisor; kegerator fan/guard; fermentation tracking including SG-driven logic; EN/SV dashboard parity and CI/HACS/Hassfest. Some are scaffolds, other modules require full-cycle physical validation. See [roadmap](docs/roadmap.md) for individual status and gates.

---

## Immediate validation focus

Supervised BrewTracker PAUS/current-target hold and Resume; RAPT profile handoff; Heatstrike gradient and Mash-In pump/target transitions; the new 10-minute settling + separate 25/50 % confirmations; real 66 °C mash hold and 66→72 °C ramp; Mash out/Sparge/Pre-boil; external probe release at Boil; Cooling/CFC Chill/Transfer; Equipment Learning. For HLT specifically, use the latest combined integration to verify held settings, real ramp-step veto, cruise/yield behavior, unknown-data fail-closed and JSONL/timer fidelity **without physical HLT connected**. See [roadmap](docs/roadmap.md).

---

## AI-assisted development

BrewAssistant is developed by Joachim Eriksson and ChatGPT using iterative Python, YAML, docs and supervised physical tests. Treat generated/AI-assisted code as experimental and review carefully before it can influence heat, pumps, cooling, pressurized equipment or other physical brewing hardware.
