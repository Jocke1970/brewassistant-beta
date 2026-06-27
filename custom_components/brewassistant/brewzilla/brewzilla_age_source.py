"""BrewZilla freshness age source helpers.

Home Assistant can report an entity again without changing its state value. In
that case `last_reported` is fresh while `last_updated` stays old. RCL may be
polling correctly even when BrewZilla temperature is stable, so BA freshness
checks should prefer `last_reported` when Home Assistant exposes it.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import State
from homeassistant.util import dt as dt_util

from . import brewzilla_learning as learning
from . import brewzilla_orchestration as orchestration

_INSTALLED = False


def _freshness_timestamp(entity_state: State | None) -> Any:
    if entity_state is None:
        return None
    return getattr(entity_state, "last_reported", None) or entity_state.last_updated


def _entity_age_seconds(entity_state: State | None) -> int | None:
    ts = _freshness_timestamp(entity_state)
    if ts is None:
        return None
    return max(0, int((dt_util.utcnow() - dt_util.as_utc(ts)).total_seconds()))


def install_last_reported_age_source() -> None:
    """Patch BrewZilla age helpers to prefer last_reported over last_updated."""
    global _INSTALLED
    if _INSTALLED:
        return
    orchestration._entity_age_seconds = _entity_age_seconds
    learning._age_seconds = _entity_age_seconds
    _INSTALLED = True
