"""Brewday package initialization."""

from .brewfather_ownership import install_core_ownership_policy

# Install before Brewday submodules import brewday_runtime_core symbols so every
# runtime/Manual/audit caller sees the same Planning-vs-Brewing ownership rule.
install_core_ownership_policy()

# Make the legacy audit rotation heuristic consume the deterministic session
# boundary instead of treating Brewfather's ready-only pre-start idle row as a
# completed prior brewday when Play is pressed.
from .brewday_audit_session_continuity import (  # noqa: E402
    install_audit_session_continuity_guard,
)

install_audit_session_continuity_guard()

# Patch the audit autostart setup before the integration imports it. The guard
# keeps terminal-session knowledge outside the rolling event log so a new
# Manual/Brewfather brewday always starts with a clean recorder.
from .brewday_audit_session_boundary import (  # noqa: E402
    install_audit_session_boundary_guard,
)

install_audit_session_boundary_guard()

# Physical mash/ramp timing follows actual controller actuation rather than the
# Brewfather source schedule. In particular, a Brewfather pause at mash
# additions must not freeze an active Heatstrike ramp clock.
from .brewday_physical_timing_phase_patch import (  # noqa: E402
    install_physical_timing_phase_patch,
)

install_physical_timing_phase_patch()
