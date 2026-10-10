# BrewAssistant 0b7/dev – färgade START-preflightchips

Status: **utvecklingskandidat i dev**, inte en fysisk testacceptans.
0b6-beta och main lämnas orörda.

## Princip

START-knappen ska inte säga bara **VÄNTAR PÅ SYSTEM** utan också visa
vilken konkret källa/identitet/readback som blockerar. Backend levererar
`sensor.brewassistant_brewday_start_status` attributet `checks`
som en lista med:

- `id`: stabilt maskinläsbart namn (`source`, `session`, `step`, `target`, ...)
- `label`: kort etikett för chip
- `status`: `passed` (grönt), `pending` (gult), `warning` (gult), `failed` (rött)
- `detail`: fullständig mänskligt läsbar beskrivning (tooltip + blockeringslista)
- `blocking`: backend använder samma status för att avgöra om START får gå vidare;
  `warning` med `blocking: false` är *enbart diagnostik*.

Chips omfattar ABORT, fallback/resync, RCL-källa, aktiv RAPT-profil,
RAPT-färskhet, profil-/sessions-ID, steg-ID, target, BZ-telemetri,
BZ-ström, BZ-temperatur/target, värmeutgång, pumputgång, BA READ-ONLY
och separat operatörsbekräftelse.

## Verifierat steg-ID ersätter opålitlig textjämförelse

0b6 jämförde `runtime.step` mot `profile.step_name` med stränglikhet.
Det blockerade `Heat Strike` vs `Heatstrike` trots att samma
profil-/sessions-/steg-ID och target var verifierade.

Ny backend kräver strikt att:

1. BA är i `RCL Brewing` och `source=RAPT BrewZilla Profile`.
2. Aktiv RCL profilsensor är unik, matchar runtimens `source_entity` och
   rapporterar komplett kontrakt och färsk status.
3. BA runtimens `profile_id` och `profile_session_id` matchar RCL-profilsensorn.
4. BA runtimens `profile_step_id` matchar RCL:s `step_id`, båda är ifyllda.
5. BA:s target och RAPT-stegmålet är inom 0,3 °C.
6. Alla BZ-sensorer, utgångar och utilization är verifierat färska;
   BZ huvudström är PÅ, läsbara siffror är giltiga, ABORT/fallback spärrar saknas.
7. READ-ONLY är PÅ tills operatören uttryckligen bekräftar START.

**Stegnamn används inte för säkerhetsauktoritet.** När ID matchar men
visningsnamnet skiljer visas ett gult **Stegnamn**-chip, med båda texterna.
Om ID skiljer eller saknas blir **Bryggsteg rött/gult** och START blockeras.

## Säkerhetsgräns

- Inga chips är aktiva kontrollknappar. De kan inte skicka BZ-kommandon.
- Grön START kräver alla blockerande checks godkända samt separat fysisk
  inspektion och operatörsbekräftelse i HA.
- Rött på START-knappen efter GO är en sessionsstatus, inte ABORT.
  ABORT är alltid separat och högst prioriterad.
- En chipstatus eller färskt HA-tillstånd certifierar aldrig fysisk OFF.
- START kan bara aktivera BA Assist på en **redan aktiv, verifierad**
  RAPT-profil; inaktiv RAPT-start och MB/BF-BT är fortsatt oimplementerade.
- Hela SV/EN-korten finns i `dashboard/cards/brewday_control_status_sv.yaml`
  och `dashboard/cards/brewday_control_status.yaml`.
