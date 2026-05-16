# BrewAssistant v4 Fermentation Migration Queue

This document defines the remaining planned PR queue for migrating `packages/brewassistant_fermentation_module.yaml` away from direct `fwk_*` reads while keeping legacy backend entities as source of truth.

The goal is to avoid one-off manual edits and instead work through small, ordered PRs.

---

## Current baseline

Already completed:

- PR #14: `brewassistant_namespace_aliases_fermentation.yaml`
- PR #15: fermentation module migration plan
- PR #17: fermentation workflow binary aliases
- PR #18: fermentation script wrappers

The remaining changes should be handled as ordered PRs.

---

## Recommended stacked PR order

### PR #19 — Migrate fermentation automation wrapper calls

File:

- `packages/brewassistant_fermentation_module.yaml`

Scope:

```yaml
- service: script.fwk_start_batch
+ service: script.brew_batch_start
```

```yaml
- service: script.fwk_reset_batch
+ service: script.brew_batch_reset
```

Notes:

- Do not rename automation IDs.
- Do not rename source scripts.
- This only changes automations to call the new wrapper scripts from PR #18.

---

### PR #20 — Migrate daily SG snapshot reads

File:

- `packages/brewassistant_fermentation_module.yaml`

Scope inside `FWK - Save Daily SG Snapshot`:

```yaml
input_boolean.fwk_batch_active
→ input_boolean.brew_batch_active
```

```yaml
sensor.fwk_live_sg
→ sensor.brew_fermentation_live_sg
```

Keep source-of-truth helpers unchanged:

```yaml
input_number.fwk_sg_today
input_number.fwk_sg_yesterday
input_number.fwk_sg_two_days_ago
```

Reason:

Those input_numbers are still storage helpers and should not be renamed yet.

---

### PR #21 — Migrate Brewfather auto-start / auto-reset conditions

File:

- `packages/brewassistant_fermentation_module.yaml`

Scope:

```yaml
input_boolean.fwk_batch_active
→ input_boolean.brew_batch_active
```

```yaml
input_boolean.fwk_transferred_to_keg
→ input_boolean.brew_transferred_to_keg
```

```yaml
script.fwk_start_batch
→ script.brew_batch_start
```

```yaml
script.fwk_reset_batch
→ script.brew_batch_reset
```

Notes:

- If PR #19 already migrated script calls, this PR only needs condition/trigger reads.
- Keep automation IDs as `fwk_*` for now.

---

### PR #22 — Migrate source script internal reads only

File:

- `packages/brewassistant_fermentation_module.yaml`

Scope:

Inside `script.fwk_start_batch`, migrate read-only template reads:

```yaml
sensor.fwk_live_sg
→ sensor.brew_fermentation_live_sg
```

Do **not** change service targets yet:

```yaml
input_boolean.fwk_batch_active
input_boolean.fwk_spunding_installed
input_boolean.fwk_dry_hop_added
input_boolean.fwk_cold_crash_active
input_boolean.fwk_transferred_to_keg
input_datetime.fwk_batch_start
input_datetime.fwk_cold_crash_start
input_number.fwk_sg_today
input_number.fwk_sg_yesterday
input_number.fwk_sg_two_days_ago
```

Reason:

Those are still backend/source-of-truth state holders.

---

### PR #23 — Add missing aliases for remaining source-of-truth sensors

File:

- `packages/brewassistant_namespace_aliases_fermentation.yaml`

Potential aliases to add after grep review:

```yaml
sensor.brew_cold_crash_days
binary_sensor.brew_fermentation_sg_stable_2_days
```

These would allow later cleanup of:

```yaml
sensor.fwk_cold_crash_days
binary_sensor.fwk_sg_stable_2_days
```

Do not add these blindly unless the source entities are verified on `main`.

---

### PR #24 — Final safe grep cleanup

Files:

- `packages/brewassistant_fermentation_module.yaml`
- alias packages if needed

Goal:

Reduce remaining `fwk_*` references outside:

- entity definitions
- unique_id values
- script names
- automation IDs
- backend/source-of-truth service targets
- alias packages

Useful grep:

```bash
grep -R "fwk_" -n packages 2>/dev/null \
  | grep -v "brewassistant_namespace_aliases" \
  | grep -v "unique_id:" \
  | grep -v "id:"
```

---

## Safety rules

1. Do not rename existing `fwk_*` entities yet.
2. Do not change `unique_id: fwk_*` values yet.
3. Do not change source-of-truth service targets until two-way helper sync is verified.
4. Prefer wrapper calls over direct legacy script calls.
5. Keep each PR small enough to inspect in HA before merging the next one.

---

## Stack strategy

If these PRs are created ahead of time, use a stacked branch model:

```text
v4-fermentation-pr19-wrapper-calls        -> main
v4-fermentation-pr20-daily-sg             -> v4-fermentation-pr19-wrapper-calls
v4-fermentation-pr21-autostart-reset      -> v4-fermentation-pr20-daily-sg
v4-fermentation-pr22-script-read-cleanup  -> v4-fermentation-pr21-autostart-reset
v4-fermentation-pr23-missing-aliases      -> main or latest merged branch
```

Merge order must follow the stack order.
