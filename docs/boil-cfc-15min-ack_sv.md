# BrewAssistant DEV: BOIL CFC/kylspiral – kvittens och sista 15 minuterna

**Status:** utveckling för nästa beta efter 2026.10.0b11. Ändrar **inte**
den redan släppta b11 eller stabila `main`.

## Operatörens val vid BOIL-start

Det svenska Brewday Control/Status-kortet visar ett uppmärksamhetskort
så snart RCL bekräftar att **aktuellt steg är BOIL**. Alternativen är:

| Val | Före 15 min återstår | Sista 15 min |
| --- | --- | --- |
| **CFC/KYLSPIRAL KLAR** | Pump OFF/0 % | Begär ON/100 % |
| **INGEN KYLNING** | Pump OFF/0 % | Pump OFF/0 % |
| **Inget val** | Pump OFF/0 % | Pump OFF/0 % |

Fysisk kvittens på CFC innebär att slangar är rätt kopplade,
returvägen är säker och kylkretsen är primad/redo. Det är **inte**
ett omedelbart ON-kommando, och ingen kvittens får själv skriva till
värme eller pump. Välj `Ingen kylning` om ingen sådan recirkulation
ska köras **under koket**.

## Tids- och källvillkor

RAPT/RCL behåller fullständig kontroll över profil, steg, tid och temperaturmål.
BrewAssistant får bara begära pump ON/100 % när:

1. RCL är verifierat profilägare och det **aktuella RCL-steget** är BOIL
   (inte nästa steg, Pre-Boil eller Cooling).
2. Operatören har aktivt valt **CFC/kylspiral klar** på **exakt**
   profil-/sessions-/steg-ID och observerad stegstart. Valet får inte
   ärvas av nästa steg eller nästa bryggning.
3. RCL:s `profile_observed_at` är högst 90 s gammal,
   `profile_contract_complete` och `profile_active` är true.
4. Steget har `step_end_type=Duration`, `step_duration_type=Start`,
   positiv `step_length` **i sekunder** och giltig
   `profile_step_transition_observed_at`.
5. Beräknad tid kvar med samma observerade stegstart är **högst 900 s**.

**Tvåstegsstart för pumpen (säkerhet):** När sista-15-minutersgrinden
är uppfylld begär BA först **pump-utilization 100 % via RCL**. Pump **ON**
får begäras först när den faktiska utilization-entiteten återlästs som ett
**ändligt tal inom 0–100 % och vid 100 % (inom tolerans)**. NaN, infinity,
saknad eller avvikande utilization spärrar start; en servicekvittens
räknas inte som verifierad readback. Även en alternativ BA-väg till
`pump ON` stoppas av samma kontroll.

**Återanslutning:** Om profildata blir för gammal, källa/profil inte går
att verifiera eller aktuellt BOIL lämnas, tas en tidigare kvittens bort
ur BA:s processminne. Om samma RAPT-session senare återkommer måste
operatören välja **CFC/kylspiral klar** på nytt; ingen automatisk
återstart på en gammal kvittens.

**Viktigt:** RCL:s stegstartsdatum är observerat via polling, inte
bekräftad exakt timer på enheten. Sista-15-minutersgränsen är därför
**ungefärlig**. Om timer, källa eller identitet inte kan verifieras
tillåts ingen automatisk positiv pumpstart. Kör då manuellt med
fysisk uppsikt enligt den befintliga säkra ordningen.

Kvittensen sparas bara i HA-processminnet. Efter omstart krävs ny
operatörskvittens, och nya normala bryggningar är säkert default OFF/0 %.

## Skriv- och felhantering

- Den vanliga kedjan **BA → RCL → BrewZilla** används; inget direkt
  parallellt BA→BZ-anrop skapas.
- `_write_allowed` nekar positiva BOIL-pumpkommandon utanför fönstret
  även om anropet kommer via en alternativ BA-kodväg.
- Inga ändringar av pumpstatus följer direkt av knapptrycket.
- READ-ONLY, ABORT, supervised apply, resync, saknad readback och
  fail-passive fortsätter överordnade; källförlust innebär **inte STOP**.
- BOIL:s värmeutilization-100-regel förblir oförändrad:
  inget extra `heater ON`, inget nytt temperaturmål.
- Om inte vald/onormal timer visar UI tydlig status och
  `sensor.brewassistant_brewzilla_boil_cooling_status` har
  diagnostiska attribut för session, steg, val och ungefärlig tid.
- Den manuella kvittensen loggas i Flight Recorder. Valet kan ändras
  under BOIL; `Ingen kylning` innebär OFF/0 % om normal, färsk och
  auktoriserad styrning fortfarande är tillåten.

## Före release

- Kör alla regressioner och sju CI-kontroller på en separat releasegren.
- Kör isolerat HA/RCL-smoke och granska verklig schema/data från RCL b5.
- Kontrollera Lovelace-korten, fysisk CFC-anslutning och timerns beteende
  med vatten, under uppsikt; inga fysiska resultat kan utlovas av CI.
- `beta`/**b11** och `main` förblir orörda under utvecklingen.
