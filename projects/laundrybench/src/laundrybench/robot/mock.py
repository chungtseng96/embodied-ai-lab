from __future__ import annotations

import random
import time

from laundrybench.types import Action, Observation


class MockRobot:
    """Small deterministic-ish stand-in for the physical SO-101.

    It exists so we can build and test the experiment/evaluation plumbing
    before the hardware arrives.
    """

    def __init__(self, seed: int = 0, success_after_steps: int = 4) -> None:
        self._rng = random.Random(seed)
        self._success_after_steps = success_after_steps
        self._steps = 0
        self._joints = [0.0] * 6

    def reset(self) -> None:
        self._steps = 0
        self._joints = [0.0] * 6

    def observe(self) -> Observation:
        return Observation(
            timestamp_s=time.time(),
            joint_positions=list(self._joints),
            image_ref="mock://camera/frame",
            metadata={"step": self._steps},
        )

    def apply(self, action: Action) -> None:
        self._steps += 1
        self._joints = list(action.joint_targets)

    def task_success(self) -> bool:
        if self._steps < self._success_after_steps:
            return False
        return self._rng.random() < 0.8
