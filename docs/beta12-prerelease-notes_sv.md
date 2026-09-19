# BrewAssistant v0.2.0-beta.12 — RAPT-källisolering och övervakad vattenvalidering

> [!WARNING]
> **Installerbar testversion, inte bevis på fysisk säkerhet.** Endast vatten, operatör närvarande hela tiden. Ingen obevakad drift eller maltprovning baserat på denna beta. Stoppa vid avvikande värme-/pumpåterkoppling. HLT SIM-1 är en ren simulering, inte elektriskt interlock. Publicera inte denna releasebeskrivning som ett färdigt resultat förrän `beta`-mergecommittens exakta SHA, checks och tagg verifierats.

## Syfte och källregeln

Denna beta gör det möjligt att testa BrewAssistant med RAPT BrewZilla Profile via en riktig HACS-installerad prerelease. **RAPT är ensam process-/mål-/stegkälla när den är vald.** BF och BT delar Brewfather som upstream och får fortsätta läsa, uppdatera och visa information; BT blir inte tyst reservkälla när RAPT-data saknas. BF:s jäsningsfunktioner och manuell bryggning behålls. Befintliga sensorer och dashboardkort är kvar.

## Vad som ingår

- Källbunden BA→BrewZilla-styrning och regressionstester för RAPT aktiv, första ofullständiga kontraktet, förlorad källa, STOP och ABORT. BT-läge är observer-only för BA:s hot-side-kommandon; manuell styrning följer sin befintliga policy.
- Supervised Apply: bindning till rätt aktuell session/steg, separat operatörskvittens för upplyft maltpipa och tillräckligt vatten över elementen, färska OFF/0-avläsningar och uppgiftsbunden tillåtelse att skriva. Underuppgifter får inte ärva behörigheten. Generiska gamla Supervised Apply-ärenden får inte skicka BrewZilla-kommandon under RAPT/BT/osäkert källäge; policyskrivning nekar maskerade/avvikande entity-ID:n.
- Sparge: BA kan föreslå förkok upp till 95 °C, men **positiv värmning är blockerad** om RAPT:s aktuella lokala Sparge-mål är annat (t.ex. 78 °C), saknas eller inte verifierats. RAPT/operatör sköter manuellt stegbyte. OFF/0-åtgärder behålls; ett HA-serviceanrop är inte fysisk OFF-verifiering.
- Utökad Brewday Audit och HLT JSONL med vald källa, RAPT-session/steg, temperaturmålets ursprung och diagnostiska spärrar. Gamla loggfält och historiska rapporter är kvar. HLT:s extra HA-fält är observationer och får aldrig ge effekt- eller styrbehörighet.
- Kompletta befintliga BF/BT-feed-kort på svenska och engelska är återställda. Nya separata RAPT Sparge-kort på båda språken har käll-/stegfilter och blockeringsorsaker. HLT SIM-1 från `dev` bevaras, utan fysisk HLT-styrning eller begränsning av BrewZillas effekt.

## Kända begränsningar och stoppvillkor

- Automatiska/fejkade HA-service-tester och gröna CI/Hassfest/HACS verifierar kodkontrakt, inte RCL:s verkliga Sparge-payload, fysiska OFF eller faktisk Lovelace-rendering. Kontrollera dessa på installerad beta **innan positiva styrkommandon tillåts**.
- Ett verkligt RAPT-profilsteg som behåller 78 °C får inte motregleras av BA:s 95 °C. Kontrollera profilens lokala mål och steg-ID i HA/RCL; om målen inte är identiska ska förkoksvärmen fortsätta vara blockerad. Välj inte ett artificiellt temperaturmål för att kringgå spärren.
- `number.brewzilla_heat_utilization` och pumpens procent är inställningsvärden, inte mätt effekt eller flöde. Säkra vattennivå, pumpprimning och återkoppling på själva enheten. Source loss/STOP/ABORT betyder inte att hårdvaran fysiskt är avstängd.
- HLT:s 2 500 W är scenariobudget och inte verifierad kretsgräns. HLT fysisk värme ska vara bortkopplad under testet. Ingen HA-omstart mitt i bryggning.
- Enhetstesterna är inte ett fullständigt HA-installations- eller browser-test. Beta är uttryckligen till för det första kontrollerade installations-/vattenprovet; dokumentera fel i nytt testprotokoll och skapa en **ny** beta.N+1, ändra aldrig publicerad tagg.

## Releasegrind — måste genomföras i denna ordning

1. Kontrollera `dev` efter feature→dev-merge: manifestversion **`0.2.0-beta.12`**, hela BF/BT-korten, RAPT Sparge-kort, loggmoduler och båda extra service-spärrarna ska finnas. CI/Hassfest/HACS gröna för faktiska dev-SHA:n.
2. Skapa en **separat** PR `dev → beta`; granska hela diffen och välj **Create a merge commit**, aldrig squash/rebase. Låt `dev` och `main` vara kvar.
3. Anteckna beta-mergecommittens fullständiga SHA. Kräv CI (Python 3.11/3.12/3.13), Hassfest och HACS **på just den SHA:n**; kontrollera manifest, `brewzilla/__init__.py`, `brewzilla_rapt_identity_guard.py`, release notes, UI-filer och testschema direkt på `beta`.
4. Skapa en **NY** tagg `v0.2.0-beta.12` från exakt verifierad `beta`-mergecommit. GitHub Release: target `beta`, fullständig text från denna fil, kryssa **Set as a pre-release**, inte latest/stable. Återanvänd eller flytta aldrig beta.11 eller äldre taggar.
5. Läs publicerad taggs commit-SHA och filen `custom_components/brewassistant/manifest.json` via taggen; kräv samma SHA som `beta`, `0.2.0-beta.12` i manifestet och installerade interlock/spärrar. Om mismatch: ingen installation eller test.

## HACS och fysiskt water-only-protokoll (ENDAST efter publicerad prerelease)

1. Avsluta pågående körning och kontrollera lokalt värmare/pump OFF. Säkerhetskopiera installerad integration och manuellt inklistrad dashboard-YAML. Installera exakt `v0.2.0-beta.12` med prereleases i HACS; verifiera tagg och manifestversion före HA-omstart.
2. Starta om HA när ingen bryggning pågår. Klistra manuellt in de svenska kort som används från **samma tagg** (HACS uppdaterar inte manuellt inklistrad YAML), särskilt `dashboard/cards/rapt_sparge_controls_sv.yaml` om Sparge provas. Kontrollera entitets-ID:n och kortens faktiska rendering.
3. Håll fysisk HLT frånkopplad. Börja med read-only/observer-läge och källval: BF/BT kan fortsätta uppdateras, men får inte ändra RAPT-steg eller utlösa BA→BrewZilla-kommandon. Verifiera session-/steg-ID och faktiskt RCL-profilmål, samt att BT inte blir fallback vid förlorat RAPT-kontrakt.
4. Kontrollera STOP och ABORT under säker uppsikt med separat fysisk avläsning av värmare/pump; service-call-success är inte OFF-bevis. Återställ säkert och använd en **ny session**; återanvänd inte gamla kvittenser.
5. Kör Sparge stegvis: verifiera faktisk vattennivå över elementen och upplyft maltpipa innan operatörskvittens. Läs färsk fysisk OFF/0-återkoppling. Vid lokal RAPT 78 °C mot BA 95 °C: verifiera att positiv uppvärmning blockeras; försök inte kringgå spärren. Positivt förkokstest endast efter dokumenterat matchande aktuellt RAPT-mål, separat Supervised Apply-kvittens och operatörens verifiering av vattennivå och lokal reglering.
6. Spara Brewday Audit, HLT JSONL, relevanta RCL-entiteter/attribut, fysisk återkoppling, installerad tagg och utfallet i en **ny daterad fältrapport**. Vid avvikelse: stoppa, rätta i utvecklingsflödet, promotera via dev→beta och publicera ny tagg. `main` ändras först efter användarens uttryckliga godkännande.

**Versionsidentitet att verifiera efter promotion:** tagg `v0.2.0-beta.12` = manifest `0.2.0-beta.12` = verifierad beta-mergecommit. Denna fil är releaseunderlag; den är inte i sig bevis på publicerad release.
