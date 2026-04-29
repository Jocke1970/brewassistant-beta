# Changelog

## v1.2-dashboard-cleanup

### Added

- Problem Center v1.1 documentation
- Hot Side Premium Workflow v1.1 concept
- FWK / Fermentation Process card enable/power workflow
- Kegerator Premium card with simplified `Temps | System` sections
- Stable helper abstraction for kegerator power:
  - `sensor.brewassistant_kegerator_power_w`
  - `binary_sensor.kegerator_compressor_active`
- Battery monitoring concept:
  - RAPT Pill battery sensor presence
  - Kegerator temperature sensor battery warning
- Future Shelly 4-outlet power strip mapping strategy

### Changed

- Dashboard should prefer BrewAssistant helper/template entities instead of raw physical device entities.
- Kegerator `Modes` section removed from main UI; mode data remains available through entity details.
- Problem Center status tiles expanded to include Brewfather and Battery.
- FWK card can now be collapsed/expanded via enable helper.
- Hot Side card can now be collapsed/expanded via enable helper.

### Fixed

- Problem Center mismatch where top card showed active problems but list did not include Brewfather.
- Template placement issue where `sensor` templates were accidentally placed under `binary_sensor`.
- RAPT Pill battery false warning when battery reports `0` while known to be nearly full.

## v1.1-problem-center

### Added

- `sensor.brewassistant_problem_count`
- `sensor.brewassistant_health_status`
- `binary_sensor.brewassistant_any_problem_active`
- Kegerator/chamber/RAPT/Brewfather health checks
- Compressor running long check
- Temperature deviation checks

## v1.0-dashboard-foundation

### Added

- Initial premium BrewAssistant dashboard structure
- Kegerator card
- FWK workflow card
- Hot Side workflow base
