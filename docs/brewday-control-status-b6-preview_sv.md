# BrewAssistant b6 — Premium Brewday Control / Status (Lovelace preview)

> **UI-only dev candidate.** Kräver BrewAssistant **2026.10.0b5 eller senare** för
> runtime-attribut och `brewassistant.brewday_reconnect_ack`. Ingen integration
> eller dashboard uppdateras automatiskt när någon ändrar en YAML-fil i GitHub.
> Låt `dev → beta → main` gälla backend/releaser. Ingen release/tagg skapas här.

## Montera manuellt

1. Öppna HA → önskad dashboard → **Redigera dashboard**.
2. **Lägg till kort** → **Manuellt**.
3. Kopiera **hela innehållet** ur `dashboard/cards/brewday_control_status_sv.yaml`,
   inte fragment, och spara kortet.
4. Behåll tidigare Brewday-kort tills detta är provkört. Den nya panelen
   innehåller egen ABORT och behöver **inte** `switch.brewassistant_show_brewday`.
5. Om status eller read-only visar `unavailable`, verifiera enheternas **faktiska
   entitets-ID** i HA först. Historiska installationer kan ha det lokaliserade
   `switch.brewassistant_endast_observation_brewzilla_styrs_lokalt` i stället för
   `switch.brewassistant_brewzilla_observe_only`. Ändra inte HA `.storage` manuellt.

Kräver HACS-resurser `custom:button-card` och `custom:expander-card`.
Båda filerna `brewday_control_status_sv.yaml` och `brewday_control_status.yaml`
är kompletta fristående kort (SV/EN).

## Varningar och styrspärrar

- ABORT/NÖDSTOPP är alltid synlig. UI visar inte fysisk OFF-verifiering.
- BA READ-ONLY **PÅ** blockerar BA:s ordinarie hardware writes men stoppar **inte**
  en RAPT/BrewZilla-profil. Behörighetsväxling är inte ett nödstopp.
- Vid `fallback_active` och `resync_required` visas låsta statusar och blockerad
  BA-styrning. Bevarat recept/timer betyder aldrig återtagen fysisk kontroll.
- Knapparna för att lämna read-only och kvittera återanslutning har separat
  visningskontroll. **Backend avgör alltid tillståndet och kan avvisa dem.**
- `brewday_reconnect_ack` skickar färsk `mode`, `expected_step` och för RCL
  `expected_session_id` från det observerade source-snapshotet. Stale/okänt
  session-ID eller steg aktiverar inte knappen. Kvittensen skickar inget eget
  fysiskt kommando, men efterföljande styrtick kan göra det om read-only är AV.
- Kör första övningen med BA READ-ONLY **PÅ** och vattenprov för allt som rör
  värme/pump. Testa aldrig fysisk STOP med UI-status som enda bevis.

## Fermentation UI — återställd stale-indikering

Följande befintliga kort är samtidigt förbättrade i `dev`:

- `dashboard/cards/fermentation_sv.yaml` + engelsk motsvarighet
- `dashboard/cards/fermentation_cockpit_v2_sv.yaml` + engelsk motsvarighet

Korten räknar om ålder varje minut, även när en källa slutar rapportera.
Från **15 minuter** visas gul äldre-varning, från **20 minuter** röd ikon/text,
och frånvarande/okänd mättid visas **rött som ej verifierad**.

V1-kort använder `last_updated` på konfigurerad **källsensor**, inte på en
BrewAssistant-normalsensor. Cockpit v2 använder `temperature_observed_at`
och `gravity_observed_at` i runtime-attributen. HA-observation är inte bevis
för ett nytt **fysiskt** RAPT-prov; Cloud Link kan återpublicera cachade värden.
Inga skriv-/styrvägar eller sensor-källmappningar ändras av denna UI-fix.

## Acceptance före b6

- Montera separat panel; kontrollera read-only PÅ, respektive RCL/Brewfather/Manual-källa.
- Förbered ett simulerat source-loss-fall och verifiera fallback/frozen timeline utan BA-writes.
- Kontrollera resync-vyn, felaktigt steg/session samt korrekt backend-avvisning vid okänd källa.
- Bekräfta ikon + röd stale-text efter 20 minuter och vid bortfallen mättid, både SV och EN.
- Kontrollera att ABORT fortfarande syns utan aktiv Brewday och att fysisk OFF inte påstås.
- Godkänd CI/HACS/Hassfest och isolerade tester på release-kandidaten är **inte** vattenprov.

**Releasestatus:** dev-preview till kommande `2026.10.0b6`. Beta `0b5`
och stable/main ändras inte av denna UI-uppdatering.
