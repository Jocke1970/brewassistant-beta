"""Brewday package initialization."""

from .brewfather_ownership import install_core_ownership_policy

# Install before Brewday submodules import brewday_runtime_core symbols so every
# runtime/Manual/audit caller sees the same Planning-vs-Brewing ownership rule.
install_core_ownership_policy()

# Patch the audit autostart setup before the integration imports it. The guard
# keeps terminal-session knowledge outside the rolling event log so a new
# Manual/Brewfather brewday always starts with a clean recorder.
from .brewday_audit_session_boundary import (  # noqa: E402
    install_audit_session_boundary_guard,
)

install_audit_session_boundary_guard()
