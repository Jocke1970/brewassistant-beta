# Implementation Plan

## Phase 1 — Discovery
Goal: confirm real source data and runtime assumptions.

### Tasks
- inspect Brewfather entities
- inspect Brewfather attributes
- confirm where OG and FG are exposed
- confirm whether dry hop / event data is structured
- confirm available RAPT / Yellow Pill sensors
- define fallback helpers

## Phase 2 — Runtime Layer
Goal: normalize recipe and live data.

### Tasks
- create recipe runtime sensors
- create live runtime sensors
- create source-priority templates
- add SG snapshot helpers
- add attenuation and gravity calculations

## Phase 3 — Decision Engine
Goal: determine process state and operational actions.

### Tasks
- build step preview binary sensors
- build step active binary sensors
- build current action selector
- build next action selector
- build readiness sensors
- build warning sensors

## Phase 4 — Scripts and Automations
Goal: make the workflow usable in practice.

### Tasks
- start batch script
- mark spunding installed
- mark dry hop added
- start cold crash
- mark transfer complete
- daily SG snapshot automation
- recipe-aware notifications

## Phase 5 — Premium UI
Goal: create an action-focused dashboard.

### Tasks
- main batch card
- current action card
- next up card
- details drawer
- shared expand/collapse pattern
- premium color logic and status polish

## Phase 6 — Validation
Goal: confirm the system behaves correctly in real use.

### Tasks
- simulate full process progression
- verify hidden / preview / active transitions
- verify completed steps disappear
- verify fallback behavior when Brewfather data is missing
- verify dashboard clarity during real fermentation

## Phase 7 — Packaging
Goal: prepare the project for GitHub / reuse.

### Tasks
- split files into clean package structure
- add documentation
- add examples
- define install instructions
- prepare release notes
