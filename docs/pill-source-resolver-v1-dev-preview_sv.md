# Pill Source Resolver v1 — dev-only read-only preview

## Atomic integration selection

**Invariant:** SG and temperature always come from the same integration. Never mix BLE SG with Cloud Link temperature or the reverse.

Current provisional entity mapping (field confirmation still required):

| Candidate | Temperature | SG |
|---|---|---|
| BLE | `sensor.yellow_pill_temperature_2` | `sensor.yellow_pill_specific_gravity` |
| Cloud Link | `sensor.yellow_pill_temperature` | `sensor.yellow_pill_gravity` |

Read-only outputs: `sensor.brewassistant_pill_active_source`, `sensor.brewassistant_pill_status`, `sensor.brewassistant_pill_temperature`, `sensor.brewassistant_pill_gravity`.

The source indicator in `dashboard/cards/fermentation_cockpit_v2_sv.yaml` shows one common Bluetooth/Wi-Fi icon, never per-metric badges. Expandable diagnostics show normalized preview values.

## Current safety limitations

- Preliminary freshness check uses Home Assistant `last_updated`, **not actual Pill measurement time**; this is a conservative proxy, but unchanged temperature may be rejected incorrectly.
- Cloud Link may repeatedly publish cached readings; `last_reported` **must not** be treated as a physical sample timestamp.
- A Cloud Link `Disconnected` state disqualifies its entire pair.
- Both SG and temperature must be available, within numeric bounds, and updated within 20 minutes. Battery is not an eligibility input yet.
- Källvalet sparas mellan coordinator-ticks i HA-minne. Vid aktiv Cloud Link krävs två distinkta BLE-observationer innan återgång; samma uppdatering räknas inte flera gånger. Tillståndet återställs vid integrationens omstart.
- En explicit tidsstämpel i `measurement_time`, `observed_at`, `last_measurement` eller `last_sample` prioriteras om integrationen tillhandahåller den. Annars används fortfarande `last_updated` som proxy. `last_reported` får aldrig användas som nytt mätbevis.
- Preview entities are **not connected** to fermentation controller, supervisor, runtime tracking or Brewfather stream. `safe_for_control: false` on diagnostics is intentional.
- `provisional` means the pair passed state-level checks, **not** that a physically new measurement was verified.

## HA field verification checklist

1. Verify which integration and physical Pill owns each entity ID.
2. Observe BLE temperature updates while SG changes; inspect integration behavior for repeated unchanged values.
3. Confirm Cloud Link disconnection versus cached/resent data.
4. Test BLE-only, Cloud-only, both stale, disconnect and reconnect.
5. Verifiera att integrationsspecifika tidsstämplar motsvarar fysisk mätning, testa återgångshysteres i HA och lägg till automatiserade tester.
6. Only after those pass, plan separate approval for connecting runtime, Brewfather and supervised control. Do not promote dev to beta/main yet.
