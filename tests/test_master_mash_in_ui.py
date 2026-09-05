from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "dashboard" / "cards" / "brewassistant_brewday_sv.yaml"


def _source() -> str:
    return MASTER.read_text(encoding="utf-8")


def test_master_has_compact_ready_to_started_mash_in_flow() -> None:
    source = _source()

    assert "STRIKE REDO · STARTA INMÄSKNING" in source
    assert "ready_for_mash_in" in source
    assert "button.brewassistant_mash_in_started" in source

    assert "INMÄSKNING PÅGÅR · VÄNTAR PÅ BF GO" in source
    assert "mash_in_started" in source
    assert "Brewfather har lämnat Paused · väntar på att BA slutför handoff." in source


def test_master_warns_if_pump_is_not_off_during_mash_in() -> None:
    source = _source()

    assert "INMÄSKNING PÅGÅR · ⚠ PUMPEN ÄR INTE AV" in source
    assert "Pumpen ska vara OFF / 0 % under inmäskningen." in source
    assert "switch.brewzilla_pump" in source
    assert "number.brewzilla_pump_utilization" in source


def test_master_started_wait_state_is_visually_attention_grabbing() -> None:
    source = _source()

    assert "ba-mashin-wait-pulse" in source
    assert "prefers-reduced-motion" in source


def test_old_ambiguous_master_mash_in_card_is_gone() -> None:
    source = _source()

    assert "name: Inmäskning startad · vänta på BF FORTSÄTT" not in source
