# BrewAssistant – projektläge och nästa steg, 20 september 2026

> **Statusdokument på `dev`, inte installerad kod eller en ny release.** Senaste [publicerade prerelease är beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14). Den taggades på commit `1a956c04044df870e005392b6bfe946097b9d440` och manifestet visar `0.2.0-beta.14`. Fysisk acceptans är **inte verifierad**. Exakt version installerad i användarens Home Assistant är okänd.

## Versions- och branchstatus

| Yta | Vid kontrollen före doc-sync | Betydelse |
| --- | --- | --- |
| `beta` | HEAD `1c117df7e817ab19c0ba06c7cf0e327421e95035`; innehåller beta.14 med read-only, ABORT och separata Manual-kort. | Efter publicerad beta.14-tagg följer en städcommit för ett engångsworkflow. En branch-HEAD är **inte** samma sak som release-taggen. |
| `dev` | HEAD `94b3dbe5f9f62c76d3f847184fad9400b12d3a17` före denna doc-sync; manifest `0.2.0-beta.13`; HLT SIM-1-diagnostik finns. | **Beta.14:s observe-only-kod finns inte på dev.** Dev och beta var divergerade: beta 67 commits före, dev två egna före dessa dokumentcommits. Gör en färsk [compare](https://github.com/Jocke1970/brewassistant-beta/compare/dev...beta), inklusive fil-diff, innan samordning. |
| `main` | HEAD `a6c0dda70e9732c4337d66b1ab2486d01761cc70`. | Ingen beta.14-promotion. |
| Automatiska tester | [PR #221](https://github.com/Jocke1970/brewassistant-beta/pull/221) anger gröna Python 3.11–3.13, HACS och Hassfest på exakt beta.14-merge-SHA samt isolerad HA/RCL-smoke på kodidentisk kandidat. | Inte fysisk kontroll. CI på `dev` triggas inte längre automatiskt; releasebranch, `beta`, `main` eller manuell körning krävs. Nya doc-commits är inte automatiskt testade. |

**Historiska beta.14-releaseanteckningar:** den [taggade filen](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/beta14-prerelease-notes_sv.md) har ännu förpubliceringsfrasen ”kandidat, inte publicerad”. Release- och tagguppgifterna ovan är verifierade efteråt och har företräde för nuläget. Flytta eller skriv inte om publicerad tagg för att rätta historik.

## Vad beta.14 faktiskt innehåller

`switch.brewassistant_brewzilla_observe_only` **PÅ** blockerar BA:s ordinarie/automatiska skrivningar till BZ men stänger inte av redan påslagen fysisk utrustning. **AV** kräver käll- och färskhetskontroll, HA-uppstart ska fail-closed. Gamla `switch.brewassistant_brewzilla_orchestration_enabled` har avvecklats och egna kort/automationer måste migreras. ABORT är separat och försöker STOP/OFF/0 även i read-only; tjänsteanrop eller HA `off` är **inte fysisk OFF-bekräftelse**.

Manual Brewday har ett separat [svenskt observationskort på beta.14-taggen](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only_sv.yaml) och [engelskt](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/dashboard/cards/brewzilla_observe_only.yaml), som monteras manuellt bredvid Manual-kortet. Direkt-RCL-reglagen är operatörskanal utanför BA-automationen; kortens synlighet är ingen global åtkomstspärr. Kontrollerna visas när BA är observerande, Manual-källa gäller, RAPT-profilen rapporterar `off` och ingen ABORT är aktiv. Den äldre Manual-panelens BA-ägda börvärden transporteras inte i observe-only. RCL-forkens beroende är `v0.5.0-beta.1`.

**Återstår för acceptans:** faktiskt installerad tagg, komplett BA/RCL-start i användarens HA, verkliga molnkommandon/readbacks, klicktest av egna kort, restart och read-only-växling samt oberoende fysisk verifiering av ABORT och maskinens värmare/pump/huvudström. Vattenprov endast under uppsikt med backup och separat fysisk avstängning. Ingen automatisk grön teststatus ger rätt att anta obevakad eller maltbaserad drift. [Issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) är öppen.

## HLT/Brewday – fältresultat och öppen avvikelse

[19 september](hlt-sim1-field-validation-2026-09-19.md) dokumenterar tidigare ramp-/färskhetsfynd. [Den separata rapporten 20 september](hlt-sim1-field-validation-2026-09-20.md) innehåller 44 giltiga JSONL-poster, fem virtuella HLT-ON-prover under RAPT-steget `Heat Strike` och tre **hypotetiska** konflikter omkring 3,7 kW mot 2,5 kW scenario. `physical_writes=false` och BZ-cap `null` i loggen är inte ett bevis för andra aktörers fysiska beteende. SIM-1 styr ingen fysisk HLT och begränsar aldrig BZ.

På `dev` tillåts `heat strike` som stage medan ramp-stegparsern **inte** känner igen exakt `step=Heat Strike`. Explicit positiv HLT-beredskap saknas som källoberoende kontrakt. Detta är en öppen process-/stegavvikelse, **inte en rättad kodbugg**. Brewday och HLT behöver definiera semantik, lägga regressionstester och omtesta en hel read-only-körning. 30 sekunders sampling och scenariobudget är inte elsäkerhet: fysisk HLT kräver separat snabb oberoende fail-OFF, verifierad fysisk OFF, rätt eldimensionering och torrkokningsskydd.

Loggen har virtuell HA-sensor `none`/`hlt`, men fyra runtime-ON-poster är ännu `none` i publicerad sensor; uppdateringsfördröjning förekommer. En tidigare skärmbild med `Okänt` är fortfarande inte entydigt förklarad. Kontrollera faktisk HA-entity och `_2`-suffix, installerad full kort-YAML och uppdateringstid. Saknad *fysisk* HLT-effektmätare ska fortfarande ge okänd fysisk mottagare.

## Prioriterat härifrån

1. **Rekonciliera beta.14 → dev som separat kodarbete.** Filgranska befintliga commits och bevara SG/CFC/Brewday och övriga parallella ändringar; ingen force-push, gammal feature-katalog eller omtaggning. Denna doc-sync backportar inte kod.
2. **Fysisk beta.14-acceptans endast med vatten och operatör:** verify install/tagg, källa, readbacks, inga bakgrunds-BA-skrivningar, separat Manual-direktreglage och fysiskt bekräftad ABORT. Skriv en ny daterad testpost; [issue #220](https://github.com/Jocke1970/brewassistant-beta/issues/220) hålls öppen innan acceptans.
3. **HLT/Brewday:** fastslå exakt HLT-startbehov och rampveto för `Heat Strike` och olika källor, kodfix + tests separat, nytt fullständigt simuleringsprov. Ingen fysisk HLT-koppling.
4. **UI:** verifiera `none` → `Ingen`, `hlt` → `HLT (virtuell)` i installerat kort och inventera gamla orchestration-referenser utan att skriva över privat dashboard.
5. **Dok-/branchstädning:** [draft PR #211](https://github.com/Jocke1970/brewassistant-beta/pull/211) beskriver äldre BZ-effektarbiter; markera som ersatt och merge:a inte direkt. Bevara egna dokument från extrabrancher innan radering.
6. Nästa kodrelease enligt [CONTRIBUTING](../CONTRIBUTING.md) med granskad `dev → beta` merge-commit, exakta CI-checks och **ny** tagg/version. `beta → main` först efter fälttest och beslut.

**Källor och ingångar:** [roadmap](roadmap.md), [publicerad beta.14](https://github.com/Jocke1970/brewassistant-beta/releases/tag/v0.2.0-beta.14), [PR #221](https://github.com/Jocke1970/brewassistant-beta/pull/221), [beta.14 release notes](https://github.com/Jocke1970/brewassistant-beta/blob/v0.2.0-beta.14/docs/beta14-prerelease-notes_sv.md), [HLT-rapport 20/9](hlt-sim1-field-validation-2026-09-20.md), [Brewday README](../custom_components/brewassistant/brewday/README.md) och [HLT README](../custom_components/brewassistant/hlt/README.md). Historiska fältrapporter och tidigare beta-releaser bevaras utan retroaktiv PASS-markering.

**Denna synk har enbart dokumentationsomfång på `dev`:** inga HA-åtgärder, kodfixar, branchmerge, promotion eller omtaggning.
