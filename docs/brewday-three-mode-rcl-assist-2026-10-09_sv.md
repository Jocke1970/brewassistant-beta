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
- den externa timelinen fryses under denna första implementation; BA hittar
  inte på nästa externa steg när källan saknas;
- **aktuellt steg fortsätter däremot som aktiv Manual Brewing-fallback**:
  BA använder retained target/stage för Learning/Advice och får fortsätta
  target/heat/pump-kontroll enligt Manual-regler när transport/readbacks är
  tillgängliga;
- om själva RCL/BrewZilla-transporten eller nödvändig temperaturtelemetri är
  nere vinner befintlig fail-passive: inga blinda nya writes skickas;
- när samma externa källa åter blir giltig vinner den automatiskt
  source-arbitrationen och Brewday återgår till `RCL Brewing` respektive
  `Brewfather Brewing`.

Fallback-cachen är runtime-lokal i HA i denna implementation. En full HA-omstart
utan frisk extern källa återskapar därför inte receptet ur minnet; det läget
förblir fail-closed. Persistent recipe→ManualPlan-import är ett separat nästa
steg innan vi kräver autonom progression genom ett längre nät-/HA-avbrott.

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

Ändringen finns endast på `dev` inom 2026.10.0b5-arbetet. Nuvarande
`beta` 2026.10.0b4 och `main` ändras inte. Backend/regressionstester är inte
fysisk acceptans; nytt vattenprov krävs före promotion.
