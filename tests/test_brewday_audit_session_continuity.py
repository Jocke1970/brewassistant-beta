"""Regression checks for same-brewday Brewfather audit continuity."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/brewassistant/brewday/brewday_audit_session_continuity.py"
BREWDAY_INIT = ROOT / "custom_components/brewassistant/brewday/__init__.py"


def test_audit_session_continuity_source_parses() -> None:
    ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_idle_no_owner_requires_durable_boundary_before_legacy_rotation() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'DATA_KEY_BOUNDARY = "brewday_audit_session_boundary"' in source
    assert 'last_state in {"idle", "inactive"} and last_source in {"", "none"}' in source
    assert "return _boundary_armed(hass)" in source
    assert 'last_state in {"completed", "finished"}' in source
    assert "return True" in source


def test_legacy_autostart_heuristic_is_patched_before_boundary_setup() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    init_source = BREWDAY_INIT.read_text(encoding="utf-8")
    assert "autostart._last_audit_session_finished = _boundary_aware_last_audit_session_finished" in source
    continuity_pos = init_source.index("install_audit_session_continuity_guard()")
    boundary_pos = init_source.index("install_audit_session_boundary_guard()")
    assert continuity_pos < boundary_pos


def test_brewfather_prestart_to_play_is_documented_as_same_session() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "ready-only Brewing pre-start" in source
    assert "when Play then makes the runtime live" in source
    assert "incorrectly rotate the recorder" in source
