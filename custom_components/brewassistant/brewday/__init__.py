"""Brewday package initialization."""

from .brewfather_ownership import install_core_ownership_policy

# Install before Brewday submodules import brewday_runtime_core symbols so every
# runtime/Manual/audit caller sees the same Planning-vs-Brewing ownership rule.
install_core_ownership_policy()
