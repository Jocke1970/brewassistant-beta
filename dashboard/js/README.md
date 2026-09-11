# BrewAssistant dashboard JavaScript drafts

This directory contains BrewAssistant-specific Lovelace custom-card drafts.
They are not installed by the Home Assistant custom integration automatically.

## Temperature gauge draft

File:

```text
brewassistant-temperature-gauge.js
```

Purpose:

```text
Mash/BLE needle + Wort/Internal needle
  -> exact same SVG center/radius/scale

Target
  -> dedicated visible target chip + marker

Target bands
  -> precision band ±0.3 °C
  -> quality band ±1.0 °C

Card background
  -> yellow while heating below target
  -> green inside configured target background tolerance
  -> red on overshoot
```

The card uses BrewAssistant entity IDs as defaults and automatically prefers the
Heatstrike target while the Heatstrike latch is active. Swedish/English labels
follow the Home Assistant frontend language.

### Manual test install

Copy the JavaScript file to:

```text
/config/www/brewassistant/brewassistant-temperature-gauge.js
```

Then add a Lovelace JavaScript module resource:

```text
/local/brewassistant/brewassistant-temperature-gauge.js?v=1
```

After adding/replacing the resource, hard-refresh the browser/frontend cache.

Example card:

```yaml
type: custom:brewassistant-temperature-gauge
min: 20
max: 80
precision_tolerance: 0.3
quality_tolerance: 1.0
background_tolerance: 1.5
```

The Swedish conditional wrapper used for the BrewAssistant dashboard draft is:

```text
dashboard/cards/brewzilla_temperature_gauge_js_sv.yaml
```

## Status

This is a development draft on `dev`. Keep the existing `gauge-card-pro` card as
the production/fallback card until the SVG gauge has been visually validated in
real Home Assistant states (Heatstrike, Mash, target, overshoot, blocked and
RCL-degraded).
