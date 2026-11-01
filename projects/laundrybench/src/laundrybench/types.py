from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from laundrybench.robot.so101_spec import SO101_JOINT_NAMES, JointUnits


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


def _check_joint_count(count: int, label: str, joint_names: tuple[str, ...]) -> None:
    if count != len(joint_names):
        raise ValueError(f"got {count} {label} for {len(joint_names)} joint names")


@dataclass(slots=True)
class Observation:
    """What the policy can observe at one step."""

    timestamp_s: float
    joint_positions: list[float]
    joint_names: tuple[str, ...] = SO101_JOINT_NAMES
    joint_units: JointUnits = "normalized"
    # Camera name -> array-like frame, or None when the slot has no frame.
    images: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_joint_count(len(self.joint_positions), "joint positions", self.joint_names)


@dataclass(slots=True)
class Action:
    """A model/policy output intended for the robot."""

    joint_targets: list[float]
    joint_names: tuple[str, ...] = SO101_JOINT_NAMES
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_joint_count(len(self.joint_targets), "joint targets", self.joint_names)


@dataclass(slots=True)
class EpisodeResult:
    """Outcome for one complete task attempt."""

    episode_id: str
    success: bool
    duration_s: float
    intervention: bool = False
    failure_category: FailureCategory | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
