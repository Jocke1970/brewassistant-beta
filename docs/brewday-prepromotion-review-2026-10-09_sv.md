# Brewday 2026.10.0b5 – separat kodgranskning och CI-gate (2026-10-09)

Bas: `dev` commit `6e6b6cd6ff3beb32f59a34772b7ca052b4e8b700`.

Detta är endast en isolerad gransknings-/CI-gren. **Ingen beta-promotion eller release är godkänd.**

## Stoppkriterier för PR #251

Se [issue #252](https://github.com/Jocke1970/brewassistant-beta/issues/252) för bekräftade öppna avvikelser:

1. Extern återanslutning saknar jämförelse mot föregående session och lokalt ManualPlan-step.
2. PAUSED kan omklassas till RUNNING vid source-loss.
3. Återstående stegtid kan nollställas/återställas till full tid.
4. Recipe Context och ManualPlan överlever inte full HA-omstart.
5. De nya trelägestesterna är huvudsakligen statisk sträng-/AST-verifiering; dynamisk beteenderegression saknas.

## Valideringsgränser

Denna gren finns för att release-workflows med `release/**`-filter ska kunna exekvera på en exakt kodkandidat utan att `dev`, `beta`, `main` eller publicerade taggar skrivs om. Resultat på denna branch bevisar inte fysisk STOP, heater OFF eller pump OFF. En eventuell grön CI-gate undanröjer **inte** ovanstående blockerare.

För fysisk acceptans krävs separat övervakat vattenprov och verifierade verkliga utgångar; ingen obevakad automatisk styrning före det.
