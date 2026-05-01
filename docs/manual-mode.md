# Manual Mode

Manual Mode is a standalone BrewAssistant module for fermentation tracking without Brewfather, RAPT or automated gravity sensors.

It is useful for:

- Cider.
- Jäshink / bucket fermentation.
- Small test batches.
- Hydrometer-only batches.
- Batches where automated sensors are not available or not trusted.

---

## Purpose

Manual Mode should answer:

- What am I fermenting?
- Is the batch active?
- What was the latest gravity reading?
- Is gravity stable?
- Is the batch close to target FG?
- What should I do next?
- Has the batch been packaged?

---

## Recommended helpers

```text
input_boolean.brew_manual_batch_active
input_boolean.brew_manual_batch_packaged
input_text.brew_manual_batch_name
input_text.brew_manual_batch_notes
input_number.brew_manual_original_gravity
input_number.brew_manual_current_gravity
input_number.brew_manual_previous_gravity
input_number.brew_manual_target_gravity
input_datetime.brew_manual_started_at
input_datetime.brew_manual_last_reading_at
input_datetime.brew_manual_packaged_at
```

Existing installations may currently use simpler names like:

```text
input_boolean.manual_batch_active
input_boolean.manual_batch_packaged
input_text.manual_batch_name
```

Either naming style can work, but the v4 direction is to use the `brew_manual_*` namespace.

---

## Recommended sensors

```text
sensor.brew_manual_status
sensor.brew_manual_next_step
sensor.brew_manual_gravity_delta
binary_sensor.brew_manual_gravity_stable
binary_sensor.brew_manual_ready_for_packaging
```

---

## Suggested workflow

### 1. Start batch

Set:

```text
Batch active = on
Batch packaged = off
Batch name = current cider/beer name
Started at = now
```

### 2. Record original gravity

Use hydrometer or refractometer correction as appropriate.

### 3. Check fermentation periodically

For cider or simple manual fermentation:

```text
Check visually during active fermentation.
Take SG readings when activity slows down.
Avoid opening the fermenter unnecessarily.
```

### 4. Record gravity readings

When taking a new reading:

```text
previous_gravity = old current_gravity
current_gravity = new reading
last_reading_at = now
```

### 5. Confirm stability

A conservative rule:

```text
If current SG and previous SG are nearly the same
and readings are at least 24 hours apart
and SG is close to target FG
then fermentation is probably complete.
```

### 6. Package

When packaged:

```text
Batch packaged = on
Batch active = off or keep active until archived
Packaged at = now
```

---

## Dashboard recommendations

A Manual Mode card should include:

- Batch name.
- Active/packaged state.
- Current SG.
- Previous SG.
- Target FG.
- Gravity delta.
- Last reading time.
- Next recommended action.
- Buttons for start/reset/package.

---

## Notes for cider

For cider, avoid excessive opening during active fermentation.

A practical rhythm:

```text
First days: check airlock/visual signs only.
After activity slows: take SG reading.
Next day or two: take another SG reading.
If stable and near expected FG: fermentation is likely complete.
```

---

## Safety and quality reminders

Manual Mode should remind the user to:

- Sanitize sampling equipment.
- Avoid oxygen exposure when possible.
- Avoid pressure in equipment not rated for pressure.
- Confirm fermentation completion before bottling with fermentable sugar.

