# Manual Brewday remaining work

Validated from Home Assistant testing:

- Manual Brewday runtime starts and resumes correctly.
- Heat strike water resolves to 66.0 C through the shared runtime/stage layer.
- Mash in pauses for operator confirmation.
- Saccharification rest pauses for operator confirmation before the 60 minute timer starts.

Remaining backend work:

1. Update BrewZilla Orchestration so it reads the normalized Brewday Runtime target for both Manual Brewday and Brew Tracker.
2. Keep all hardware write actions in BrewZilla Orchestration only.
3. Avoid direct hardware actions from UI, Stage Engine, Runtime, or adapters.
4. Refine Stage Engine labels so mash rest below target displays as Heating Mash rather than Heating Strike.
5. After this is stable, move backend modules into domain folders without changing behavior.

Architecture rule:

- Runtime/adapters describe what should happen.
- Stage Engine interprets status read-only.
- BrewZilla Runtime normalizes hardware read-only.
- BrewZilla Orchestration is the only layer that may apply hardware actions, behind operator-supervised guardrails.
