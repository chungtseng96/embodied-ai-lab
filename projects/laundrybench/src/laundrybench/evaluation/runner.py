from __future__ import annotations

import time
import uuid

from laundrybench.policies.base import Policy
from laundrybench.robot.base import Robot
from laundrybench.types import EpisodeResult


def run_episode(
    robot: Robot,
    policy: Policy,
    *,
    max_steps: int = 20,
) -> EpisodeResult:
    """Run one closed-loop episode against a robot and policy."""

    robot.reset()
    start = time.perf_counter()

    for step in range(max_steps):
        observation = robot.observe()
        action = policy.act(observation)
        robot.apply(action)

        if robot.task_success():
            return EpisodeResult(
                episode_id=str(uuid.uuid4()),
                success=True,
                duration_s=time.perf_counter() - start,
                metadata={"steps": step + 1, "policy": policy.name},
            )

    return EpisodeResult(
        episode_id=str(uuid.uuid4()),
        success=False,
        duration_s=time.perf_counter() - start,
        failure_category="timeout_or_task_failure",
        metadata={"steps": max_steps, "policy": policy.name},
    )
