"""BrewAssistant BrewZilla package."""

from . import brewzilla_freshness_guard as _freshness_guard
from . import brewzilla_stale_safe_guard as _runtime_safety

_freshness_guard.install_freshness_guard()
_runtime_safety.install_stale_safe_guard()
