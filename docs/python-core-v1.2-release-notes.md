# BrewAssistant Python Core v1.2 Release Notes

BrewAssistant Python Core v1.2 is a packaging and release cleanup milestone.

It remains read-only.

No climate, switch, fan, heater, fridge, relay or compressor actions are performed by Python Core v1.2.

---

## Added

```text
[x] v1.2 release checklist
[x] Module migration plan for BIAB and Manual Fermentation
[x] README updated for Python Core v1.1 stable baseline
```

---

## Module migration direction

Recommended next module:

```text
BIAB Python v0.1 read-only calculations
```

Manual Fermentation should remain helper/UI-driven for now and later receive a read-only Python summary/bridge layer.

---

## New files

```text
docs/python-core-v1.2-release-checklist.md
docs/module-migration-plan.md
docs/python-core-v1.2-release-notes.md
```

---

## Safety boundary

v1.2 does not add hardware control.

It only adds packaging, documentation, release cleanup and module migration planning.
