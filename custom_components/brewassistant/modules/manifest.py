"""Manifest models for BrewAssistant modules and capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ModuleType(StrEnum):
    """High-level module category."""

    BASE = "base"
    SOURCE_PROVIDER = "source_provider"
    HARDWARE_ADAPTER = "hardware_adapter"
    OPTIONAL_MODULE = "optional_module"
    DIAGNOSTICS = "diagnostics"


class ModuleStatus(StrEnum):
    """Runtime status a module can report."""

    DISABLED = "disabled"
    ENABLED_MISSING_SOURCES = "enabled_missing_sources"
    ENABLED_READY = "enabled_ready"
    ACTIVE = "active"
    BLOCKED = "blocked"


class CapabilityType(StrEnum):
    """Capability category."""

    READ = "read"
    RECOMMEND = "recommend"
    CONTROL = "control"
    SAFETY = "safety"
    NOTIFY = "notify"


class CapabilityPolicy(StrEnum):
    """Default policy for a capability."""

    DISABLED = "disabled"
    READ_ONLY = "read_only"
    CONFIRM = "confirm"
    DIRECT = "direct"
    GUIDANCE_ONLY = "guidance_only"


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    """Static definition of one capability exposed by a module."""

    key: str
    name: str
    capability_type: CapabilityType
    default_policy: CapabilityPolicy
    description: str = ""


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    """Static definition of a BrewAssistant module."""

    key: str
    name: str
    module_type: ModuleType
    enabled_by_default: bool
    description: str = ""
    required_sources: tuple[str, ...] = ()
    optional_sources: tuple[str, ...] = ()
    capabilities: tuple[CapabilityManifest, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = ()

    @property
    def default_status(self) -> ModuleStatus:
        """Return the initial status implied by default enablement."""
        if not self.enabled_by_default:
            return ModuleStatus.DISABLED
        if self.required_sources:
            return ModuleStatus.ENABLED_MISSING_SOURCES
        return ModuleStatus.ENABLED_READY
