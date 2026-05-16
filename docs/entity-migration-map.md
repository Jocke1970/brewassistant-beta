# Entity Migration Map

This document tracks the BrewAssistant v4 namespace migration away from the old `fwk_*` entity model.

The goal is not to blindly replace every occurrence of `fwk_`. The goal is to move each entity into a clear v4 namespace based on what it actually represents.

---

## Migration principles

1. Backend and dashboard YAML must be migrated together.
2. Process state, batch state, recipe data, chamber state and fermentation telemetry should not share one generic namespace.
3. UI cards should reference the same entities that backend packages actually create.
4. Legacy/archived files under `old_files/` do not need active migration unless they are restored.
5. Plain text labels that mention `FWK` are not automatically a problem; entity IDs are the priority.

---

## Recommended namespaces

| Area | Preferred prefix | Purpose |
|---|---|---|
| Process/workflow | `brew_process_*` | Current workflow status, next step, action stage, readiness |
| Batch lifecycle | `brew_batch_*` | Batch active, started timestamps, archived/done state |
| Recipe/runtime | `brew_recipe_*` | OG, FG, source, active recipe target values |
| Fermentation telemetry | `brew_fermentation_*` | Live SG, liquid temp, attenuation, SG timestamps |
| Cold crash | `brew_cold_crash_*` | Cold crash active state, start/done times, duration |
| Chamber control | `brew_chamber_*` | Chamber target, suggested range, alignment, action |
| Spunding | `brew_spunding_*` or `brew_process_spunding_*` | Spunding configuration and workflow prompts |
| Dry hop workflow | `brew_process_dry_hop_*` | Dry-hop preview/active workflow state |
| Transfer workflow | `brew_process_transfer_*` | Transfer preview/active/readiness state |
| BrewAssistant module toggles | `brewassistant_*` | Module enable flags and global BrewAssistant settings |

---

## High-priority entity mapping

### Process and workflow

| Old entity | Proposed new entity | Notes |
|---|---|---|
| `input_boolean.fwk_process_card_enabled` | `input_boolean.brew_process_card_enabled` | Used by main/process dashboard cards |
| `input_text.fwk_process_stage` | `input_text.brew_process_stage` | Manual/current stage text |
| `input_select.fwk_process_step` | `input_select.brew_process_step` | Workflow step selector |
| `sensor.fwk_process_status` | `sensor.brew_process_status` | Main workflow status |
| `sensor.fwk_next_step` | `sensor.brew_process_next_step` | Main next-step text |
| `sensor.fwk_current_action_stage` | `sensor.brew_process_current_action_stage` | Current action bucket |
| `sensor.fwk_next_action_stage` | `sensor.brew_process_next_action_stage` | Upcoming action bucket |
| `sensor.fwk_planned_summary` | `sensor.brew_process_planned_summary` | Human-readable runtime summary |
| `binary_sensor.fwk_ready_for_cold_crash` | `binary_sensor.brew_process_ready_for_cold_crash` | Workflow readiness |
| `binary_sensor.fwk_ready_for_transfer` | `binary_sensor.brew_process_ready_for_transfer` | Workflow readiness |

### Batch lifecycle

| Old entity | Proposed new entity | Notes |
|---|---|---|
| `input_boolean.fwk_batch_active` | `input_boolean.brew_batch_active` | Core batch active flag |
| `input_boolean.fwk_batch_confirmed` | `input_boolean.brew_batch_confirmed` | Batch confirmation |
| `input_boolean.fwk_batch_archived` | `input_boolean.brew_batch_archived` | Archived/done state |
| `input_datetime.fwk_batch_started_at` | `input_datetime.brew_batch_started_at` | Batch start timestamp |
| `input_datetime.fwk_batch_start` | `input_datetime.brew_batch_start` | Legacy duplicate candidate; review before migration |
| `input_button.fwk_start_batch` | `input_button.brew_batch_start` | Start action |
| `counter.fwk_gravity_check_counter` | `counter.brew_batch_gravity_check_counter` | Batch-level reading counter |
| `sensor.fwk_batch_age_days` | `sensor.brew_batch_age_days` | Derived batch age |
| `sensor.fwk_batch_age_hours` | `sensor.brew_batch_age_hours` | Derived batch age |

### Recipe/runtime

| Old entity | Proposed new entity | Notes |
|---|---|---|
| `input_boolean.fwk_recipe_loaded` | `input_boolean.brew_recipe_loaded` | Recipe context available |
| `input_text.fwk_recipe_source` | `input_text.brew_recipe_source` | Source such as Brewfather/manual fallback |
| `input_number.fwk_recipe_og` | `input_number.brew_recipe_og` | Recipe OG |
| `input_number.fwk_recipe_fg` | `input_number.brew_recipe_fg` | Recipe FG |
| `sensor.fwk_recipe_active_target_temp` | `sensor.brew_recipe_active_target_temp` | Active recipe target temp |

### Fermentation telemetry

| Old entity | Proposed new entity | Notes |
|---|---|---|
| `input_number.fwk_manual_sg` | `input_number.brew_fermentation_manual_sg` | Manual SG input |
| `input_number.fwk_manual_sg_previous` | `input_number.brew_fermentation_manual_sg_previous` | Previous manual SG |
| `input_number.fwk_sg_today` | `input_number.brew_fermentation_sg_today` | Daily SG storage |
| `input_number.fwk_sg_yesterday` | `input_number.brew_fermentation_sg_yesterday` | Daily SG storage |
| `input_number.fwk_sg_two_days_ago` | `input_number.brew_fermentation_sg_two_days_ago` | Daily SG storage |
| `sensor.fwk_live_sg` | `sensor.brew_fermentation_live_sg` | Current SG source |
| `sensor.fwk_live_temp` | `sensor.brew_fermentation_live_temp` | Current liquid temp source |
| `sensor.fwk_sg_last_updated` | `sensor.brew_fermentation_sg_last_updated` | SG timestamp |
| `sensor.fwk_attenuation` | `sensor.brew_fermentation_attenuation` | Fermentation attenuation |
| `sensor.fwk_gravity_points_left` | `sensor.brew_fermentation_gravity_points_left` | Gravity remaining |
| `binary_sensor.fwk_sg_stable_2_days` | `binary_sensor.brew_fermentation_sg_stable_2_days` | Stability detection |

### Cold crash

| Old entity | Proposed new entity | Notes |
|---|---|---|
| `input_boolean.fwk_cold_crash_active` | `input_boolean.brew_cold_crash_active` | Cold crash active flag |
| `input_datetime.fwk_cold_crash_start` | `input_datetime.brew_cold_crash_start` | Legacy timestamp candidate |
| `sensor.fwk_cold_crash_days` | `sensor.brew_cold_crash_days` | Derived duration |
| `binary_sensor.fwk_cold_crash_preview` | `binary_sensor.brew_process_cold_crash_preview` | Workflow preview |
| `binary_sensor.fwk_cold_crash_active_card` | `binary_sensor.brew_process_cold_crash_active_card` | Dashboard/workflow helper |
| `input_button.fwk_start_cold_crash` | `input_button.brew_cold_crash_start` | Action button |
| `input_button.fwk_finish_cold_crash` | `input_button.brew_cold_crash_finish` | Action button |

### Dry hop, spunding and transfer workflow

| Old entity | Proposed new entity | Notes |
|---|---|---|
| `input_boolean.fwk_dry_hop_added` | `input_boolean.brew_process_dry_hop_added` | Workflow flag |
| `binary_sensor.fwk_dry_hop_preview` | `binary_sensor.brew_process_dry_hop_preview` | Workflow preview |
| `binary_sensor.fwk_dry_hop_active` | `binary_sensor.brew_process_dry_hop_active` | Workflow active state |
| `input_boolean.fwk_spunding_installed` | `input_boolean.brew_spunding_installed` | Equipment/workflow flag |
| `binary_sensor.fwk_spunding_preview` | `binary_sensor.brew_process_spunding_preview` | Workflow preview |
| `binary_sensor.fwk_spunding_active` | `binary_sensor.brew_process_spunding_active` | Workflow active state |
| `input_boolean.fwk_transferred_to_keg` | `input_boolean.brew_process_transferred_to_keg` | Packaging/transfer completion flag |
| `binary_sensor.fwk_transfer_preview` | `binary_sensor.brew_process_transfer_preview` | Workflow preview |
| `binary_sensor.fwk_transfer_active` | `binary_sensor.brew_process_transfer_active` | Workflow active state |
| `input_button.fwk_start_packaging` | `input_button.brew_process_start_packaging` | Action button |
| `input_button.fwk_finish_packaging` | `input_button.brew_process_finish_packaging` | Action button |

### Chamber

| Old entity | Proposed new entity | Notes |
|---|---|---|
| `input_boolean.fwk_semiauto_enabled` | `input_boolean.brew_chamber_semiauto_enabled` | Chamber automation flag |
| `input_boolean.fwk_auto_apply_bf_target` | `input_boolean.brew_chamber_auto_apply_brewfather_target` | Apply BF target automatically |
| `input_boolean.fwk_allow_cold_crash_semiauto` | `input_boolean.brew_chamber_allow_cold_crash_semiauto` | Allow semiauto cold crash |
| `input_boolean.fwk_lock_fermentation_chamber` | `input_boolean.brew_chamber_lock_fermentation_chamber` | Chamber safety lock |
| `sensor.fwk_chamber_target_midpoint` | `sensor.brew_chamber_target_midpoint` | Climate target midpoint |
| `sensor.fwk_chamber_target_span` | `sensor.brew_chamber_target_span` | Climate target span |
| `sensor.fwk_recipe_vs_chamber_delta` | `sensor.brew_chamber_recipe_delta` | Recipe vs chamber target delta |
| `sensor.fwk_live_vs_recipe_delta` | `sensor.brew_chamber_live_vs_recipe_delta` | Liquid/live vs recipe delta |
| `sensor.fwk_chamber_action` | `sensor.brew_chamber_action` | Current chamber action |
| `sensor.fwk_chamber_summary` | `sensor.brew_chamber_summary` | Human-readable chamber summary |
| `sensor.fwk_suggested_chamber_range` | `sensor.brew_chamber_suggested_range` | Suggested target range |
| `binary_sensor.fwk_chamber_on_recipe` | `binary_sensor.brew_chamber_on_recipe` | Alignment flag |
| `binary_sensor.fwk_chamber_running_too_warm` | `binary_sensor.brew_chamber_running_too_warm` | Warning flag |
| `binary_sensor.fwk_chamber_running_too_cold` | `binary_sensor.brew_chamber_running_too_cold` | Warning flag |
| `script.fwk_apply_brewfather_target` | `script.brew_chamber_apply_brewfather_target` | Dashboard calls this directly |

---

## Files known to contain `fwk_*`

### Backend packages

| File | Priority | Notes |
|---|---:|---|
| `packages/brewassistant_fermentation_module.yaml` | 1 | Largest legacy surface; contains most process, batch, recipe and fermentation helpers |
| `packages/brewassistant_brewfather_adapter.yaml` | 2 | Recipe/runtime bridge; contains `fwk_recipe_*`, `fwk_live_sg`, `fwk_sg_last_updated` |
| `packages/brewassistant_chamber_module.yaml` | 3 | Chamber targets, deltas and apply-target logic use `fwk_*` |
| `packages/brewassistant_notifications_module.yaml` | 4 | Uses `fwk_batch_active`, `fwk_transferred_to_keg`, `fwk_cold_crash_active` in guards/triggers |

### Dashboards

| File | Priority | Notes |
|---|---:|---|
| `dashboards/brewassistant_fermentation_process_card.yaml` | 1 | Main process card; heavily references `fwk_*` |
| `dashboards/brewassistant_main_card.yaml` | 2 | Main/top card; heavily references `fwk_*` |
| `dashboards/brewassistant_fermentation_chamber_card.yaml` | 3 | References chamber sensors and `script.fwk_apply_brewfather_target` |

### Do not migrate automatically

| File/location | Reason |
|---|---|
| `old_files/` | Archive/legacy reference only |
| Manual mode `FWK` batch type option | User-facing batch type label, not an entity namespace |
| Documentation explaining legacy `fwk_*` | Should remain as migration documentation |

---

## Suggested migration sequence

1. Add new entities while keeping old entities temporarily.
2. Update dashboard YAML to the new entities.
3. Update automations/scripts to the new entities.
4. Keep optional compatibility/template aliases for one release cycle if needed.
5. Remove old `fwk_*` helpers only after Home Assistant has been restarted and dashboards verified.

---

## Replacement strategy

Avoid one global replacement such as:

```text
fwk_ -> brew_
```

Use category-aware replacements instead:

```text
fwk_process_*        -> brew_process_*
fkw_batch_*          -> brew_batch_*       # typo guard: do not apply; listed to catch mistakes
fwk_batch_*          -> brew_batch_*
fkw_recipe_*         -> brew_recipe_*      # typo guard: do not apply; listed to catch mistakes
fwk_recipe_*         -> brew_recipe_*
fkw_chamber_*        -> brew_chamber_*     # typo guard: do not apply; listed to catch mistakes
fwk_chamber_*        -> brew_chamber_*
```

Then review all remaining `fwk_` occurrences manually.

---

## Next work item

Create a migration branch that updates backend and dashboard YAML together, starting with:

1. `packages/brewassistant_fermentation_module.yaml`
2. `packages/brewassistant_brewfather_adapter.yaml`
3. `dashboards/brewassistant_fermentation_process_card.yaml`
4. `dashboards/brewassistant_main_card.yaml`

The chamber files should follow immediately after, because chamber cards depend on recipe target and active cold-crash state.
