# Physical validation — 2026-09-05

This document records the supervised BrewAssistant / Brewfather / BrewZilla field-test findings from 2026-09-05.

It is a dated evidence snapshot. Later fixes should not rewrite the observations below; add new validation evidence instead.

## Test focus

The session focused on the physical transition:

```text
Heatstrike
  -> strike readiness
  -> Mash-In Started
  -> Brewfather Continue / progression
  -> Mash-In Complete
  -> normal mash circulation
```

The canonical external MASH/process probe remained the readiness temperature while BrewZilla internal/WORT remained the hotter safety/overshoot view.

---

## Finding 1 — Heatstrike gradient deadlock

The session reproduced a deterministic state where the external process probe still needed heat while the internal BrewZilla view had already crossed the strike target.

Representative observed state:

```text
strike target       71.8 °C
MASH/BLE             ~67.8 °C
BrewZilla internal   ~72.7 °C
```

The existing hottest-view overshoot rule could request:

```text
heat utilization 0%
heater OFF
```

while the MASH/BLE readiness probe was still several degrees below strike.

That created a deadlock:

```text
MASH/BLE says: not ready
internal says: stop heat
=> readiness probe cannot converge to strike
```

### Fix — PR #197

The normal +0.5 °C overshoot safe-down remains the default behavior, but a narrow pre-mash-in gradient-relief state now exists when:

```text
MASH/BLE is still below strike
AND mash/internal temperature gradient is real
AND hottest-view overshoot > 0.5 °C
AND hottest-view overshoot <= 1.5 °C
```

In that state:

```text
heat authority cap = 15%
heater master remains enabled
pump utilization = 100%
```

The intent is temperature equalization while BrewZilla's local thermostat continues regulating against the written strike target.

A hottest-view overshoot above +1.5 °C remains an explicit hard stop even when a gradient exists.

Regression coverage was added for the observed BLE-low/internal-high deadlock case.

---

## Finding 2 — Heatstrike / Mash-In progression improved

After the Heatstrike gradient fix, the physical flow progressed farther through strike readiness and Mash-In than in the previous validation runs.

The test confirmed that the remaining issue was no longer simply failure to reach the Mash-In gate. The next fault appeared at the handoff from `mash_in_started` to Brewfather progression.

---

## Finding 3 — pump could resume too early during Mash-In

The intended contract is:

```text
Mash-In Started
  -> pump OFF
  -> pump utilization 0%
  -> grain addition / stirring window
  -> wait for real Brewfather progression
  -> Mash-In Complete
  -> normal mash circulation resumes
```

During the test, circulation was observed active again while the Mash-In status UI still indicated that BrewAssistant was waiting for Brewfather Continue.

The root cause was the auto-complete bridge accepting an ordinary Brewfather `running` mash state as sufficient evidence that Mash-In had completed.

That was too permissive because Brewfather can already report a running mash context while the operator is still inside the physical Mash-In window.

### Fix — PR #202

Automatic Mash-In Complete now requires real Brewfather progression evidence:

```text
explicit paused -> running transition
OR
active Brewfather mash target moves away from the strike target captured by the Mash-In gate
```

A plain `running` state alone is no longer enough.

Until progression is observed:

```text
mash_in_gate_state = mash_in_started
pump remains OFF / 0%
```

Only after progression may normal mash circulation resume.

Regression coverage explicitly forbids the old `running_while_mash_in_started_*` behavior.

---

## Finding 4 — Mash-In status UI could linger

The yellow Mash-In status box could remain visible after backend progression because the card could prefer stale button attributes over the live orchestration/gate state.

PR #202 changes the runtime-flow cards to prefer the live gate/orchestration state.

Expected behavior:

```text
ready_for_mash_in / mash_in_started
  -> Mash-In status box visible

mash_in_complete
  -> Mash-In status box disappears
```

English and Swedish runtime-flow cards were updated together.

---

## UI observations completed the same day

The field test also led to two operator-visibility improvements:

### BrewTracker phase chip — PR #200

```text
Planning   -> yellow
Pre-start  -> green
Brewing    -> red
other      -> blue fallback
```

### BrewZilla thermal gauge — PR #201

The dual-temperature BrewZilla gauge now uses a dynamic background around the active target:

```text
below target - 1.5 °C  -> yellow
within ±1.5 °C         -> green
above target + 1.5 °C  -> red
missing target/temp     -> neutral
```

These are presentation changes only and do not modify control authority.

---

## Repository watchdog baseline — PR #199

The same development cycle added repository-level validation:

```text
CI / compile / fatal Ruff checks
pytest on Python 3.11 / 3.12 / 3.13
HACS Action
Hassfest
Dependabot
```

Hassfest caught and caused correction of manifest ordering during setup, demonstrating that the validation layer is already useful.

---

## Status after the 2026-09-05 fixes

Implemented and regression-covered:

```text
[x] Heatstrike gradient relief avoids BLE-low/internal-high zero-heat deadlock
[x] +1.5 °C gradient hard-stop boundary retained
[x] Mash-In Started owns pump OFF / 0% physical window
[x] plain BF running state cannot auto-complete Mash-In
[x] BF progression can auto-complete Mash-In
[x] Mash-In UI prefers live gate state and disappears after completion
[x] BrewTracker phase color semantics improved
[x] BrewZilla gauge thermal-state background added
[x] repository CI/HACS/Hassfest watchdog baseline added
```

Still requires physical validation after the merged fixes:

```text
[ ] Mash-In Started visibly holds pump OFF / 0% for the entire grain-addition window
[ ] Brewfather Continue/progression is the first event that permits circulation restart
[ ] Mash-In status box disappears immediately after confirmed progression
[ ] gradient-relief state converges MASH/BLE without unsafe internal overshoot
[ ] > +1.5 °C hottest-view overshoot still produces the intended hard stop
[ ] first continuous real-mash validation through 66 °C hold and following ramp
```

---

## Architecture contract carried forward

The fixed external temperature ownership remains unchanged:

```text
Heat strike -> Mash -> Mash out -> Sparge -> Pre-boil
  Brewday / hot-side owns the optional external process sensor

Boil starts
  hot-side releases it

Chill -> Transfer
  Cooling/CFC may own the same sensor as wort-out/CFC-outlet temperature
```

The 2026-09-05 fixes do not alter that ownership model.
