"""Manual Brewday Runtime engine.

This module contains the first Python model for manual brewday orchestration.
It is intentionally independent from Lovelace/YAML helpers so the UI can remain
presentation-only while the engine owns timers, steps and transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any


class ManualRuntimeState(StrEnum):
    """Manual runtime states."""

    IDLE = "idle"
    PREPARED = "prepared"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_CONFIRM = "awaiting_confirm"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ManualStep:
    """A single manual brewday step."""

    name: str
    step_type: str = "manual"
    description: str | None = None
    duration_seconds: int | None = None
    target_temperature: float | None = None
    pause_before: bool = False
    auto_advance: bool = False

    def to_timeline_entry(self, index: int, state: str) -> dict[str, Any]:
        """Return a UI-friendly timeline entry."""
        return {
            "index": index,
            "name": self.name,
            "description": self.description,
            "type": self.step_type,
            "duration": self.duration_seconds,
            "value": self.target_temperature,
            "completed": state == "completed",
            "active": state == "active",
            "upcoming": state == "upcoming",
            "state": state,
        }


@dataclass(frozen=True)
class ManualStage:
    """A manual brewday stage."""

    name: str
    stage_type: str = "manual"
    steps: tuple[ManualStep, ...] = field(default_factory=tuple)

    def to_timeline_entry(
        self,
        index: int,
        state: str,
        step_entries: list[dict[str, Any]],
        progress_percent: float | None,
        remaining_seconds: int | None,
    ) -> dict[str, Any]:
        """Return a UI-friendly stage timeline entry."""
        duration = sum(step.duration_seconds or 0 for step in self.steps)
        return {
            "index": index,
            "name": self.name,
            "type": self.stage_type,
            "duration": duration,
            "remaining_seconds": remaining_seconds,
            "progress_percent": progress_percent,
            "completed": state == "completed",
            "active": state == "active",
            "upcoming": state == "upcoming",
            "state": state,
            "steps": step_entries,
        }


@dataclass(frozen=True)
class ManualPlan:
    """A manual brewday plan."""

    name: str = "Manual Brewday"
    stages: tuple[ManualStage, ...] = field(default_factory=tuple)

    @property
    def total_steps(self) -> int:
        """Return total number of steps in the plan."""
        return sum(len(stage.steps) for stage in self.stages)

    @staticmethod
    def default_biab_plan() -> "ManualPlan":
        """Return a safe default BIAB-style manual plan."""
        return ManualPlan(
            name="Manual BIAB Brewday",
            stages=(
                ManualStage(
                    name="Setup",
                    steps=(
                        ManualStep(
                            name="Prepare equipment",
                            description="Check kettle, bag, water volume, malt and hops.",
                            pause_before=True,
                        ),
                        ManualStep(
                            name="Heat strike water",
                            description="Heat water to the planned mash-in temperature.",
                            target_temperature=66.0,
                        ),
                    ),
                ),
                ManualStage(
                    name="Mash",
                    steps=(
                        ManualStep(
                            name="Mash in",
                            description="Add malt and stabilize mash temperature.",
                            target_temperature=66.0,
                            pause_before=True,
                        ),
                        ManualStep(
                            name="Saccharification rest",
                            description="Hold mash temperature.",
                            duration_seconds=3600,
                            target_temperature=66.0,
                            pause_before=True,
                            auto_advance=False,
                        ),
                        ManualStep(
                            name="Mash out",
                            description="Raise mash temperature before lifting the bag.",
                            duration_seconds=600,
                            target_temperature=76.0,
                        ),
                    ),
                ),
                ManualStage(
                    name="Sparge",
                    steps=(
                        ManualStep(
                            name="Lift bag / sparge",
                            description="Drain and optionally sparge to pre-boil volume.",
                            pause_before=True,
                        ),
                    ),
                ),
                ManualStage(
                    name="Boil",
                    steps=(
                        ManualStep(
                            name="Start boil timer",
                            description="Start boil once a stable boil is reached.",
                            pause_before=True,
                        ),
                        ManualStep(
                            name="Boil",
                            description="Boil timer running.",
                            duration_seconds=3600,
                            target_temperature=100.0,
                        ),
                    ),
                ),
                ManualStage(
                    name="Whirlpool",
                    steps=(
                        ManualStep(
                            name="Whirlpool / hop stand",
                            description="Run whirlpool or hop stand schedule before chilling.",
                            duration_seconds=1200,
                            target_temperature=80.0,
                            pause_before=True,
                        ),
                    ),
                ),
                ManualStage(
                    name="Chill / Transfer",
                    steps=(
                        ManualStep(
                            name="Chill wort",
                            description="Cool wort to fermentation temperature.",
                            target_temperature=20.0,
                        ),
                        ManualStep(
                            name="Transfer",
                            description="Transfer wort to fermenter.",
                            pause_before=True,
                        ),
                    ),
                ),
            ),
        )


@dataclass
class ManualRuntimeSession:
    """Mutable runtime state for a manual brewday."""

    plan: ManualPlan = field(default_factory=ManualPlan.default_biab_plan)
    state: ManualRuntimeState = ManualRuntimeState.IDLE
    active_stage_index: int = 0
    active_step_index: int = 0
    step_started_at: datetime | None = None
    paused_at: datetime | None = None
    remaining_when_paused: int | None = None

    @property
    def active_stage(self) -> ManualStage | None:
        """Return active stage."""
        if 0 <= self.active_stage_index < len(self.plan.stages):
            return self.plan.stages[self.active_stage_index]
        return None

    @property
    def active_step(self) -> ManualStep | None:
        """Return active step."""
        stage = self.active_stage
        if stage is None:
            return None
        if 0 <= self.active_step_index < len(stage.steps):
            return stage.steps[self.active_step_index]
        return None

    @property
    def next_step(self) -> ManualStep | None:
        """Return next step across stage boundaries."""
        stage = self.active_stage
        if stage is not None and self.active_step_index + 1 < len(stage.steps):
            return stage.steps[self.active_step_index + 1]

        next_stage_index = self.active_stage_index + 1
        if next_stage_index < len(self.plan.stages):
            next_stage = self.plan.stages[next_stage_index]
            if next_stage.steps:
                return next_stage.steps[0]
        return None

    def prepare(self) -> None:
        """Prepare manual brewday without starting timers."""
        self.state = ManualRuntimeState.PREPARED
        self.active_stage_index = 0
        self.active_step_index = 0
        self.step_started_at = None
        self.paused_at = None
        self.remaining_when_paused = None

    def start(self, now: datetime | None = None) -> None:
        """Start or resume current manual step."""
        now = now or datetime.now(timezone.utc)
        if self.state == ManualRuntimeState.COMPLETED:
            self.active_stage_index = 0
            self.active_step_index = 0
            self.step_started_at = None
            self.paused_at = None
            self.remaining_when_paused = None
            self.state = ManualRuntimeState.IDLE

        if self.state in {ManualRuntimeState.IDLE, ManualRuntimeState.PREPARED, ManualRuntimeState.AWAITING_CONFIRM}:
            self.step_started_at = now
            self.remaining_when_paused = None
        elif self.state == ManualRuntimeState.PAUSED:
            remaining = self.remaining_when_paused
            duration = self.active_step.duration_seconds if self.active_step else None
            if duration is not None and remaining is not None:
                elapsed = max(duration - remaining, 0)
                self.step_started_at = now - timedelta(seconds=elapsed)
            self.remaining_when_paused = None
        self.state = ManualRuntimeState.RUNNING
        self.paused_at = None

    def pause(self, now: datetime | None = None) -> None:
        """Pause current step."""
        now = now or datetime.now(timezone.utc)
        self.remaining_when_paused = self.remaining_seconds(now)
        self.paused_at = now
        self.state = ManualRuntimeState.PAUSED

    def next(self, now: datetime | None = None) -> None:
        """Advance to next step or complete the plan."""
        now = now or datetime.now(timezone.utc)
        stage = self.active_stage
        if stage is None:
            self.finish()
            return

        if self.active_step_index + 1 < len(stage.steps):
            self.active_step_index += 1
        elif self.active_stage_index + 1 < len(self.plan.stages):
            self.active_stage_index += 1
            self.active_step_index = 0
        else:
            self.finish()
            return

        self.step_started_at = now
        self.paused_at = None
        self.remaining_when_paused = None
        step = self.active_step
        self.state = ManualRuntimeState.AWAITING_CONFIRM if step and step.pause_before else ManualRuntimeState.RUNNING

    def finish(self) -> None:
        """Finish manual brewday."""
        self.state = ManualRuntimeState.COMPLETED
        self.step_started_at = None
        self.paused_at = None
        self.remaining_when_paused = 0

    def reset(self) -> None:
        """Reset manual brewday to idle."""
        self.state = ManualRuntimeState.IDLE
        self.active_stage_index = 0
        self.active_step_index = 0
        self.step_started_at = None
        self.paused_at = None
        self.remaining_when_paused = None

    def remaining_seconds(self, now: datetime | None = None) -> int | None:
        """Return remaining seconds for active step."""
        step = self.active_step
        if step is None or step.duration_seconds is None:
            return None
        if self.state == ManualRuntimeState.PAUSED and self.remaining_when_paused is not None:
            return max(self.remaining_when_paused, 0)
        if self.step_started_at is None:
            return step.duration_seconds
        now = now or datetime.now(timezone.utc)
        elapsed = int((now - self.step_started_at).total_seconds())
        return max(step.duration_seconds - elapsed, 0)

    def progress_percent(self, now: datetime | None = None) -> float:
        """Return total plan progress based on completed steps plus active timer."""
        total = self.plan.total_steps
        if total <= 0:
            return 0.0
        completed = 0
        for stage_index, stage in enumerate(self.plan.stages):
            if stage_index < self.active_stage_index:
                completed += len(stage.steps)
            elif stage_index == self.active_stage_index:
                completed += self.active_step_index
                break
        active_fraction = 0.0
        step = self.active_step
        if step and step.duration_seconds:
            remaining = self.remaining_seconds(now)
            if remaining is not None:
                active_fraction = max(0.0, min(1.0, (step.duration_seconds - remaining) / step.duration_seconds))
        elif self.state in {ManualRuntimeState.AWAITING_CONFIRM, ManualRuntimeState.RUNNING, ManualRuntimeState.PAUSED}:
            active_fraction = 0.0
        if self.state == ManualRuntimeState.COMPLETED:
            return 100.0
        return round(((completed + active_fraction) / total) * 100, 1)

    def to_snapshot(self, now: datetime | None = None) -> dict[str, Any]:
        """Return normalized snapshot compatible with Brewday Runtime concepts."""
        now = now or datetime.now(timezone.utc)
        stage = self.active_stage
        step = self.active_step
        next_step = self.next_step
        remaining = self.remaining_seconds(now)
        progress = self.progress_percent(now)
        return {
            "source": "Manual Brewday",
            "status": self.state.value,
            "runtime_state": self.state.value,
            "stage": stage.name if stage else "Idle",
            "step": step.name if step else "Idle",
            "next_step": next_step.name if next_step else "None",
            "progress": progress,
            "time_remaining_seconds": remaining or 0,
            "time_remaining_minutes": round((remaining or 0) / 60),
            "target_temperature": step.target_temperature if step else None,
            "actual_temperature": None,
            "summary": self.summary(now),
            "timeline": self.timeline(now),
        }

    def summary(self, now: datetime | None = None) -> str:
        """Return compact summary."""
        snapshot = {
            "state": self.state.value,
            "stage": self.active_stage.name if self.active_stage else "Idle",
            "step": self.active_step.name if self.active_step else "Idle",
            "progress": self.progress_percent(now),
            "remaining": self.remaining_seconds(now) or 0,
        }
        minutes = round(snapshot["remaining"] / 60)
        return f"{snapshot['state']} · {snapshot['stage']} · {snapshot['step']} · {snapshot['progress']:.0f}% · {minutes} min kvar"

    def timeline(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """Return timeline compatible with Brewfather timeline output."""
        rows: list[dict[str, Any]] = []
        for stage_index, stage in enumerate(self.plan.stages):
            active_stage = stage_index == self.active_stage_index and self.state != ManualRuntimeState.COMPLETED
            completed_stage = self.state == ManualRuntimeState.COMPLETED or stage_index < self.active_stage_index
            upcoming_stage = stage_index > self.active_stage_index and self.state != ManualRuntimeState.COMPLETED
            step_rows: list[dict[str, Any]] = []
            for step_index, step in enumerate(stage.steps):
                active = active_stage and step_index == self.active_step_index
                completed = completed_stage or (active_stage and step_index < self.active_step_index)
                upcoming = upcoming_stage or (active_stage and step_index > self.active_step_index)
                state = "active" if active else "completed" if completed else "upcoming"
                step_rows.append(step.to_timeline_entry(step_index, state))
            state = "active" if active_stage else "completed" if completed_stage else "upcoming"
            rows.append(stage.to_timeline_entry(
                stage_index,
                state,
                step_rows,
                self.progress_percent(now) if active_stage else 100.0 if completed_stage else 0.0,
                self.remaining_seconds(now) if active_stage else 0 if completed_stage else None,
            ))
        return rows
