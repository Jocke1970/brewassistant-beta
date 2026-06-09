"""Compatibility wrapper for the kegerator guard module.

The canonical implementation lives in ``brewassistant.kegerator.guard``.
This file remains temporarily so older imports keep working during the
kegerator package cleanup.
"""

from __future__ import annotations

from .kegerator.guard import (  # noqa: F401
    async_apply_kegerator_guard,
    async_disable_kegerator_guard,
    async_enable_kegerator_guard,
    async_setup_kegerator_guard,
    build_kegerator_guard_snapshot,
)
