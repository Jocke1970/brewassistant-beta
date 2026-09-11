from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASH_IN = ROOT / "dashboard" / "cards" / "brewzilla_mash_in_controls_sv.yaml"


def _source() -> str:
    return MASH_IN.read_text(encoding="utf-8")


def test_modular_mash_in_controls_keep_ready_to_started_flow() -> None:
    source = _source()

    assert "INMÄSKNING PÅBÖRJAD" in source
    assert "ready_for_mash_in" in source
    assert "button.brewassistant_mash_in_started" in source

    assert "Inmäskning påbörjad." in source
    assert "mash_in_started" in source
    assert "FORTSÄTT i Brewfather" in source
    assert "button.brewassistant_mash_in_complete" in source


def test_modular_mash_in_controls_preserve_pump_off_handoff_contract() -> None:
    source = _source()

    assert "håller pumpen av" in source
    assert "desired_pump_utilization" in source
    assert "pump 50%" in source

    # The reusable Mash-In card requests BA actions; it must not expose direct
    # BrewZilla pump toggles that could compete with the controller.
    assert "switch.brewzilla_pump" not in source


def test_modular_mash_in_wait_states_remain_visually_distinct() -> None:
    source = _source()

    assert "background: rgba(255,193,7,.12)" in source
    assert "background: rgba(76,175,80,.12)" in source
    assert "mash_in_started" in source


def test_old_ambiguous_master_mash_in_card_is_gone() -> None:
    source = _source()

    assert "name: Inmäskning startad · vänta på BF FORTSÄTT" not in source
