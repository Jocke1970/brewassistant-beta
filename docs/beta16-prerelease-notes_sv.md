# BrewAssistant 2026_10-03 — GF30 supervised target beta (v0.2.0-beta.16)

**Releasenamn:** `2026_10-03`  
**GitHub-tagg:** `v0.2.0-beta.16`  
**Integrationsmanifest:** `0.2.0-beta.16`  
**Releasekanal:** Pre-release / HACS

## Syfte

Beta.16 kopplar BrewAssistants fermentation tracking till den fältverifierade
GF30-targetytan utan att ge BrewAssistant direkt heater- eller cooling-pump-kontroll.

## Kontrollkedja

```text
fermentation_tracking
  -> rekommenderad öltemperatur
  -> Prepare GF30 Target
  -> Supervised Apply pending action
  -> explicit CONFIRM
  -> grainfather.set_controller_target_temperature(confirm=true)
  -> Grainfather MQTT readback
  -> verified
```

BrewAssistant publicerar aldrig rå MQTT till GF30. Grainfather-integrationen äger
command 0, transport, bounded target-write och readback-verifiering.

## Nya entiteter

- `button.brewassistant_gf30_prepare_target`
- `sensor.brewassistant_gf30_target_apply_state`
- `sensor.brewassistant_gf30_recommended_target`
- `sensor.brewassistant_gf30_controller_target`
- `sensor.brewassistant_gf30_target_delta`

Befintlig `button.brewassistant_confirm_supervised_apply` används för kvittens.

## Säkerhetsgräns

- GF30 äger heater och automatisk cooling-pump.
- Direkt heater/cooling från BrewAssistant är DISABLED.
- Target-write är CONFIRM-only.
- En GF30-plan får inte skriva över en pending action från annan backend.
- Live-rekommendationen återvalideras precis före write.
- BrewAssistant räknar inte åtgärden som utförd utan verifierad extern readback.
- Coolant/freezer-spåret är fortsatt separat och read-only.

## Releasegrind

Promotion sker som merge commit `dev → beta`.
CI, HACS och Hassfest ska vara gröna på exakt beta-merge-SHA före taggning.

**beta-merge-SHA:** fylls med den verifierade beta-SHA:n efter promotion.

Home Assistant-omstart krävs efter HACS-uppdatering eftersom nya
integration-owned sensorer, button och supervised executor registreras.
