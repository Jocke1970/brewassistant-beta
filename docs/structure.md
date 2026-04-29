## Planned Module Structure

BrewAssistant is intended to be modular. Each hardware stage should add functionality without breaking the previous setup.

```text
BrewAssistant
├── Core Workflow
│   ├── Batch state
│   ├── Current phase
│   ├── Next step
│   ├── Progress
│   └── Notifications
│
├── Fermentation / Kegerator Chamber
│   ├── Cooling control
│   ├── Compressor protection
│   ├── Fan circulation
│   ├── Cold crash support
│   └── Serving / storage support
│
├── DigiBoil BIAB Guide
│   ├── Power monitoring only
│   ├── Manual mash workflow
│   ├── Manual sparge workflow
│   ├── Timers
│   └── Checklists
│
├── Fercubator Module
│   ├── Dedicated fermentation chamber
│   ├── Recipe temperature targets
│   ├── Fermentation profiles
│   └── Chamber-specific automation
│
└── BrewZilla RAPT Module
    ├── RAPT telemetry
    ├── Heating status
    ├── Pump status
    ├── Target temperature
    ├── Mash profile support
    └── Advanced hot-side workflow
