# Brewday Runtime patch notes

Planned runtime behavior:

- Brewfather Brew Tracker is a snapshot source.
- BrewAssistant calculates live remaining time between Brewfather snapshots.
- BrewAssistant calculates live progress between Brewfather snapshots.
- Runtime exposes snapshot age and snapshot updated-at metadata.
- Runtime resolves next step from Brewfather raw stages and steps instead of trusting the flat next-step sensor.
- Runtime can expose a timeline structure with stages and steps marked as completed, active or upcoming.
- When live remaining time reaches zero, runtime should enter an awaiting-snapshot state and recommend source refresh.

Implementation target branch: feature/python-core-v0.1.
