# BrewAssistant 0b6 — Premium START med säker preflight (dev-preview)

## Knappens fem lägen

| Läge | Färg/rörelse | Tryck |
| --- | --- | --- |
| `waiting` / `blocked` | Gult, långsam puls | Visa blockerande preflight-anledningar, **inga skrivningar** |
| `ready` | Grönt, långsam puls | Visa HA-bekräftelsedialog, därefter `brewassistant.brewday_start_verified` |
| `starting` | Blått, stilla | Ingen dubbelstart |
| `running` | Rött, stilla | Visa status; knappen STOPPAR **inte** bryggningen |
| `aborted` | Gult, stilla | Visa spärrorsak; separat alltid synlig **ABORT** |

Blink/puls kan stängas av via `prefers-reduced-motion`.

## Regler/säkerhet

- START är en **egen backendtjänst**, **inte** en direkt `switch.turn_off`.
- START verifierar RCL-källa, källa/session/profil-ID/steg-ID, rätt raw device,
  komplett profilkontrakt, target, intern BZ-temperatur, BZ-huvudström PÅ och
  aktuella värme-/pump-utgångar inkl utilization. Telemetri högst 90 sekunder.
- Exakt profilenhet identifieras via `ba_source: rapt_cloud_link_brewzilla_profile_runtime`.
  Flera möjliga RCL/BrewZilla-enheter utan exakt entydighet blockerar start.
- Preflight är read-only och beräknar `ready`/orsaker utan fysisk styrning.
- Vid bekräftad START med matchande identiteter aktiveras BA:s RCL Assist via
  den befintliga **guardade** read-only-vägen. Backend validerar omedelbart
  igen före aktivering och kontrollerar samma session/steg efteråt.
- GO/rött kvarstår när RAPT-profilen går till nästa steg i samma session,
  men försvinner vid ny session/profil, källbortfall, ABORT eller återstart.
- ABORT är **separat och högre prioriterat**: OFF/0 och profil-STOP begärs
  oberoende av START-status. BZ:s huvudström lämnas normalt PÅ för återläsning.
  HA-/molnkvittens kan aldrig certifiera fysisk OFF.
- Read-only innebär fortsatt beräkning men **inga vanliga BA-skrivningar**.
  Direkt manuell switch OFF nekas i 0b6 när START-transaktionen saknas.

## Viktig begränsning (avsiktligt fail-closed)

**Den här första START-implementationen startar inte en laddad men ännu inaktiv RAPT-profil från RAPT.io.**

RCL:s `binary_sensor.*_profile_active` levererar verifierad `profile_id`,
`profile_session_id` och `step_id` från den **aktiva** sessionen; enbart
laddat recept ger inte dessa nödvändiga identiteter. Att gissa eller återanvända
ett historiskt ID kan starta fel bryggning. RCL-start av inaktiv profil,
Manual Brewday och Brewfather Brew Tracker START ligger i [issue #258](https://github.com/Jocke1970/brewassistant-beta/issues/258).
De förblir GULA/spärrade i denna kandidat.

För första vattenprovet: låt RAPT-profilen starta genom RAPT/BrewZilla,
kontrollera dess riktiga profilsensor, och använd därefter grön START för
BA:s heat/pump-assistans under uppsikt.

## Installation

- Fullständiga kort: `dashboard/cards/brewday_control_status_sv.yaml` och
  `dashboard/cards/brewday_control_status.yaml`.
- Backend måste vara en **0b6-beta som inkluderar** ny
  `sensor.brewassistant_brewday_start_status` och
  `brewassistant.brewday_start_verified`. Ett kort inklistrat mot installerad
  0b5 visar därför gult/otillgängligt och **kan inte utföra START**.
- **Installera inte dev i produktionsbryggeriet för att få den nya knappen**.
  Behåll 0b5 under uppsikt och vänta med START-test tills säker beta är redo.
- Gammal knapp `AKTIVERA BA-STYRNING` har tagits bort ur premiumkortet.
  Read-only **PÅ** finns kvar som separat skyddsknapp.
- Den faktiska säkerhetskontrollen måste göras med **vatten** och fysiska
  utgångs- och temperaturkontroller innan vidare release.

## Acceptanskrav

1. Gul/blink och tydliga skäl vid saknat recept, profil-ID, session, steg,
   readback, target, gammal telemetri, fallback/resync och ABORT.
2. Grön/blink först vid färsk verifierad aktiv RCL och read-only PÅ.
3. Bekräftelsedialog + nytt backend-check; fel identitet ska inte ge kommandon.
4. RCL Assist röd/stilla **endast** efter verifierad START; nästa RAPT-steg
   i samma session får inte göra RUNNING till felaktig BLOCKED.
5. Byte av RAPT-session, nätavbrott eller ABORT kan aldrig återstarta BA.
6. Separat ABORT testas före/under/efter START med BZ-huvudström kvar PÅ.
7. MB och BF-BT kräver egna genomgångna start-/ägarkontrakt före grön START.
