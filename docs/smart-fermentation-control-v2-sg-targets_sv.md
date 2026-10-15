# Smart Fermentation Control v2 – SG-styrda jässteg (designkontrakt)

**Status:** Beslutad målbild, ännu inte implementerad eller accepterad i Home Assistant. Dokumenterad 2026-10-15.  
**Prioritet:** Efter att Cooling Runtime v2 har färdigställts och verifierats.  
**Releaseväg:** dev → beta → main.

## Ansvarsfördelning

- **Brewfather (BF)** tillhandahåller fermenteringsschemats temperaturer, stegordning och planerade tidslängder.
- **BrewAssistant (BA)** lagrar SG-targets för övergångar mellan steg, eftersom BF inte erbjuder SG-target per fermenteringssteg.
- Användaren väljer **TIME** eller **SG** för stegövergångar. Lägena blandas inte.
  - TIME: BF:s tidsvillkor avgör när nästa steg är aktuellt.
  - SG: BA:s SG-target avgör när nästa steg är aktuellt; BF:s tider visas enbart som referens och får inte blockera eller tidigarelägga övergång.
- När ett villkor uppfylls ska BA föreslå nästa steg. **Manuell kvittens krävs innan nästa temperaturmål tillämpas** (supervised apply).
- SG-target kopplas till **övergången från ett steg till nästa**, inte till temperaturvärdet. Sista steget saknar normalt SG-target för nästa steg.

## SG-källor

1. RAPT Pill via **RAPT Cloud Link (RCL)**, med konfigurerad HA-entitet.
2. RAPT Pill via **RAPT BLE**, med konfigurerad HA-entitet.
3. **Manuell SG-mätning** via hydrometer eller refraktometer, registrerad i BA.

Återanvänd Fermentation Trackings konfigurerbara `gravity_entity` / `CONF_GRAVITY_ENTITY` och källmetadata. **Hårdkoda inte** `sensor.yellow_pill_gravity_2` för alla installationer. RAPT BLE Thermometer A7BA är CFC-temperaturkälla och inte SG-källa.

- Manuell mätning är en fullvärdig primär källa, inte bara fallback.
- Tillåt manuella kontrollmätningar även när automatisk RAPT Pill-källa är aktiv; behåll separat mätmetod, tidsstämpel och historik utan att skriva över automatisk data.
- För refraktometer: planera korrekt alkoholkompenserad SG-beräkning med OG och dokumenterad beräkningsmetod; förväxla inte rå Brix med färdig SG.
- Vid saknad, otillgänglig, föråldrad eller orimlig SG-data: **ingen automatisk stegövergång**. Bevara aktuellt steg och visa varför övergång blockeras.
- Filtrera automatiska mätningar och kräv flera rimliga observationer; en ensam spik får inte utlösa kvittensförslag. Manuella mätningar ska ha tydlig mät- och kvittenshistorik.

## UI och beständighet

- Välj TIME/SG per fermenteringssession.
- Visa BF:s steg, temperaturer och tider samt BA:s redigerbara SG-targets per övergång.
- Visa aktiv SG-källa, aktuellt SG, senaste giltiga mätning, mätålder, nästa SG-target och föreslagen övergång.
- Registrera manuella SG-värden med tidpunkt och mätmetod.
- Spara styrmetod, SG-targets, källval, manuella mätningar och kvittenser **per batch/session**, över HA-omstart.
- Flera samtidiga BF-batcher och robust batchmatchning planeras separat. Om aktiv batch inte kan identifieras säkert får BA inte välja godtycklig SG-historik eller recept.

## Särskilda regler och acceptanskriterier

- Kallkrasch kan kräva särskilt villkor för **stabil SG** över tid och separat kvittens, inte bara ett enskilt tröskelvärde.
- Ingen automatisk styrning vid källa-/kommunikationsbortfall. BA ska aldrig tolka bortfall som STOP, OFF eller stegbyte.
- Behåll fysisk styrnings säkerhetskontrakt och separat ägarskap; inga nya parallella direkta BrewZilla-kommandon.
- Testa TIME och SG oberoende, tidig/sen SG-uppfyllelse, SG-spikar, stale/unavailable, RCL/BLE-byte, manuella prover, HA-omstart, fel batch och kallkrasch före beta.

## Avgränsning

Cooling Runtime v2 använder BF:s **första jässtegets temperatur** som kylmål; SG-targets styr **inte** Cooling. Cooling ska färdigställas och testas först. Detta dokument är ett framtida utvecklingskontrakt, inte en beskrivning av redan fungerande funktionalitet.
