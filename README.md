# BrewAssistant v0.2.0-beta.11 — hot-side control paused

**BrewAssistant** is a modular Home Assistant brewing assistant for Brewday intelligence, BrewZilla/RAPT integration, cooling, carbonation, serving/climate, fermentation tracking, dashboards and notifications.

> [!CAUTION]
> **Current operating decision, 2026-09-19: do not use BrewAssistant for active BrewZilla hot-side control.** The beta.11 water-only field test was aborted after physical Mash-In authority and the read-only timing display diverged. Interlock installation/tag identity are verified, **physical behavior is not accepted**. `recovery_required` blocks new BA writes but does not necessarily switch off outputs already running on BrewZilla. Verify actual heater/pump state locally. A RAPT profile does **not** automatically isolate BA: the current RAPT bridge still gives BA target/heat/pump control authority. A genuine monitor-only/external-owner write barrier has **not** been implemented or verified. Do not run two competing controllers. Read the [dated incident checkpoint and RAPT handoff](docs/ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md) before further hot-side work.
>
> The published `v0.2.0-beta.10` tag contains old code and must not be used for control tests. HLT power sharing is **simulation only**, not an electrical safety system. Passing CI does not approve unattended or grain brewing.

BrewAssistant is moving from YAML-heavy Home Assistant packages to a Python integration. Runtime normalization, ownership, calculations, safety and hardware orchestration live in `custom_components/brewassistant/`; dashboard YAML presents state and explicit operator actions. **This describes the existing code, not a currently approved active-control configuration.**

```text
Python integration = runtime + ownership + logic + guards + existing hardware decisions
Dashboard YAML     = presentation + explicit operator actions
```

---

## Current division of work (2026-09-19)

- **RAPT control development:** dedicated RAPT Cloud Link chat. Intended future single hot-side controller: RAPT/BrewZilla. Validate real profile execution and ownership there, not here.
- **BrewAssistant development:** pause all BA hot-side actuator field testing. Preserve read-only status, diagnostics, audit, timing, efficiency/learning and UI work where they can be safely separated from actuator writes. The current integration still includes write paths; no safe simultaneous RAPT+BA deployment is implied.
- **Operator:** physical BrewZilla controls, pump/flow, mash-in and final safety verification. An aborted BA test is not proof of hardware OFF.
- **Brewfather:** recipe/metadata only in the proposed single-controller design, without parallel BA control.

**Next engineering gate:** inventory *all* BA actuator paths and implement/test one central fail-closed monitor-only/external-owner boundary before enabling BA alongside an independently running RAPT profile. Simply hiding a card, setting a read-only-looking status or changing documentation cannot enforce this. The old RAPT runtime documentation describes BA as controller and remains historical until the handoff is implemented.

---

## Development / release flow

Three permanent branches, **no invented project branches**:

```text
dev (development) -> beta (integrated test + GitHub Pre-release) -> main (validated/stable)
```

Normal work is committed to `dev`. Promote a coherent candidate with a `dev -> beta` PR using **Create a merge commit**, not squash/rebase. Require CI/HACS/Hassfest on the actual beta merge SHA. Tag and publish a prerelease from that exact SHA; read back the tag SHA, tagged manifest and critical files before HACS installation. Promote `beta -> main` separately only after appropriate field validation. Never move a published tag. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

**Actual release status:** [PR #213](https://github.com/Jocke1970/brewassistant-beta/pull/213) is merged; [v0.2.0-beta.11](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.11) is published from beta merge commit `c989cde6dbebe769c2f4ff9575c78b532718f8eb`, tagged manifest version `0.2.0-beta.11` and Mash-In interlock file/install verified. Subsequent water-only test **failed acceptance and was aborted**. Do not republish beta.11 or treat a verified release archive as physical validation. This documentation-only checkpoint updates `dev`, not the published release, `beta`, `main`, or the HA installation.

---

## Repository watchdogs

CI compiles Python, checks fatal Ruff errors, validates JSON and runs pytest on Python 3.11/3.12/3.13. HACS validation, Hassfest, Dependabot and promotion-source guard are present. CI/HACS/Hassfest run on `dev`, `beta` and `main`; Dependabot targets `dev`. The promotion guard requires PRs to `beta` from `dev` and PRs to `main` from `beta`. Code checks are not physical acceptance tests.

---

## Documentation map

| Area | Document |
| --- | --- |
| **Current safety/status checkpoint and RAPT handoff (read first)** | [`docs/ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md`](docs/ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md) |
| Workflow / promotion / release rules | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Published beta.11 release notes (historical package description, not field acceptance) | [`docs/beta11-prerelease-notes_sv.md`](docs/beta11-prerelease-notes_sv.md) |
| Historical, currently suspended physical mash test plan | [`docs/physical-mash-test-plan-2026-09-19_sv.md`](docs/physical-mash-test-plan-2026-09-19_sv.md) |
| Roadmap and outstanding validation gates | [`docs/roadmap.md`](docs/roadmap.md) |
| Existing RAPT profile bridge (BA-owned control, **not** desired passive model) | [`docs/rapt-brewzilla-profile-runtime.md`](docs/rapt-brewzilla-profile-runtime.md) |
| HLT SIM-1 field evidence and Brewday handoff | [`docs/hlt-sim1-field-validation-2026-09-19.md`](docs/hlt-sim1-field-validation-2026-09-19.md) |
| HLT safety contract | [`custom_components/brewassistant/hlt/README.md`](custom_components/brewassistant/hlt/README.md) |
| HLT sensor/source contract and dashboard | [`docs/hlt-dashboard-backend.md`](docs/hlt-dashboard-backend.md), [`docs/hlt-dashboard-card.md`](docs/hlt-dashboard-card.md) |
| Brewday ↔ BrewZilla architecture (legacy active-control design) | [`docs/brewday-brewzilla.md`](docs/brewday-brewzilla.md) |
| Physical validation 2026-09-06 and earlier | [`docs/physical-validation-2026-09-06.md`](docs/physical-validation-2026-09-06.md), [`docs/physical-validation-2026-09-05.md`](docs/physical-validation-2026-09-05.md), [`docs/physical-validation-2026-08-31.md`](docs/physical-validation-2026-08-31.md) |
| Brewday Event Log / Flight Recorder | [`docs/brewday-audit.md`](docs/brewday-audit.md) |
| BrewZilla backend | [`docs/backends/brewzilla-backend.md`](docs/backends/brewzilla-backend.md), [`custom_components/brewassistant/brewzilla/README.md`](custom_components/brewassistant/brewzilla/README.md) |
| Cooling backend | [`docs/backends/cooling-backend.md`](docs/backends/cooling-backend.md) |
| BrewZilla equipment learning | [`docs/brewzilla-control-profile.md`](docs/brewzilla-control-profile.md), [`docs/brewzilla-equipment-learning.md`](docs/brewzilla-equipment-learning.md) |
| Dashboard / localization | [`docs/dashboard-baselines.md`](docs/dashboard-baselines.md), [`docs/localization.md`](docs/localization.md) |

Dated validation documents and released notes are historical evidence. Do not rewrite them retroactively to imply later fixes were already tested. The checkpoint above supersedes old **operating advice**, not historical observations.

---

## Existing hot-side code: architecture, NOT approved for live control

The beta.11 implementation normalizes Brewfather Brew Tracker, Manual Brewday or a RAPT BrewZilla profile into BA runtime/ownership and lets BA write target, heat and pump via RAPT Cloud Link. BrewZilla supplies readback. This is precisely why the proposed passive BA model requires code changes: `brewzilla_rapt_profile_control_bridge.py` explicitly identifies BA as `control_owner` and `heat_pump_owner`, so an active RAPT profile is not currently isolated from BA.

```text
Existing (PAUSED) implementation:
Brewfather / Manual / RAPT profile -> BA runtime + orchestration -> RCL writes -> BrewZilla

Intended (NOT IMPLEMENTED/VERIFIED):
RAPT profile -> RAPT/BrewZilla owns physical control
                        ↓ read-only observations
BA status + timing + audit + passive learning
```

The intended Mash-In guard (`ready -> Started -> pump OFF -> Complete -> 10 min settling -> separate ~25% and ~50% confirmations`, with physical hold target authority) passed code tests but failed field acceptance. The September 19 test saw `recovery_required`/`gate idle` with no physical hold target while the timing card showed a 66 °C hold; heater/pump readback also remained on at that point. Operator reported abort. Do not equate a timer display or new interlock attribute with a functioning physical gate. See the [checkpoint](docs/ba-hot-side-pause-and-rapt-handoff-2026-09-19_sv.md).

The operator ABORT latch and BrewZilla hardware ABORT have distinct semantics. `recovery_required` blocks BA writes; it is not an automatic physical OFF action. Verify physical device state locally.

The documented external process sensor ownership (hot side through pre-boil, cooling/CFC in Chill/Transfer) remains a proposed/implemented integration contract and needs validation when redesigning the passive path. Do not let BA take an active control lease merely to render data.

---

## HLT SIM-1 — simulation only

The simulator consumes Brewday Audit/session, sparge volume and BrewZilla readback, with a separate timer, read-only sensors and cards. BrewZilla priority and HLT watt budget are *hypothetical*. It does not cap BZ, switch a physical HLT, or provide independent fast fail-OFF electrical load shedding. Prior 2026-09-19 field observations led to code regression fixes that still need a separate read-only HA retest. Do not connect physical HLT outputs while this work is parked. See [HLT evidence](docs/hlt-sim1-field-validation-2026-09-19.md).

---

## Other modules and paused work

Fermentation, cooling, carbonation, serving/climate, manual runtime, diagnostic sensors, notifications, physical timing and Equipment Learning are distinct BA workstreams. Code presence does not imply every module is validated. Preserve existing code, data and prior test artifacts. Continue isolated, non-actuating work only when safe to do so; do not disable safety functionality blindly to silence errors.

**Priority order:** (1) verify the physical machine is safe after any stopped test; (2) isolate BA actuator writes before coexisting with RAPT; (3) establish passive telemetry and consistent states; (4) improve oversized runtime-flow UI; (5) revisit BA hot-side physical control only as a separate, explicitly approved and retested effort. See [roadmap](docs/roadmap.md).

---

## AI-assisted development

BrewAssistant is developed by Joachim Eriksson and ChatGPT using iterative Python, YAML, documentation and supervised physical tests. Treat generated/AI-assisted code as experimental; review before it influences heat, pumps, cooling, pressurized equipment or other hardware.
