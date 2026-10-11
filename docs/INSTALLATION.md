# Installation och uppdatering – BrewAssistant Beta

**Senast uppdaterad: 2026-10-11.** Gällande installerbar beta är
**[BrewAssistant 2026.10.0b11](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v2026.10.0b11)**,
GitHub **Pre-release** med integrationsmanifest `2026.10.0b11`. Installera inte
`dev` eller en enskild feature-/releasebranch för fysiskt styrprov.

**Kontrollkedja för RAPT-bryggning:**
`BrewAssistant → RAPT Cloud Link → BrewZilla`.
BrewAssistant får inte ta över en aktiv RAPT-profil vid RCL-bortfall.
Stabil `main` och gamla publicerade taggar påverkas inte av beta-uppdateringar.

## 1. Före installation

1. Stoppa ny bryggning, arbeta **inte under aktiv eller obevakad värmning**.
   Använd lokal kontroll och säkra vatten-/vätskenivåer.
2. Säkerhetskopiera HA och befintlig `/config/custom_components/brewassistant/`
   utanför `custom_components`.
3. Säkerställ en fungerande **RAPT Cloud Link 2026.10.0b5** för RAPT:s
   aktuella profil-, timer- och tillsatsattribut. RCL har egen kontakt med
   BrewZilla och behåller den fysiska profilsessionen.
4. Notera faktiska entity-ID:n under **Utvecklarverktyg → Tillstånd**.
   Egen entity registry och tidigare installationshistorik kan ge andra ID:n.

## 2. Rekommenderad HACS-installation

1. Lägg till `https://github.com/Jocke1970/brewassistant-beta` som
   **Custom repository → Integration** i HACS om det inte redan finns.
2. Öppna **BrewAssistant Beta**, visa beta/prerelease-versioner och välj
   uttryckligen **2026.10.0b11**.
3. Kontrollera att HACS-versionen och
   `custom_components/brewassistant/manifest.json` motsvarar `2026.10.0b11`.
4. **Starta om Home Assistant** så att uppdaterad Python-backend laddas.
5. Kontrollera integrationslogg, tillgängliga sensorer, RCL-profilstatus,
   READ-ONLY och ABORT-latch **innan** någon övervakad testkörning.

**Observera:** HACS installerar integrationskoden, **inte** dina manuellt
inklippta Lovelace-kort. Filer under `dashboard/cards/` måste bytas var för sig
med hela aktuella YAML-kortet.

## 3. Alternativ manuell installation – exakt låst tagg

Använd en **ny tom temporärkatalog**, backa upp först och kontrollera
källan innan du använder `rsync --delete`. Kör endast när bryggningen
är inaktiv:

```bash
git clone --depth 1 --branch v2026.10.0b11 \
  https://github.com/Jocke1970/brewassistant-beta.git \
  /tmp/brewassistant-2026.10.0b11

mkdir -p /config/brewassistant_backups/custom_components

if [ -d /config/custom_components/brewassistant ]; then
  cp -a /config/custom_components/brewassistant \
    "/config/brewassistant_backups/custom_components/brewassistant_$(date +%Y%m%d_%H%M%S)"
fi

# Inspektera filerna. --delete tar bort filer i målet som saknas i taggen.
rsync -a --delete \
  /tmp/brewassistant-2026.10.0b11/custom_components/brewassistant/ \
  /config/custom_components/brewassistant/
```

Kontrollera versionsfältet `2026.10.0b11` i målmanifestet, starta om HA
och verifiera samtliga käll-/säkerhetsspärrar. En PR-merge eller uppdaterad
GitHub-branch uppdaterar **inte** automatiskt installerad kod.

## 4. Uppdatera svenska premiumkort

Hämta **hela** kortet från den tagg som matchar din installerade backend.
För 0b11 är relevanta exempel:

- [Brewday Control/Status SV](https://github.com/Jocke1970/brewassistant-beta/blob/v2026.10.0b11/dashboard/cards/brewday_control_status_sv.yaml)
- [RAPT Profile Runtime SV](https://github.com/Jocke1970/brewassistant-beta/blob/v2026.10.0b11/dashboard/cards/rapt_profile_runtime_sv.yaml)
- [Flight Recorder SV](https://github.com/Jocke1970/brewassistant-beta/blob/v2026.10.0b11/dashboard/cards/brewassistant_brewday_event_log_sv.yaml)

Engelska motsvarigheter finns utan suffixet `_sv`.
Vanliga beroenden är `custom:button-card`, `custom:expander-card` och
andra frontendkort som anges i respektive YAML. **Montering är manuell.**

Kontrollera före användning:
- `sensor.brewassistant_brewday_runtime_summary`,
  `sensor.brewassistant_brewday_start_status` och aktuell RCL-profilsensor.
- `switch.brewassistant_brewzilla_observe_only` eller dess **verkliga**
  entity-ID om din entity registry fortfarande använder äldre namn.
- `button.brewassistant_abort_brewday` och
  `button.brewassistant_rearm_brewday_control`, där återaktivering endast
  används efter fysisk kontroll och en faktisk ABORT-latch.
- Flight Recorders `archive_path` och `archive_status`.

Öppna [dashboard-guiden](../dashboard/README.md) för fullständiga kort och
[0b11-releasenoterna](2026.10.0b11-prerelease-notes_sv.md) för UI-ändringar.

## 5. Safety-first test efter uppdatering

**0b11 BOIL:** endast verifierat *aktuellt* BOIL-steg tillåter BA att begära
**heat-utilization 100 %, pump OFF och pump-utilization 0 %** via RCL, under
befintliga authority-, readback- och supervised-apply-spärrar.
`heat-utilization 100 %` är **inte** ett separat heater-ON-kommando.

**Viktigt för BOIL:** BrewZillas egna fysiska reglergivare ska växlas
**manuellt från BLE till intern vörttemperatur** innan kokning, och
RAPT-profilens pumpbeteende ska kontrolleras separat. RAPT/BrewZilla
äger fortfarande steg, timers och temperaturmål.

**CFC under de sista 15 minuterna:** 0b11 har **inte** ännu någon
BOIL-kvittens som startar cirkulationen. En separat förbättring finns
i [PR #300](https://github.com/Jocke1970/brewassistant-beta/pull/300);
den är utvecklingskod och ska **inte** blandas med installerad 0b11.
Använd ingen automatisk pumpstart baserad på en oviss RAPT-timer.

**RCL-bortfall:** BA slutar skicka nya normalstyrkommandon; bortfallet
innebär **inte** STOP, OFF eller utilization 0. Ägarskap, resync och
operatörskvittens avgör när normal styrning får återupptas.

**ABORT:** global operatörsåtgärd är separat och kan begära profil-STOP
och OFF/0 även om normal styrning är spärrad. Kontrollera verkligt
BrewZilla-readback och fysisk pump/värme – en lyckad HA-tjänst är inte
fysisk bekräftelse.

Testa **först med vatten och fysisk uppsikt**, inte obevakat med vört.
`main` uppdateras först efter separat fältacceptans.

## 6. Flight Recorder och äldre loggar

0b11 använder ett komplett **append-only JSONL-arkiv per bryggsession**
under `/config/brewassistant/logs/brewday-*.jsonl`. HA-sensorn visar
en kort sammanfattning. Tidigare recorder-sessioner var testkörningar:
0b11 nollställer **endast äldre Flight Recorder-metadata en gång** och
migrerar inte gamla historikfönster. Nya JSONL-sessioner bevaras över HA-omstarter.
**Gamla filer raderas inte automatiskt** av uppdateringen eller `Rensa vy`.

Dokumentation: [Flight Recorder](brewday-audit.md).

## 7. Äldre installationer, releasehistorik och brancher

Äldre beta.14/beta.15-guidningar, gamla lokala YAML-paket och deras
verkliga felrapporter är **historik**, inte installationsmål för aktuell beta.
Radera inte entity registry eller ändra `.storage` manuellt för att försöka
lösa gamla visningsnamn. Undvik parallella automationsvägar från gamla
`/config/packages/` om de kan skriva till samma hårdvara.

Versionsflödet är **`dev → beta → main`**. En version måste få egen ny tagg
och CI-verifiering; ingen gammal release/tagg får flyttas.
Se [SOP](../CONTRIBUTING.md) och [roadmap](roadmap.md).
