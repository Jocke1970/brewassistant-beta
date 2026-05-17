# BrewAssistant Python Core v1.1 Release Notes

BrewAssistant Python Core v1.1 is a dashboard and branding polish release.

It remains read-only.

No climate, switch, fan, heater, fridge, relay or compressor actions are performed by Python Core v1.1.

---

## Added

```text
[x] Version bump to 1.1.0
[x] Branding guide for Home Assistant dashboard logo asset
[x] Install/update guide for Python Core
[x] Branded debug card with BrewAssistant logo support
[x] v1.1 test plan
```

---

## New files

```text
dashboards/cards/brewassistant_core_debug_card_v1_1.yaml
docs/python-core-branding.md
docs/python-core-install-update.md
docs/python-core-v1.1-test-plan.md
docs/python-core-v1.1-release-notes.md
```

---

## Logo asset

Repository source:

```text
pictures/BrewAssistant_color_small.png
```

Recommended Home Assistant path:

```text
/config/www/brewassistant/BrewAssistant_color_small.png
```

Dashboard URL:

```text
/local/brewassistant/BrewAssistant_color_small.png
```

---

## Dashboard card

New branded card:

```text
dashboards/cards/brewassistant_core_debug_card_v1_1.yaml
```

Existing cards remain available:

```text
dashboards/cards/brewassistant_core_debug_card.yaml
dashboards/cards/brewassistant_core_debug_card_v1.yaml
```

---

## Safety boundary

v1.1 does not add hardware control.

It only updates versioning, documentation and dashboard branding/polish.
