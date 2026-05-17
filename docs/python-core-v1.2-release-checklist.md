# BrewAssistant Python Core v1.2 Release Checklist

v1.2 is a packaging and release cleanup milestone.

It does not add hardware control.

---

## Release readiness

```text
[ ] Home Assistant loads integration without errors
[ ] Core version reports 1.2.0
[ ] Source health reports OK or useful warning
[ ] Runtime source reports OK or useful warning
[ ] Next recommended action works
[ ] Options flow opens
[ ] Saving options reloads cleanly
[ ] Active branded dashboard card renders
[ ] Legacy debug cards are archived or removed from active dashboard
```

---

## Documentation readiness

```text
[x] README documents Python Core v1.1 stable baseline
[x] Install/update guide exists
[x] Branding guide exists
[x] v1.1 release notes exist
[ ] v1.2 release notes exist
[ ] BIAB and Manual Fermentation migration plan exists
[ ] PR / merge checklist exists
```

---

## Merge readiness

```text
[ ] Decide whether feature/python-core-v0.1 should merge to main
[ ] Confirm no experimental hardware-control code is included
[ ] Confirm old dashboard cards are archived, not active
[ ] Confirm README points to current recommended card
[ ] Confirm release notes mention read-only safety boundary
[ ] Optional: create GitHub release/tag after merge
```

---

## Safety boundary

Python Core remains read-only.

No climate, switch, fan, heater, fridge, relay or compressor actions are performed by Python Core.
