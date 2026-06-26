"""BrewZilla temperature filter placeholder."""

from __future__ import annotations

_INSTALLED = False


def install_temp_filter() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
