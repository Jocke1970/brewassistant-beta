# Roadmap

## Next focus: Hot Side action and timer layer

Goal:

```text
Start → activate workflow
Next → move to next brew step
Previous → move back one brew step
Pause → pause workflow/timer
Timer → start/pause/resume timer for current step
Reset → return to Idle
```

Recommended Hot Side steps:

```text
Preparation
Strike Water
Mash
Mash-out
Boil
Whirlpool
Cooling
Done
```

Timer rules:

```text
Preparation → no timer
Mash → mash minutes
Mash-out → mash-out minutes
Boil → boil minutes
Whirlpool → whirlpool minutes
Cooling → manual/no timer
```

## Later polish

```text
1. Remove remaining unavailable/unknown text from UI
2. Add better fallback text: Waiting for data, No active batch, Off, Idle
3. Add Brewfather step sync
4. Add RAPT gravity trend / FG ETA
5. Add dashboard module toggles
6. Add GitHub-ready package structure
7. Add screenshots and badges
8. Add release notes per module
```

## Long-term design

Adapters should feed modules, but modules should never require adapters.

Possible future adapters:

```text
brewassistant_brewfather_adapter.yaml
brewassistant_rapt_adapter.yaml
brewassistant_brewzilla_adapter.yaml
```

Possible future UI packs:

```text
ui/fermentation.yaml
ui/chamber.yaml
ui/kegerator.yaml
ui/hot_side.yaml
ui/health.yaml
```
