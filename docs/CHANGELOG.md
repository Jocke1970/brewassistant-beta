# Changelog

## v4 modular split - working draft

### Added

- Modular backend structure
- Fermentation module
- Chamber module
- Kegerator module
- Brewfather adapter
- Hot Side module
- Health module
- Notifications module
- Cleaning module
- Compatibility-first preservation of `fwk_*` entities

### Confirmed during testing

- Fermentation module loads
- Chamber module loads
- Kegerator module loads
- Brewfather adapter fallback works
- Health module reports OK
- Hot Side UI/core loads
- Kegerator compressor binary sensor patched
- Brewfather target FG fallback patched
- Details helper identified
- Process status Off/Idle behavior patched

### Known remaining work

- Hot Side timer engine
- Hot Side action layer cleanup
- UI fallback polish
- Possible module-specific UI toggles
