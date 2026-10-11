# BrewAssistant 0b8-dev – Operatören ska se nästa åtgärd direkt

**Status:** dev-kandidat, ingen beta-release eller fysisk säkerhetsacceptans.

## Varför

Under vattenprovet 2026-10-10 var RCL-källa/profil åter tillgänglig
medan BA stannade i `resync_required`. Operatören visste inte att
separat kvittens behövdes och upplevde väntan som långsam.
BA:s read-only/ABORT-skydd ska **inte** kringgås eller automatiskt hävas.

Manual Brewday-kortet försvann också när källa kunde vara `Manual Brewday`
men runtime fortfarande `idle`. Det gamla kortet krävde samtidigt
`None + idle` för PREPARE och `Manual Brewday + !idle` för arbetskortet.
Dessa tillstånd kan lämna hela vyn tom.

## Ny operatörs-UI

### Återanslutning – överst på Brewday Control

En **stor pulserande gul operatörspanel** ligger överst, före övriga
statuskort. Den visas när `sensor.brewassistant_brewday_runtime_state` är
`resync_required` **eller** attributet `resync_required: true` finns på
`sensor.brewassistant_brewday_runtime_summary`.

**Viktigt 0b8-fälttest / korrigering:** Lovelace `conditional`-kortets
`state`-villkor stöder inte attributjämförelsen från PR #274. Därför
använder operatörspanelen nu `custom:button-card` med en reaktiv
JavaScript-`styles.card.display`-kontroll (`triggers_update: all`).
Det täcker HA-omstart där runtime fortfarande är `idle` men den persistenta
reconnect-spärren väntar på kvittens. Vid hävd spärr blir panelens
`display: none` först när båda signalerna är falska.

Operatörens kvittens är fortfarande separat backendguardad; visning ger
**ingen** ny rätt att styra BrewZilla. Denna ändring är inte fältverifierad
i användarens Lovelace förrän kortet klistrats in och kontrollerats.
Den visar:

- **BA VÄNTAR PÅ DIG** när aktuella villkor för ACK ser klara ut.
  Annars **ÅTERANSLUTNING – KONTROLL KRÄVS**.
- Åtgärd: **KVITTERA ÅTERANSLUTNING** direkt på huvudpanelen.
- RCL/Brewfather-källa, RCL-session-ID, exakt känt steg, snapshotålder,
  blockeringsorsak och gröna/röda statuschips för ABORT, read-only,
  datafärskhet, steg och källa.
- Stor visuellt låst ACK-knapp om villkor saknas. Serviceanropet använder
  oförändrad guard och exakt RCL-session/steg, med separat HA-bekräftelse.
- Banner försvinner efter verifierad kvittens, **men read-only kvarstår**.
  Nästa operatörsåtgärd blir separat grön **AKTIVERA BA-ASSISTANS**.
- Vid `prefers-reduced-motion` pulserar inget; kontrast/etikett består.

ABORT-knappen är fortfarande ett separat alltid synligt nödkommando.
Ingen automatisk återaktivering eller direkt BZ-kontroll tillkommer.

### Manual Brewday – visas bara när det är relevant

Efter fältgranskning 2026-10-11 ska Manual Brewing **inte** visa en grå
`SPÄRRAD`-panel när RAPT/Brewfather äger bryggningen, när återanslutning
väntar på kvittens eller när ABORT/okänt källäge gör Manual otillgängligt.
Brewday Control visar redan aktuellt ägarskap, spärr och åtgärd.

Den översta Manual-panelen är ett `custom:button-card` med
`triggers_update: all` och ett reaktivt `styles.card.display`-uttryck:
- **Visas:** `FÖRBERED BRYGGDAG` när modulen är på, källan är
  `None` eller `Manual Brewday`, både Brewday och Manual-sessionen är
  `idle` och ingen extern RAPT/Brewfather-källa, fallback, resync eller ABORT
  finns. Förberedelse har en separat bekräftelse och **startar inte hårdvara**.
- **Visas:** `MANUAL BREWING · PÅGÅR` när en faktisk Manual-session kör
  utan extern ägarkonflikt och modulen är på.
- **Döljs:** när RCL/RAPT/Brewfather äger, en säkerhetsspärr ligger kvar,
  modulen är av, källan saknas/inte kan verifieras eller Manual ännu inte är
  redo. Inga tomma spärrkort ska ta dashboardutrymme.

Det befintliga processkortet för aktiv Manual-session har fortsatt separata
Lovelace-villkor och skyddas av backendspärrarna (#276). Visningslogik
är aldrig en rätt att skicka BrewZilla-kommandon: BA → RCL → BrewZilla,
READ-ONLY, ABORT och operatörsbekräftelse gäller oförändrat.

## 0b8 – kompakt READ-ONLY och tydlig tidsindikering

- READ-ONLY-panelen har ett explicit kompakt två-radersgrid med synlig
  sköldikon, tydlig rubrik och kort instruktion. Ett högt tomt ikonfält ska
  inte längre ta plats. Den enda tillåtna manuella tjänsten från denna panel
  är `switch.turn_on` för att aktivera observation, **aldrig** manuell
  `switch.turn_off`.
- Reconnect-panelens rubrik och kvittensindikation använder samma spärrvillkor
  som knappen: riktig `resync_required`, BA READ-ONLY, giltigt steg (inte
  `idle/unknown/none`), färsk data, verifierad källa/session och ingen ABORT.
  Backend avgör alltid slutligt.
- Under reconnect/fallback och annan uttryckligt osäker timer visas `—`
  i stället för ett falskt `0 min`. Manual RAPT-steg med säker källa visar
  fortfarande `MANUELLT`.
- Kontrollera båda språkvarianterna i faktisk Lovelace (inte bara YAML-parser).
  Backend-spärrar, RCL ägarskap och ABORT får inte kringgås av UI.

## Leverans och tester

Kompletta EN/SV-kort:

- `dashboard/cards/brewday_control_status_sv.yaml`
- `dashboard/cards/brewday_control_status.yaml`
- `dashboard/cards/brewassistant_manual_brewday_sv.yaml`
- `dashboard/cards/brewassistant_manual_brewday.yaml`

Regressionskontroll parsar YAML till rätt kortstruktur och kontrollerar
guardad ACK, källa, session, read-only, ABORT och Manual Prep.
JavaScript-mock kontrollerades för `Manual Brewday+idle` (PREPARE synlig/tillåten),
`resync_required` och aktiv RAPT (PREPARE blockerat),
ACK med färsk session (anrop möjlig), samt stale session (ingen ACK).

För att se ändringarna i Lovelace måste **hela de två kortens YAML**
ersättas om de installerats manuellt – HACS uppdaterar inte
automatiskt inklistrade kortdefinitioner.
