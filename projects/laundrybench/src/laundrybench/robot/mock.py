from __future__ import annotations

import time

from laundrybench.types import Action, Observation


class MockRobot:
    """Small deterministic stand-in for the physical SO-101.

    It exists so we can build and test the experiment/evaluation plumbing
    before the hardware arrives. Task success is judged outside the robot
    (see ``laundrybench.evaluation.judge``). ``seed`` is accepted for call
    compatibility; the mock robot itself is deterministic.
    """

    def __init__(self, seed: int = 0) -> None:
        self._steps = 0
        self._joints = [0.0] * 6
        self.stopped = False

    def reset(self) -> None:
        self._steps = 0
        self._joints = [0.0] * 6
        self.stopped = False

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

    def stop(self) -> None:
        self.stopped = True
