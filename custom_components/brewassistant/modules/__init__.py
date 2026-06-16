"""BrewAssistant module and capability registry.

This package is intentionally passive for now: it defines the target module/capability
shape without changing runtime behavior. Future config/options flow and entity setup can
use these manifests to decide what should be enabled, available or visible.
"""

from .manifest import (
    CapabilityManifest,
    CapabilityPolicy,
    CapabilityType,
    ModuleManifest,
    ModuleStatus,
    ModuleType,
)
from .registry import MODULE_MANIFESTS, get_module_manifest, iter_module_manifests

__all__ = [
    "CapabilityManifest",
    "CapabilityPolicy",
    "CapabilityType",
    "ModuleManifest",
    "ModuleStatus",
    "ModuleType",
    "MODULE_MANIFESTS",
    "get_module_manifest",
    "iter_module_manifests",
]
