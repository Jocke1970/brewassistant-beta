"""0b8 UI contract: RCL targets, actual BZ temperature and honest RAPT timers.

Cards are view-only. They must not manufacture a countdown from profileLength
or stepLength, and must never display 0/0 as an actual current profile step.
"""

from pathlib import Path

CARDS = Path(__file__).resolve().parents[1] / "dashboard" / "cards"


def test_rapt_cards_use_fresh_physical_temperature_distinct_from_profile_target():
    for filename in ("rapt_profile_runtime_sv.yaml", "rapt_profile_runtime.yaml"):
        source = (CARDS / filename).read_text(encoding="utf-8")
        assert "sensor.brewzilla_temperature" in source
        assert "measuredAge <= 90" in source
        assert "measuredRaw >= 0 && measuredRaw <= 105" in source
        assert "fmtTemp(measuredTemp)" in source
        assert "fmtTemp(displayRawTarget)" in source
        assert "displayRawTarget = rawTarget === 0 && !cooling ? null : rawTarget" in source
        assert "stepNo > 0 && stepCount !== null && stepCount > 0" in source
        assert "KONTROLLERA KÄLLAN" in source or "CHECK SOURCE" in source
        assert "triggers_update: all" in source
        assert "length / 60" in source  # RCL profile step lengths are seconds
        assert "step_length * 60" not in source
        assert "time_remaining" not in source
        assert "service: number.set_value" not in source
        assert "service: switch.turn_on" not in source


def test_brewday_control_marks_manual_rapt_as_manual_not_fake_remaining_time():
    for filename in ("brewday_control_status_sv.yaml", "brewday_control_status.yaml"):
        source = (CARDS / filename).read_text(encoding="utf-8")
        assert "a.profile_step_end_type" in source
        assert "a.profile_step_length" in source
        assert "manualRcl" in source
        assert "durationRcl" in source
        assert "timeDisplay" in source
        assert "timeDetail" in source
        assert "tile(T.remaining,timeDisplay,timeDetail)" in source
        assert "plannedSeconds/60" in source
        assert "BREWASSISTANT · BREWDAY" in source
        assert "BREWASSISTANT · 0b6 UI" not in source
        assert "service: switch.turn_off" not in source
        assert "brewassistant.brewday_start_verified" in source
        assert "button.brewassistant_abort_brewday" in source
