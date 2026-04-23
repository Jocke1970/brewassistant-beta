# Acceptance Criteria

## Purpose

Define when core BrewAssistant features are considered complete.

## Foundation

### Runtime Data
- recipe runtime sensors exist
- live runtime sensors exist
- source priority is documented
- fallback helpers work when source data is missing

### Decision Engine
- the system can determine current process status
- the system can determine next step
- the system can determine current action stage
- the system can determine next action stage

## Step Visibility

### Spunding
- preview appears before due time
- active state appears when spunding is due
- card disappears after spunding is marked installed

### Dry Hop
- preview appears before SG enters dry hop window
- active state appears inside dry hop window
- card disappears after dry hop is marked added

### Cold Crash
- preview appears when fermentation nears terminal
- active state appears when cold crash is ready
- card disappears after cold crash is started

### Transfer
- preview appears during active cold crash before minimum duration is reached
- active state appears when transfer is ready
- card disappears after transfer is marked completed

## UI

### Main Dashboard
- main batch card is always visible
- current action card shows only one primary active step
- next up card shows only one preview step
- details section can be expanded and collapsed

### Cleanliness
- completed steps do not clutter the dashboard
- irrelevant future steps remain hidden
- the dashboard emphasizes what matters now

## Operational Usefulness
- the user can run the full workflow with scripts and buttons
- notifications fire at the correct stage transitions
- recipe-aware values influence process timing
- live SG and temperature influence recommendations

## GitHub Readiness
- documentation exists for architecture, roadmap, state machine, and data model
- file layout is documented
- implementation order is documented
