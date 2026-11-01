from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureCategory(str, Enum):
    """Why a failed episode failed."""

    MISSED_GRASP = "missed_grasp"
    GRASP_LOST = "grasp_lost"
    WRONG_OBJECT = "wrong_object"
    DROPPED = "dropped"
    MISSED_BASKET = "missed_basket"
    TIMEOUT = "timeout"
    INTERVENTION = "intervention"
    HARDWARE_FAULT = "hardware_fault"
    FROZEN_CAMERA = "frozen_camera"
    UNSPECIFIED = "unspecified"


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
    failure_category: FailureCategory | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
