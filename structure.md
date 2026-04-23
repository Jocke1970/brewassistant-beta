# BrewAssistant – Structure

## Overview
This project builds a smart fermentation workflow in Home Assistant using:
- Brewfather (recipe & schedule)
- RAPT / Yellow Pill (live fermentation data)
- HA (decision engine + UI)

## Architecture Layers
1. Recipe Layer (Brewfather + fallback)
2. Live Data Layer (RAPT / sensors)
3. Decision Engine
4. UI Layer (Lovelace)

## Key Concepts
- State-driven UI
- Step-based workflow (Spunding, Dry Hop, Cold Crash, Transfer)
- Preview vs Active vs Hidden states
