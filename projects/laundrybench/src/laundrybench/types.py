from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Observation:
    """What the policy can observe at one step."""

    timestamp_s: float
    joint_positions: list[float]
    image_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Action:
    """A model/policy output intended for the robot."""

    joint_targets: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EpisodeResult:
    """Outcome for one complete task attempt."""

    episode_id: str
    success: bool
    duration_s: float
    intervention: bool = False
    failure_category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
