# BrewAssistant Beta

**Home Assistant-integration för Brewday, BrewZilla/RAPT, Brewfather, manuell bryggning, kylning, jäsning, servering och Flight Recorder.**

> **Aktuell publicerad testversion: [2026.10.0b11](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v2026.10.0b11)** (11 oktober 2026). HACS **Pre-release**, inte fysisk acceptans eller en stable-release. För fullständig ändringslista, läs [0b11-releasenoterna](docs/2026.10.0b11-prerelease-notes_sv.md) och [CHANGELOG](CHANGELOG.md).
>
> **Nästa utvecklingsarbete:** [PR #300 – CFC/kylspiral med operatörskvittens under BOIL](https://github.com/Jocke1970/brewassistant-beta/pull/300). Denna ändring är **inte en del av 0b11**, och någon ny beta har inte publicerats för den.

## Arkitektur och kontrollägarskap

Den ordinarie kedjan vid aktiv BrewZilla/RAPT-profil är:

```text
BrewAssistant (beräknar/kvitterar tillåten assistans)
    → RAPT Cloud Link (Home Assistant-entiteter/tjänster)
    → BrewZilla (RAPT äger aktuell profil, steg, timer och target)
```

- BrewAssistant använder **inte någon parallell direktstyrning** av BrewZilla vid RCL Brewing.
- RAPT/RCL förblir ägare av en redan startad profil även om BA tappar RCL. **RCL-bortfall är aldrig liktydigt med STOP**. BA skickar då inte automatiskt heater OFF, pump OFF, utilization 0, profil-STOP eller step-advance.
- Normala BA-kommandon kräver verifierad källa, identitet, färsk observation, fysiska readbacks och rätt **READ-ONLY/supervised-apply-/ABORT**-tillstånd.
- **ABORT/NÖDSTOPP** är en uttrycklig, separat operatörsåtgärd; HA-kommandokvittens är inte bevis för att hårdvaran verkligen är avstängd.
- `Manual Brewing`, `Brewfather Brewing` och `RCL Brewing` är olika processlägen. Vid tappad extern källa kan BA behålla läsbar ManualPlan/receptkontext, men den får **inte tyst ta över fysisk styrning** utan verifiering och kvittens.

Design och historik: [trelägesmodell och RCL Assist](docs/brewday-three-mode-rcl-assist-2026-10-09_sv.md), [RAPT-runtime](docs/rapt-brewzilla-profile-runtime.md) och [Brewday execution modes](docs/brewday-execution-modes.md).

## Vad som ingår i 2026.10.0b11

| Område | Aktuell testfunktion | Viktig begränsning |
| --- | --- | --- |
| **BOIL** | Aktuellt verifierat BOIL-steg: **heat-utilization 100 %**, **pump OFF/0 %** via ordinarie RCL-guardad väg | 100 % är ett effekttak, **inte heater ON**. Byt BrewZillas fysiska reglergivare manuellt från BLE till intern inför kokning. |
| **Brewday UI** | Premium operatörspanel synlig när kvittens/åtgärd behövs; ABORT alltid tillgänglig | Manuell Lovelace-YAML uppdateras **inte** av HACS. |
| **RAPT-profiltider** | Planerad steglängd och konservativ, ungefärlig nedräkning när en giltig stegstart kan observeras | Ingen påhittad timer vid osäker Start-/Target-/manuell tid. Kräver RCL `2026.10.0b5` för aktuella profiler/tillsatser. |
| **Flight Recorder** | Append-only JSONL per bryggsession, utan 250-radersgräns i arkivet | Gamla testloggar migreras inte. Tidigare filer raderas inte automatiskt; HA-sensorn är en lätt statusvy. |
| **Cooling/CFC** | Separat kylbackend och CFC-verktyg, inklusive BLE-temperatur när konfigurerat | **BOIL-kvittens för CFC sista 15 minuterna finns ännu bara i PR #300.** |
| **HLT** | SIM-1: virtuell effektbudget och passiv observation | Ingen fysisk HLT-styrning eller verifierad elsäkerhet. |

**Installation:** [docs/INSTALLATION.md](docs/INSTALLATION.md). **Fälttest:** börja med vatten och fysisk uppsikt. CI/HACS/Hassfest och isolerad HA/RCL-smoke på beta-merge-SHA var **7/7 gröna** inför taggen `v2026.10.0b11`; det ersätter **inte** ett verkligt vattenprov.

## HACS och Lovelace

HACS-källan är `Jocke1970/brewassistant-beta` (kategori **Integration**). Installera en uttryckligt vald **GitHub Pre-release**, inte `dev` eller ett okontrollerat branch-HEAD.

Efter backenduppdatering: säkerhetskopiera först och starta om HA. Kort under `dashboard/cards/` är **manuella** exempel. För svensk 0b11:
- `dashboard/cards/brewday_control_status_sv.yaml`
- `dashboard/cards/rapt_profile_runtime_sv.yaml`
- `dashboard/cards/brewassistant_brewday_event_log_sv.yaml`

Montera hela kortfiler och kontrollera verkliga entity-ID:n. Se [dashboard/README](dashboard/README.md) och [dashboard-baselines](docs/dashboard-baselines.md).

## Brancher, SOP och dokumentationsstatus

```text
dev (utveckling och dokumentation)
   → beta (HACS-testversioner med unik tagg och prerelease)
   → main (stabilt först efter separat fältacceptans)
```

`main` representerar den tidigare stabila kodbasen; 0b11 är **inte** promoterad dit. `beta` och den publicerade `v2026.10.0b11` är distinkta begrepp: taggen är låst mot en testad commit. Släpp aldrig en ny beta genom att flytta en gammal tagg.

Nästa arbete ska gå via `dev` och en separat ny version efter godkännande och tester. Läs [CONTRIBUTING.md](CONTRIBUTING.md), [roadmap](docs/roadmap.md) och [Flight Recorder](docs/brewday-audit.md).

## Dokumentationskarta

| Ämne | Källa |
| --- | --- |
| Aktuell installerbar beta och begränsningar | [0b11 release notes](docs/2026.10.0b11-prerelease-notes_sv.md) |
| HACS-installation, HA-omstart, fullständiga YAML-kort | [INSTALLATION](docs/INSTALLATION.md) |
| Nya CFC-knapparna (under utveckling, **inte 0b11**) | [PR #300](https://github.com/Jocke1970/brewassistant-beta/pull/300) och PR:ns `docs/boil-cfc-15min-ack_sv.md` |
| Flight Recorder / JSONL | [brewday-audit](docs/brewday-audit.md) |
| BrewZilla/BOIL | [0b11 BOIL-kontrakt](docs/2026.10.0b11-boil-pump-off-zero_sv.md) |
| Fysisk kontroll och planerade milstolpar | [roadmap](docs/roadmap.md) |
| Kylning, jäsning och GF30 | [backends](docs/backends/README.md) |
| Tidigare valideringshistorik och äldre beta-versioner | [historiska noteringar](docs/doc-sync-2026-09-24_sv.md) |

Äldre daterade testprotokoll och publicerade releaseanteckningar är **historiska underlag**, inte instruktioner för aktuell installation. Ändra aldrig tidigare resultat retroaktivt till PASS.
