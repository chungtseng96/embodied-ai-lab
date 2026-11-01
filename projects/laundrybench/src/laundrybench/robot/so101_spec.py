"""SO-101 arm joint layout and the units its joint values can be reported in."""

from __future__ import annotations

from typing import Literal

SO101_JOINT_NAMES: tuple[str, ...] = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)

JointUnits = Literal["degrees", "normalized"]
