# Dokumentationssynk – BrewAssistant, 2026-10-11

## Kontrollens omfattning och resultat

**Gällande version:** `2026.10.0b11`, låst prerelease-tagg
`v2026.10.0b11`, publicerad 2026-10-11 från beta-SHA
`87d80316f53df8d46a7edf06114e8a96c902b186`.
**Gällande SOP:** `dev → beta → main`. Stable `main` behåller
sin tidigare commit och får inte uppdateras utan fälttest/acceptans.

| Dokument/område | Utfall |
| --- | --- |
| `README.md` | Aktualiserad release, RCL-ägarskap, 0b11/PR #300-gräns och dokumentationskarta |
| `docs/INSTALLATION.md` | Exakt installerbar tagg, RCL b5-beroende, HACS/manual installation, kompletta UI-kort och water-only |
| `docs/roadmap.md` | Ny daterad gällande status överst; septemberstatus kvar tydligt markerad som historik |
| `CONTRIBUTING.md` | Kalenderbaserad betatagg, merge-commit, exakt SHA och dev/beta/main |
| `CHANGELOG.md` | Faktiskt publicerad 0b11, med PR #300 markerad som separat opublicerad utveckling |
| `dashboard/README.md` | Aktuella SV/EN-kort och rätt RAPT/RCL-target- och timerägarskap |
| `docs/setup.md`, `docs/dashboard-baselines.md`, `docs/CLEAN_BASELINE.md` | Äldre guider tydligt begränsade till historiska kontroller; saknad `brewzilla_advice_auto.yaml` borttagen ur setup-listan |
| `docs/backends/cooling-backend.md`, `brewzilla-backend.md`, `docs/brewday-brewzilla.md`, `docs/rapt-brewzilla-profile-runtime.md` | Tydlig varning för äldre arkitektur och hänvisning till 0b11 |
| `docs/2026.10.0b11-boil-pump-off-zero_sv.md`, `docs/2026.10.0b11-operator-attention-visibility_sv.md` | Status korrigerad från 'endast dev / planerad' till publicerad 0b11 |
| `docs/brewday-three-mode-rcl-assist-2026-10-09_sv.md` | Gällande release/bortfallsprincip förklarad; äldre design bevarad |
| `docs/brewday-audit.md`, `docs/2026.10.0b11-prerelease-notes_sv.md` | Redan i linje med publikt 0b11; ingen retroaktiv omskrivning |

## Öppna avgränsningar

- **PR #300 – CFC-kvittens:** dess `docs/boil-cfc-15min-ack_sv.md`,
  service, sensor och kort finns bara i utvecklingsgrenen
  `feature/boil-cfc-15min-ack-20261011`. Den är **inte** del av
  den publicerade betan och får inte beskrivas som installerad.
- **Historiska dokument:** äldre daterade fältrapporter, gamla
  prerelease-noteringar och ursprungliga arkitekturrapporter är
  avsiktligt inte omskrivna till nutidsinstruktioner.
  Tidigare 'FAIL/ej verifierat' förblir sådant tills nya observationer finns.
- **Fysisk acceptans:** grön 7/7 release-CI för 0b11 är inte bevis
  på verklig pump/heat/ABORT-funktion.
- **Publicerad tagg och HACS:** befintlig tagg `v2026.10.0b11`
  är immutable. Dokumentationssynk på `dev` ändrar inte den taggen
  eller den installerade `beta`-distributionen.
  Nästa publicerade beta måste ha ett **nytt** kalenderbaserat versionsnummer.

## Bekräftelse av grenstädningen

Vid kontroll hade `main` försvunnit. Den återställdes på sin tidigare,
verifierade commit `a6c0dda70e9732c4337d66b1ab2486d01761cc70`
**utan** att ändra `dev`, `beta` eller publicerade taggar.

## Säkerhetskontrakt

```text
BrewAssistant → RAPT Cloud Link → BrewZilla
RAPT/RCL äger aktiv profil, steg, timer och target
Källbortfall → inga nya BA-kommandon, men inte STOP/OFF/0
READ-ONLY / supervised apply / identitet / readback / ABORT prioriteras
BOIL 0b11 → pump OFF/0 %, heat-utilization 100 % under gällande spärrar
BOIL CFC sista 15 min → endast utvecklings-PR #300
```

**Tolkning:** Denna uppdatering rättar *aktuella övergripande guider*,
men gör inte historiska dokument till nya fysiska testbevis.
