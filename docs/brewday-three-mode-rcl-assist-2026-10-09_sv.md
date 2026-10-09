# Brewday trelägesmodell + RCL Assist — 2026-10-09

## Beslut

Brewday har tre normala exekveringslägen:

1. **Manual Brewing**
2. **Brewfather Brewing**
3. **RCL Brewing**

STOP/ABORT är inte ett fjärde läge utan en global kill-switch över alla tre.

## Ägarskap

| Funktion | Manual Brewing | Brewfather Brewing | RCL Brewing |
| --- | --- | --- | --- |
| Recept/steg | BA/manual plan | Brewfather/Brew Tracker | RAPT/BrewZilla-profil |
| Timer/progression | BA | Brewfather/Brew Tracker | RAPT/BrewZilla |
| Target | BA | BF-intent transporteras av BA | **RAPT/BrewZilla; BA får inte skriva target** |
| Heat utilization | BA/Learning | BA/Learning | **BA/Learning** |
| Pump ON/OFF | BA/Learning | BA/Learning | **BA/Learning** |
| Pump utilization | BA/Learning | BA/Learning | **BA/Learning** |
| Heater-switch normal drift | BA-reglering | BA-reglering | **BrewZilla lokal reglering; BA får inte skriva** |

RCL Brewing är alltså ett assist-läge: RAPT/BrewZilla bestämmer **vad**
receptet vill göra och BA optimerar **hur** värmeeffekt och cirkulation används.

När `switch.brewassistant_brewzilla_observe_only` är PÅ spärras även
assist-skrivningarna. När en verifierad RCL-källa är aktiv och read-only
uttryckligen har slagits AV får RCL Assist automatiskt korrigera
heat-utilization samt pump ON/OFF/%. Dessa snabba Learning-korrigeringar kräver
inte ny Supervised Apply-kvittens för varje procentändring. Target och normal
heater ON/OFF förblir spärrade av source-authority-lagret.

## Fallback utan att kasta receptet

Källförlust ändrar **exekveringsläge**, inte batch/recept-identitet.

- aktiv RCL-profil tappas → `Manual Brewing` fallback med senast verifierade
  RAPT-recept/step/timeline kvar;
- aktiv BF/BT-feed tappas → `Manual Brewing` fallback med senast verifierade
  BF-runtime kvar;
- färsk BrewZilla target-readback prioriteras vid fallback, annars används
  cached external target;
- den senast verifierade externa timelinen/profilen konverteras konservativt
  till den befintliga Python-`ManualPlan`-motorn; BA hittar inte på steg som
  saknades i källans recept;
- **Manual Brewing-fallbacken kan fortsätta samma batch lokalt**: aktivt steg
  mappas till motsvarande ManualPlan-position och operatören kan använda
  Manual Brewdays vanliga stegprogression om avbrottet varar;
- den cachade externa timelinen förblir oförändrad som reconnect-referens,
  medan ManualPlan-kopian är operatörens lokala arbetsplan under avbrottet;
- BA visar retained target/stage och operator-led ManualPlan. **Alla vanliga BA-hot-side-writes blockeras under source-loss fallback**, även om mål/readbacks finns. Operatören hanterar fysisk BrewZilla-styrning separat tills källägarskapet är verifierat;
- om själva RCL/BrewZilla-transporten eller nödvändig temperaturtelemetri är
  nere vinner befintlig fail-passive: inga blinda nya writes skickas;
- automatisk återtagning sker **endast** om RCL-session, profil, steg och lokal ManualPlan-progress är oförändrade, medan Brewfather efter källbortfall alltid kräver operatörskvittens (batchidentitet saknar garanterad attestation);
- vid ändrad/okänd identitet eller lokalt avancerad plan låses `resync_required` och BA får ingen normal hot-side-write-behörighet. Operatören måste granska fysisk situation, aktuell session och steg och kvittera separat.

Fallback-cache med senaste externa recept/timeline lagras nu via Home Assistants Store. En HA-omstart kan återskapa receptet och ManualPlan **pausat**, men kan aldrig återställa en tidigare styrbehörighet. Aktuell extern källa behöver verifieras/kvitteras innan BA får styra igen. Tidtagning utan verifierad remaining visas som okänd, inte som en påhittad full stegtid.

### Operatörskvittens vid `resync_required`

Använd endast efter fysisk kontroll av BrewZilla, aktivt RAPT-/Brewfather-recept och aktuellt steg.

I **Utvecklarverktyg → Åtgärder** kör `brewassistant.brewday_reconnect_ack`:

```yaml
mode: RCL Brewing
expected_session_id: <aktuellt verifierat RCL-session-ID>
expected_step: <aktuellt raw step-namn>
```

För Brewfather: `mode: Brewfather Brewing`, ange `expected_step`; session-ID krävs inte när källan saknar ett stabilt batch-ID. Servern läser färsk källa igen vid kvittens och skickar **inga** fysiska kommandon som del av kvittensen. Normala RCL Assist heat/pump-korrigeringar kan dock återupptas vid **nästa styrtick**; håll observe-only på tills anläggningen är redo. Vid aktiv ABORT avvisas kvittensen. Om BA fortfarande markerar okänd identitet ska operatören INTE kvittera blint.

## RCL write-scope

Tillåtet under normal `RCL Brewing`:

```text
number.brewzilla_heat_utilization
switch.brewzilla_pump
number.brewzilla_pump_utilization
```

Blockerat under normal `RCL Brewing`:

```text
number.brewzilla_target_temperature
switch.brewzilla_heater
RAPT profile next/step/timer/recipe writes
```

Global operator-ABORT är separat och försöker fortfarande profile STOP,
heater OFF, pump OFF, heat/pump utilization 0 och main power OFF oavsett normal
source-authority. HA/RCL-ACK räknas aldrig som fysisk OFF-verifikation.

## Release/status

Ändringen förbereds på `dev` för 2026.10.0b5. CI/HACS/Hassfest/RCL-gates ska köras före `dev → beta`. Beta är avsedd för övervakade vattenprov; sådana är **ett krav innan `beta → main`**, inte ett krav för att få installera beta. Bekräftad HA service-ACK är aldrig fysisk OFF-bevisning.
