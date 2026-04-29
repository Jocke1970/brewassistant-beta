# BrewAssistant Notifications

BrewAssistant notifications are designed to be useful, quiet and module-aware.

The goal is not to notify about everything. The goal is to notify when a module is active and when the user actually needs to know something.

---

## Design Principles

### 1. Notifications follow active modules

Notifications should only be sent when the related BrewAssistant module is active.

Examples:

- Chamber notifications are only sent when the chamber module is active.
- Fermentation notifications are only sent during an active fermentation workflow.
- Hot-side notifications are only sent during an active hot-side / BIAB session.
- Serving or kegerator notifications are only sent when serving/storage mode is active.

This prevents BrewAssistant from sending irrelevant notifications while the system is idle.

---

### 2. Global notification master switch

A global master switch should control whether BrewAssistant may send notifications at all.

Recommended helper:

```yaml
input_boolean:
  brewassistant_notifications_enabled:
    name: BrewAssistant notifications
    icon: mdi:bell
```

When this helper is `off`, normal BrewAssistant notifications should be muted.

---

### 3. Module-aware notification guards

Each notification automation should check:

1. Global notifications are enabled
2. The relevant module is active
3. The event is relevant and actionable

Example condition for chamber notifications:

```yaml
condition:
  - condition: state
    entity_id: input_boolean.brewassistant_notifications_enabled
    state: "on"

  - condition: state
    entity_id: input_boolean.brewassistant_chamber_module_active
    state: "on"
```

Example condition for fermentation notifications:

```yaml
condition:
  - condition: state
    entity_id: input_boolean.brewassistant_notifications_enabled
    state: "on"

  - condition: state
    entity_id: input_boolean.brewassistant_fermentation_module_active
    state: "on"
```

---

## Recommended Module Helpers

```yaml
input_boolean:
  brewassistant_notifications_enabled:
    name: BrewAssistant notifications
    icon: mdi:bell

  brewassistant_chamber_module_active:
    name: Chamber module active
    icon: mdi:snowflake-thermometer

  brewassistant_fermentation_module_active:
    name: Fermentation module active
    icon: mdi:beer

  brewassistant_hot_side_module_active:
    name: Hot side module active
    icon: mdi:kettle-steam

  brewassistant_serving_module_active:
    name: Serving / kegerator module active
    icon: mdi:glass-mug
```

---

## Optional Warning Override

Some warnings may be important even when normal notifications are disabled.

Recommended helper:

```yaml
input_boolean:
  brewassistant_warnings_enabled:
    name: BrewAssistant warnings
    icon: mdi:alert-circle
```

Suggested behavior:

- Normal notifications require `brewassistant_notifications_enabled`
- Warning notifications require `brewassistant_warnings_enabled`
- Critical warnings may optionally bypass module activity, depending on the use case

Example warning condition:

```yaml
condition:
  - condition: state
    entity_id: input_boolean.brewassistant_warnings_enabled
    state: "on"
```

---

## Notification Categories

### Chamber Notifications

Used when the fermentation chamber or kegerator chamber is active.

Examples:

- Chamber temperature outside expected range
- Cooling has been active for unusually long
- Compressor short-cycle protection triggered
- Chamber target changed
- Fridge power draw indicates compressor activity
- Circulation fan failure or unexpected state

Recommended guard:

```yaml
condition:
  - condition: state
    entity_id: input_boolean.brewassistant_notifications_enabled
    state: "on"

  - condition: state
    entity_id: input_boolean.brewassistant_chamber_module_active
    state: "on"
```

---

### Fermentation Notifications

Used when a batch is actively fermenting.

Examples:

- Fermentation started
- Gravity is approaching target FG
- Gravity appears stable
- Ready for cold crash
- Cold crash started
- Ready for transfer
- Fermentation workflow state changed

Recommended guard:

```yaml
condition:
  - condition: state
    entity_id: input_boolean.brewassistant_notifications_enabled
    state: "on"

  - condition: state
    entity_id: input_boolean.brewassistant_fermentation_module_active
    state: "on"
```

---

### Serving / Kegerator Notifications

Used when the kegerator is in serving, carbonation or storage mode.

Examples:

- Carbonation timer complete
- Storage temperature reached
- Kegerator temperature outside range
- Fan circulation active
- Compressor activity abnormal

Recommended guard:

```yaml
condition:
  - condition: state
    entity_id: input_boolean.brewassistant_notifications_enabled
    state: "on"

  - condition: state
    entity_id: input_boolean.brewassistant_serving_module_active
    state: "on"
```

---

### Hot-Side Notifications

Used later for DigiBoil BIAB and BrewZilla RAPT workflows.

Examples:

- Strike water ready
- Add grain
- Stir mash
- Mash timer complete
- Mash-out step complete
- Lift BIAB bag
- Sparge step reminder
- Boil timer started
- Hop addition reminder
- Flameout reminder
- Chill wort reminder

Recommended guard:

```yaml
condition:
  - condition: state
    entity_id: input_boolean.brewassistant_notifications_enabled
    state: "on"

  - condition: state
    entity_id: input_boolean.brewassistant_hot_side_module_active
    state: "on"
```

---

## Suggested Default Behavior

| Area | Default |
|---|---|
| Global notifications | On |
| Warnings | On |
| Chamber notifications | Active only when chamber module is active |
| Fermentation notifications | Active only when fermentation module is active |
| Serving notifications | Active only when serving/kegerator module is active |
| Hot-side notifications | Active only when hot-side module is active |
| Idle mode | Silent, except selected warnings |

---

## Idle Mode

When BrewAssistant is idle:

- No normal workflow notifications should be sent
- No chamber/fermentation/hot-side reminders should be sent
- Optional warnings may still be sent
- Dashboard status should clearly show that notifications are idle/suppressed

Suggested UI text:

```text
Notifications: Idle
Reason: No active BrewAssistant module
```

---

## UI Recommendations

A future settings card may expose the notification state like this:

```text
BrewAssistant Notifications

Master notifications: On
Warnings: On

Active notification modules:
- Chamber: Active / Idle
- Fermentation: Active / Idle
- Serving: Active / Idle
- Hot Side: Active / Idle
```

The UI should show why notifications are or are not being sent.

Example:

```text
Fermentation notifications: Enabled
Reason: Fermentation module active
```

Or:

```text
Hot-side notifications: Muted
Reason: Hot-side module idle
```

---

## Implementation Notes

Recommended file:

```text
brewassistant_notifications.yaml
```

Recommended responsibilities:

- Define notification helper inputs
- Define notification scripts
- Define guarded notification automations
- Keep module-specific notification logic grouped clearly
- Avoid hardcoding notify targets where possible

Recommended script pattern:

```yaml
script:
  brewassistant_send_notification:
    alias: BrewAssistant - Send notification
    mode: queued
    fields:
      title:
        description: Notification title
      message:
        description: Notification message
    sequence:
      - condition: state
        entity_id: input_boolean.brewassistant_notifications_enabled
        state: "on"

      - service: notify.mobile_app_your_phone
        data:
          title: "{{ title }}"
          message: "{{ message }}"
```

Module-specific automations should still check whether their module is active before calling the notification script.

---

## Future Improvements

Potential future improvements:

- Per-module quiet hours
- Per-module severity levels
- Notification targets per module
- Persistent dashboard notification log
- Actionable mobile notifications
- Snooze notifications for a module
- Critical warning override
- Notification history sensor
- Last notification timestamp per module

---

## Summary

BrewAssistant notifications should be:

- Module-aware
- Quiet by default
- Actionable
- Easy to disable globally
- Able to send warnings separately
- Integrated with the active brewing workflow

Design rule:

> Notifications should follow the brewing process. The user should not have to manage notification noise manually.
