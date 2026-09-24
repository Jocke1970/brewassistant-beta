# GF30 → Brewfather: utgående fermenteringslogg

**Status 2026-09-22: planerad integrering, dokumentation endast.** Ingen sändare aktiveras eller ändras genom denna specifikation. Läs tillsammans med [GF30 temperatur/learning](gf30-thermal-control-learning.md) och [GF30 discovery-roadmap](grainfather-fermenter.md).

## Verifierat i källorna

- `fidley/grainfather_integration`: Grainfather Cloud pollas som standard var 300 s (5 min), med konfigurerbar uppdatering 60–3600 s. Den lokala GF30-regulatorn styr sin egen pump; den offentliga integrationens enheter/tjänster innebär inte att BA kan styra pump eller frys.
- Användarens `Jocke1970/brewfather`, branch `dev`, har **redan** en valbar Custom Stream-sändare i `custom_components/brewfather/coordinator.py`: vid vanliga coordinatoruppdateringar (konstant `UPDATE_INTERVAL = 900` s) hämtas en konfigurerad HA-temperatursensor och valfri SG-sensor och data postas. Sändaren är inte i GF30-backenden. Läs `const.py`, `coordinator.py`, `connection.py` och `config_flow.py` innan ändring. Forkens README beskriver BrewTracker-*tillägget* som read-only, men den ärvda integrationskoden har denna separata, valbara **utgående** Custom Stream-funktion. Dessa ska inte förväxlas.
- Brewfathers officiella Custom Stream: `POST https://log.brewfather.net/stream?id=<logging-id>`; högst **en loggning var 15:e minut per enhetsnamn**, tätare anrop ignoreras. Enhetens `name` är obligatoriskt. BF-stödda fält inkluderar `temp`, `aux_temp` (etikett Fridge Temp), `ext_temp` (etikett Room Temp), `gravity`, enheter och metadata. Källor: https://docs.brewfather.app/integrations/custom-stream och https://docs.brewfather.app/devices . För batchlogg måste den nyregistrerade stream-enheten knytas till den aktiva batchen; BF-dokumentationen anger loggning när batchen är Fermenting eller Conditioning.
- **Befintlig kod behöver härdas före drift för GF30:** `const.py` använder `http://log.brewfather.net/stream?id={}` snarare än HTTPS; `connection.py` skriver i debug ut full post-URL inklusive ID; `create_custom_stream_data()` kontrollerar numerisk sensorstate men inte verklig provtimestamp/färskhet, och sändning är kopplad till varje coordinator-refresh (även manuellt framtvingade/extra refresh). Nuvarande payload har bara primär temperatur plus eventuell SG, inte båda oberoende öltemperaturgivarna eller medium/frysluft. Ändra inte aktivt flöde utan granskning och test.

## Föreslaget ansvar, inga dubbla sändare

```text
GF30 Cloud var ~5 min → GF30 intern temp ─┐
RAPT Pill vid ny mätning → SG + Pill-temp ─┤
Frysluft + köldmedium ~1 min ─────────────┤
                                          v
                           BA read-only normalisering
                           mättid, källa, plausibilitet,
                           validitet + learning-historik
                                          |
                           *en* vald BF-exportadapter
                                          |
                           Custom Stream högst 1/15 min
                                          v
                                 Brewfather logg
```

Återanvänd helst den existerande stream-transporten i Brewfather-forken efter nödvändiga säkerhets-/färskhetsfixar; BA kan exponera tydliga, verifierade exportvärden, men ska inte dessutom posta direkt. Om vi senare väljer BA som transportägare måste den ärvda BF-sändaren först inaktiveras. Om RAPT Cloud redan loggar samma Pill till BF ska en tydlig exportpolicy förebygga två olika stream-enheter som dubbelregistrerar samma mätning. Inga återkopplingsloopar: BA:s SG-/temperaturregler utgår från originalsensorer, inte data BA just skickat till BF och sedan läst tillbaka.

## Rekommenderad tidsmodell

| Flöde | Frekvens / trigger | Villkor |
| --- | --- | --- |
| GF30 Cloud in | 300 s som utgångsläge | Verklig `last_heard`/provstid kontrolleras, API-uppdatering är inte automatiskt nytt mätprov. |
| Pill in | Vid verklig ny mätning | Egen provtimestamp/färskhet. |
| Frysluft/medium | Cirka 60 s eller sensorhändelse | Lokal termostat reagerar på sensorsignaler utan att invänta BF-synk. |
| BA thermal learning | Cirka 60 s, eller på giltiga händelser | Inga kommandon; lokala högupplösta prover sparas separat från BF. |
| BF Custom Stream ut | **Tidigast 900 s per stream-`name`**, bara vid giltiga prover | Separat sändklocka/monotont rate limit, även efter omstart och extra coordinator-refresh; första upptäckt/anslutning får inte leda till tät dublettsändning. |

BF:s 15-minutersregel är en **mottagningsgräns**, inte ett krav att GF30 eller köldmediet ska pollas så glest. Välj en stabil enhetsidentitet per fysisk batch/fermenter enligt BF:s dokumenterade enhetsmodell; batchkoppling måste kontrolleras före aktiv drift. Undvik att använda ett nytt enhetsnamn vid varje omstart, och planera avsedd historik över batchbyte.

## Datamappning (förslag, inte fastställd)

- `temp`: validerad **öltemperatur** med deklarerad källa, förslagsvis Pill vid korrekt kalibrering/färskhet. GF30-intern används samtidigt av BA som parallell sanningskontroll och för att flagga differenser; **ingen tyst medelvärdesbildning eller fallback** vid givarkonflikt.
- `gravity`: Pillens färska, plausibla SG om BF-export av SG är vald; annars utelämna. Verifiera om Pill redan skickas via RAPT→BF för att undvika dubbel loggning.
- `aux_temp`: BF visar detta som **Fridge Temp**. Endast efter ett explicit UI-beslut om semantik, till exempel frysluft. Köldmediet är *inte* frysluft; märk inte felaktigt. `ext_temp` visas som **Room Temp** och ska inte användas för att dölja en tredje eller fjärde öl-/köldmediegivare under fel namn.
- BF:s Custom Stream har en primär temperatur och två extra temperaturkanaler. För att behålla Pill, GF30 intern, frysluft **och** köldmedium som fyra separata, korrekt namngivna serier behövs en separat godkänd exportrepresentation, exempelvis en ytterligare unikt namngiven BF-enhet; v1 bör bara exportera tydligt semantiskt mappade fält och behålla full telemetry i BA.
- `temp_target` kan efter verifiering beskriva BA/GF30:s tillämpade öltemperaturmål; får inte antas vara samma sak som begärt receptmål utan verklig target-readback. Skicka inte okända eller stale värden.

## Transportsäkerhet, hälsa och test

1. Använd endast HTTPS; behandla `logging-id`/stream-URL som hemlighet: redigera inte in den i repo, attribut, issue eller debugloggar. Logga maskerade endpointuppgifter. Autentisering mot vanliga batch-REST-API:t är inte ett substitut för stream-ID.
2. Skapa separat exportstatus: enabled, configured, selected sender, last attempted, last HTTP success, last **eligible fresh sample**, last submitted sample ID/timestamp, destination name (utan ID), throttled/ignored och felorsak. HTTP 200 bevisar inte att BF placerat en punkt i rätt batch; verifiera loggpunkten i BF efteråt.
3. Färskhetsgrindar per fält; ingen påhittad temperatur, SG, interpolerad automatisk ersättning eller replay av gammeldata efter HA-omstart. Om nödvändigt prov saknas: avstå från sändning/utelämna fält enligt vald policy och visa orsak.
4. Säkerställ max en sändare per loggenhet, ingen burst vid omstart/refresh, ingen credential leak, korrekt °C/SG, korrekt batchkoppling, korrekt temperatursemantik och rapport vid anslutningsfel.
5. Gör detta som ett separat testat adapterarbete på `dev`; ingen cloud POST eller ändring av befintlig installation genom dokumentationssynk. Publicering, `beta` och `main` kräver egna beslut.

**Öppen designfråga:** om BF-forken eller en framtida fristående BA-exportadapter ska äga transporten. **Tills vidare rekommenderas återanvändning av BF-forkens enda existerande avsändare, efter fix för HTTPS/färskhet/rate limit; inga parallella POST-rutiner.**