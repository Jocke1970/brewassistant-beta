"""Append-only, per-session Brewday Flight Recorder archive (JSON Lines).

The HA state machine is a status/preview, not the event archive. File IO runs
in HA's executor; callers serialize appends with the brewday_audit session lock.
Never change physical control if disk access fails.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from homeassistant.core import HomeAssistant

_LOG_DIR = ("brewassistant", "logs")
_SAFE_NAME = re.compile(r"^brewday-\d{8}T\d{6}-\d{6}Z\.jsonl$")


def new_session_file(started_at: datetime) -> str:
    """Return a relative path, generated exclusively from a UTC datetime."""
    stamp = started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    return "/".join((*_LOG_DIR, f"brewday-{stamp}.jsonl"))


def _absolute_path(hass: HomeAssistant, relative: str) -> Path:
    parts = relative.split("/")
    if len(parts) != 3 or tuple(parts[:2]) != _LOG_DIR or not _SAFE_NAME.fullmatch(parts[-1]):
        raise ValueError("Invalid Brewday archive path")
    return Path(hass.config.path(*parts))


def _append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # One complete JSON event per line. open(..., 'a') never truncates history.
    payload = json.dumps(event, sort_keys=True, ensure_ascii=False, default=str,
                         separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


def _migrate_legacy_window(path: Path, events: list[dict[str, Any]]) -> bool:
    """Import the last HA .storage window once, without pretending it is complete.

    Exclusive creation makes a retry after power failure non-destructive. If
    the file already exists, preserve its contents rather than replaying rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            header = {
                "schema_version": 3, "event_type": "archive_migration",
                "legacy_window_only": True,
                "legacy_events_retained": len(events),
                "note": "Earlier overwritten .storage events cannot be recovered.",
            }
            handle.write(json.dumps(header, sort_keys=True) + "\n")
            for event in events:
                handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False,
                                        default=str, separators=(",", ":")) + "\n")
        return True
    except FileExistsError:
        return False


async def async_append_event(hass: HomeAssistant, relative: str, event: dict[str, Any]) -> None:
    """Write an actual event off the HA event loop."""
    await hass.async_add_executor_job(_append_jsonl, _absolute_path(hass, relative), dict(event))


async def async_migrate_legacy(
    hass: HomeAssistant, relative: str, events: list[dict[str, Any]]
) -> bool:
    return await hass.async_add_executor_job(
        _migrate_legacy_window, _absolute_path(hass, relative),
        [dict(event) for event in events],
    )
