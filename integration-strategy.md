# Integration Strategy

## Goal

Combine Brewfather, RAPT-style live fermentation logic, and Home Assistant UI into one coherent system.

## Primary Strategy

## Brewfather First
Use Brewfather as the primary source for:
- recipe identity
- fermentation schedule
- recipe notes
- target temperatures
- future process steps
- batch timing context

## Live Sensor First for Reality Checks
Use live fermentation sensors as the source of truth for:
- actual gravity
- actual fermentation temperature
- progress toward FG
- stability over time
- pace of fermentation

## Manual Fallbacks
Use manual helpers only when recipe values are not available from Brewfather or BeerXML.

## Optional BeerXML Layer
BeerXML should be treated as:
- import support
- backup recipe source
- parser-driven supplement
- useful for portability and archival use

It should not be the only required path if Brewfather already provides the current batch context.

## Why This Strategy

A purely BeerXML-driven system is static.

A purely live-sensor-driven system lacks recipe intent.

A Brewfather + live data hybrid gives:
- plan
- live reality
- decision logic

## Source Priority Rules

### Recipe values
1. Brewfather raw/attribute data
2. Brewfather standard sensors
3. BeerXML parsed runtime data
4. manual fallback helpers

### Live values
1. Yellow Pill / RAPT live sensor data
2. derived snapshots / rolling calculations
3. manual override only if explicitly added later

## Expected Unknowns

Before final implementation, the project must verify:
- where Brewfather exposes OG and FG
- whether dry hop events appear as structured data or notes only
- whether spunding rules exist only in notes / manual inputs
- whether experimental all-batches data is stable enough to depend on

## Safe Design Rules

- never hardcode UI logic directly to raw integration entities if a runtime entity can exist
- never assume Brewfather exposes all fields as top-level sensors
- keep fallback helpers available even when Brewfather works
- keep live gravity logic independent from recipe-source logic

## Long-Term Path

### v1
Brewfather-first runtime package with fallback helpers

### v2
Optional BeerXML import bridge

### v3
Reusable custom integration or advanced package system
