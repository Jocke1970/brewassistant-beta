# Installation – BrewAssistant Beta

**Uppdaterat 2026-09-24.** Nästa prerelease är `v0.2.0-beta.15`; installera den först när den är publicerad som GitHub Pre-release efter gröna checks på exakt `beta`-merge-SHA. Före publiceringen är [`v0.2.0-beta.15`](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.15) senaste publicerade tagg. `dev` är utveckling, `beta` testgren och `main` stabil gren. Beta.15 tillför GF30 read-only/preflight men **ingen fysisk GF30-/pump-/frysstyrning**.

## Rekommenderat: HACS som anpassat repository

1. I HACS: öppna Custom repositories och lägg till `https://github.com/Jocke1970/brewassistant-beta`, kategori **Integration**.
2. Installera BrewAssistant Beta och välj uttryckligen prerelease **v0.2.0-beta.15** via HACS versionsval om den inte är förvald. Kontrollera visad version före och efter installation; använd inte ett ospecificerat branch-HEAD.
3. Ta säkerhetskopia, kontrollera kompatibel RAPT Cloud Link-fork `v0.5.0-beta.1`, installera/uppdatera när BrewZilla inte används och starta om Home Assistant.
4. Lägg till integrationen via Inställningar → Enheter och tjänster om den inte redan finns. HACS lägger integrationskoden under `/config/custom_components/brewassistant/` men installerar **inte** egna Lovelace-dashboardkort automatiskt.

## Manuell beta.15-installation (endast med uttryckligt versionsval)

Synka bara katalogen `custom_components/brewassistant/`, inte tidigare hela repositoryn eller en gammal featurebranch. Exempel i Home Assistants skal när maskinen är inaktiv:

```bash
git clone --depth 1 --branch v0.2.0-beta.15 \
  https://github.com/Jocke1970/brewassistant-beta.git /tmp/brewassistant-beta15
mkdir -p /config/brewassistant_backups/custom_components
if [ -d /config/custom_components/brewassistant ]; then
  cp -a /config/custom_components/brewassistant \
    "/config/brewassistant_backups/custom_components/brewassistant_$(date +%Y%m%d_%H%M%S)"
fi
# Granska källan och backupen före synk: --delete tar bort filer i mål som saknas i taggen.
rsync -a --delete \
  /tmp/brewassistant-beta15/custom_components/brewassistant/ \
  /config/custom_components/brewassistant/
```

Använd en tom temporär klonkatalog; om sökvägen redan finns, välj en ny. Kontrollera därefter att `/config/custom_components/brewassistant/manifest.json` anger `0.2.0-beta.15` och starta om HA. Följ vanlig backup-/rollbackrutin vid fel. En GitHub-branchmerge uppdaterar aldrig installerad Home Assistant-kod.

## Kontroll efter omstart

Sök under Utvecklarverktyg → Tillstånd och Inställningar → Enheter och tjänster → Entiteter (inklusive inaktiverade). Kontrollera bland annat:

- `sensor.brewassistant_brewzilla_orchestration_mode`
- `sensor.brewassistant_brewday_operator_control_state`
- `button.brewassistant_abort_brewday`
- `button.brewassistant_rearm_brewday_control`
- Den faktiska switchen med visningsnamn **Endast observation – BrewZilla styrs lokalt**.

**Känt beta.15-ID-fynd:** HA registrerade i en verklig installation `switch.brewassistant_endast_observation_brewzilla_styrs_lokalt` i stället för det avsedda `switch.brewassistant_brewzilla_observe_only`. Ändra entitets-ID genom HA:s entitetsinställningar, eller anpassa lokala kort efter faktiskt ID. Editera inte `.storage` manuellt. Detta är en **öppen kodfix**, inte korrigerat i den publicerade taggen. Avsaknad av switchen ska undersökas; anta aldrig att en felande entity innebär fysisk read-only.

Efter HA-start ska switchen vara PÅ och `sensor.brewassistant_brewzilla_orchestration_mode` ha `observe_only_effective: true` och `hot_side_actuator_writes_allowed: false`. Dessa anger endast att BA:s ordinarie skrivningar spärras; kontrollera fysiska utgångar lokalt. Kontrollera RCL:s anslutning och att återläsning är färsk innan styrprov; `Disconnected` är inte fysisk OFF-verifikation.

**Två separata handgrepp:** efter ABORT och fysisk kontroll tryck `button.brewassistant_rearm_brewday_control`, kontrollera `operator_abort_active: false` och `operator_control_state: armed`. Switch **AV** gör därefter sin egen atomiska kontroll av behörig källa + sex färska readbacks. Ingen separat observe-only-rearmtjänst behövs i normal UI. Med `source: None` eller gammal telemetri nekas styrning och read-only förblir PÅ. För manuellt vattenprov: behåll read-only PÅ, välj Manual Brewday och verifiera uttryckligt RAPT-profil-STOP.

## Dashboard

Kort under `dashboard/cards/` är exempel och behöver läggas till manuellt. För beta.15: lägg `dashboard/cards/brewzilla_observe_only_sv.yaml` (eller engelska motsvarigheten) **bredvid** det befintliga `brewassistant_manual_brewday_sv.yaml`. Kontrollera att dess entity-ID matchar faktisk installation. Kortet har ABORT och switch, med direkta RCL-reglage endast under villkoren read-only PÅ, källa Manual Brewday, RAPT-profil bekräftat stoppad och ingen ABORT. Visningsvillkor är inte ett globalt behörighetsskydd för andra direkt-RCL-kort. Rensa lokala referenser till avvecklade `switch.brewassistant_brewzilla_orchestration_enabled`.

Läs [testkontraktet](brewzilla-observe-only-test_sv.md), [dashboard-baselines](dashboard-baselines.md) och [dashboard/README](../dashboard/README.md). Vanliga frontendberoenden inkluderar `custom:button-card`, `custom:vertical-stack-in-card`, Mushroom, expander-card och övriga cards som respektive YAML-fil anger.

## Äldre YAML-paket och säkerhet

Äldre BrewAssistant-paket under `/config/packages/` eller `/config/packages_disabled/` är inte denna Python-integrations källa. Kör dem inte parallellt utan avsiktlig migrationsplan eftersom dubbla hjälpare och oanvändbara entity-ID kan uppstå. Ta bort övergivna entities via HA UI, aldrig genom direktmanipulation av `.storage`.

Beta.14:s ABORT försöker profil-STOP och OFF/0 men varken tjänstekvittens eller HA:s OFF är fysisk avstängningsgaranti. Kontrollera vattennivå, faktisk värme, pump, effekt och huvudström, håll lokal frånkoppling tillgänglig och använd inga obevakade testkörningar. Nästa praktiska acceptans är endast vattenprov; dokumentera nytt resultat innan någon promotion till `main`.

## GF30 beta.15 – första read-only kontrollen

Efter HA-omstart finns nya GF30-diagnostiksensorer och tjänster. Lämna de tre nya coolant/freezer-options-fälten tomma tills verkliga sensorer/termostat finns. Tomt är ett giltigt fail-passive läge.

För första vatten-/temperaturprovet:

1. Kör `brewassistant.gf30_clear_preflight`.
2. Ta en manuell temperaturmätning och kör `brewassistant.gf30_record_manual_temperature` med `temperature_c`, gärna `phase: baseline`.
3. Upprepa under `cooling` och senare `recovery`; BrewAssistant sparar samtidigt aktuell konfigurerad Pill-temperatur och dess timestamp.
4. Läs bland annat `sensor.brewassistant_gf30_preflight_status`, delta/rate-sensorer och `sensor.brewassistant_gf30_safe_point`.
5. Tolka allt som diagnostik. Ingen av dessa sensorer eller tjänster startar GF30-pump, frys eller temperaturändring.
