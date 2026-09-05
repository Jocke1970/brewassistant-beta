# BrewAssistant 0.2.0-beta.9

Status: **prerelease candidate**

Beta.9 consolidates the 2026-09-05 Heatstrike/Mash-In field-test fixes, operator-facing BrewZilla/BrewTracker UI improvements, repository watchdogs and the new three-branch promotion workflow.

This remains a supervised beta. It is not an unattended brewing-control release.

## Hot-side / Mash-In

### Heatstrike gradient relief — PR #197

Fix a pre-mash-in deadlock where the external MASH/BLE readiness probe could remain below strike while BrewZilla internal/WORT had already crossed the strike target.

Current contract:

```text
normal hottest-view overshoot > +0.5 °C
  -> explicit safe-down remains the default

but, during a real pre-mash-in temperature gradient:
  MASH/BLE still below strike
  internal overshoot > +0.5 °C and <= +1.5 °C
  -> keep local thermostat enabled
  -> heat authority capped at 15%
  -> pump forced to 100% for equalization

internal overshoot > +1.5 °C
  -> hard stop remains authoritative
```

The change is intentionally narrow and does not alter Brewfather ownership, target latching or the Mash-In state machine.

### Mash-In pump hold / Brewfather handoff — PR #202

Fix a second handoff fault where an ordinary Brewfather `running` state could cause Mash-In to auto-complete and circulation to restart too early.

New contract:

```text
Mash-In Started
  -> pump OFF / 0%
  -> wait for real Brewfather progression

progression evidence:
  paused -> running
  OR active BF mash target moves away from the strike target

plain BF running state
  -> not sufficient
```

The Mash-In status UI now prefers live gate/orchestration state over stale button attributes, so the yellow waiting box disappears after actual completion.

See `docs/physical-validation-2026-09-05.md` for the field-test evidence and remaining physical checkpoints.

## Operator UI

### BrewTracker phase chip — PR #200

```text
Planning   -> yellow
Pre-start  -> green
Brewing    -> red
fallback   -> blue
```

### BrewZilla thermal gauge — PR #201

The dual-temperature gauge now has dynamic thermal-state background feedback:

```text
below target - 1.5 °C -> yellow
within ±1.5 °C        -> green
above target + 1.5 °C -> red
invalid/missing data   -> neutral
```

The gauge uses the same target priority as the displayed BrewZilla process state, including the latched strike target during Heatstrike.

## Repository watchdogs — PR #199

Beta.9 includes the repository-quality baseline:

- Python compile checks
- fatal Ruff checks
- integration JSON validation
- pytest on Python 3.11, 3.12 and 3.13
- HACS Action
- Hassfest
- daily Dependabot checks

Hassfest already caught a manifest-ordering issue during initial setup.

## Backend documentation — PR #198

Code-local backend READMEs now document the current ownership boundaries and installed architecture close to the implementation, including:

- Brewday Runtime
- BrewZilla hot side
- Cooling Runtime v2
- Fermentation Tracking / Fermentation Chamber
- Carbonation
- Kegerator / Climate Supervisor
- shared utilities and module registry

## Development / release workflow

The repository now uses three long-lived branches only:

```text
dev -> beta -> main -> GitHub Release
```

- `dev`: active development
- `beta`: integrated field-test candidate
- `main`: installable/runnable version
- releases are created only from `main`

CI, HACS and Hassfest run across all three branches. Dependabot enters through `dev`, and the promotion guard enforces `dev -> beta -> main` for pull requests.

See `CONTRIBUTING.md`.

## Physical validation still required

Before treating beta.9 as physically proven through the Mash-In boundary:

```text
[ ] verify Mash-In Started keeps pump OFF / 0% until BF progression
[ ] verify BF Continue/progression is what permits circulation restart
[ ] verify Mash-In waiting UI disappears immediately after completion
[ ] verify gradient relief converges the external process probe safely
[ ] verify > +1.5 °C hottest-view overshoot still hard-stops heat
[ ] continue through real mash hold/ramp validation
```

## Release note

When this candidate has passed the intended `beta` validation and is promoted to `main`, create GitHub prerelease:

```text
v0.2.0-beta.9
```

from the promoted `main` commit.
