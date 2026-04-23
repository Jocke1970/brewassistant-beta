# UI Specification

## Purpose

Define the desired dashboard behavior for BrewAssistant.

The UI should feel clean, operational, and focused on the current brewing task.

## Core Principles

- show current state first
- show only relevant actions
- reduce clutter
- expose the next step before it becomes urgent
- hide completed steps
- keep details available but collapsed

## Main Layout

## 1. Main Batch Card
Always visible.

### Shows
- recipe name
- current status
- next step
- SG
- fermentation temperature
- batch age
- attenuation / progress
- optional chamber status

## 2. Current Action Card
Shows the single most relevant operational step right now.

Possible stages:
- Spunding
- Dry Hop
- Cold Crash
- Transfer

Only one should be active as the primary action.

## 3. Next Up Card
Optional smaller preview card for the next likely upcoming step.

This helps reduce surprise without cluttering the UI.

## 4. Details Drawer
Collapsed by default.

### Contains
- runtime details
- source information
- diagnostics
- recipe data
- chamber references
- debug entities

## Step Card Behavior

Each step card should support:
- hidden
- preview
- active
- completed

Completed cards should disappear from the action area.

## Expand / Collapse

Main cards should support:
- a toggle in the top right corner
- internal detail visibility helpers
- consistent behavior across brewing cards

Suggested helper:
- `input_boolean.fwk_show_details`

## Visual Language

### Main Batch Card
- premium gradient background
- status color adapts to phase
- clean summary text
- compact but readable

### Action Cards
- stronger emphasis than preview cards
- clear action button
- obvious “why this is showing now”

### Preview Cards
- softer styling
- lower urgency
- short “coming soon” phrasing

## Suggested Sections

### Summary
Main batch card

### Action
Current action card

### Upcoming
Next up preview

### Details
Collapsible diagnostics and raw process information

## Responsive Goal

The UI should remain useful on:
- desktop dashboards
- wall panels
- mobile views later

## Non-Goals for v1

- no overloaded all-in-one mega-card
- no forcing every step to always be visible
- no dependence on manual reading of raw sensors in the UI
