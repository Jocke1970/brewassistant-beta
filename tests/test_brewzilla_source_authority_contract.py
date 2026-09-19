"""Pure contract tests; NOT proof the live BA actuator paths are gated."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE = (
    Path(__file__).resolve().parents[1]
    / "custom_components/brewassistant/brewzilla/brewzilla_source_authority_contract.py"
)
# Direct file loading avoids importing the full Home Assistant integration.
spec = importlib.util.spec_from_file_location("brewzilla_source_authority_contract", MODULE)
assert spec is not None and spec.loader is not None
import sys
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_brewfather_hot_side_is_observer_regardless_of_rapt_metadata() -> None:
    result = module.resolve_hot_side_authority(
        "Brewfather Brew Tracker",
        rapt_contract_valid=True,
        rapt_profile_active=True,
        rapt_session_id="old-rapt-session",
        telemetry_fresh=True,
    )
    assert result.mode == "brewfather_observer"
    assert result.may_write_brewzilla is False


def test_rapt_requires_verified_active_fresh_session() -> None:
    valid = dict(
        rapt_contract_valid=True,
        rapt_profile_active=True,
        rapt_session_id="session-1",
        telemetry_fresh=True,
    )
    assert module.resolve_hot_side_authority("RAPT BrewZilla Profile", **valid).may_write_brewzilla is True
    for key, replacement in (
        ("rapt_contract_valid", False),
        ("rapt_profile_active", False),
        ("rapt_session_id", None),
        ("rapt_session_id", " "),
        ("telemetry_fresh", False),
    ):
        case = {**valid, key: replacement}
        result = module.resolve_hot_side_authority("RAPT BrewZilla Profile", **case)
        assert result.mode == "blocked"
        assert result.may_write_brewzilla is False


def test_abort_and_missing_source_never_authorize_new_writes() -> None:
    valid = dict(
        rapt_contract_valid=True,
        rapt_profile_active=True,
        rapt_session_id="session-1",
        telemetry_fresh=True,
    )
    assert module.resolve_hot_side_authority("RAPT BrewZilla Profile", operator_abort=True, **valid).may_write_brewzilla is False
    for source in (None, "", "unknown", "Brewfather Fermentation"):
        assert module.resolve_hot_side_authority(source, **valid).may_write_brewzilla is False


def test_manual_is_explicitly_deferred_without_changing_legacy_behavior() -> None:
    result = module.resolve_hot_side_authority("Manual Brewday")
    assert result.mode == "manual_legacy_unresolved"
    assert result.may_write_brewzilla is None


def test_fermentation_metadata_cannot_implicitly_select_hot_side() -> None:
    assert module.resolve_hot_side_authority("Brewfather Fermentation").mode == "blocked"
    assert module.resolve_hot_side_authority("RAPT BrewZilla Profile", rapt_profile_active=True).mode == "blocked"
