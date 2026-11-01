from __future__ import annotations

import time
import uuid

from laundrybench.evaluation.judge import SuccessJudge
from laundrybench.policies.base import Policy
from laundrybench.robot.base import Robot
from laundrybench.types import EpisodeResult


def run_episode(
    robot: Robot,
    policy: Policy,
    judge: SuccessJudge,
    *,
    max_steps: int = 20,
) -> EpisodeResult:
    """Run one closed-loop episode against a robot, policy, and success judge."""

    robot.reset()
    start = time.perf_counter()
    observation = robot.observe()

    for step in range(max_steps):
        action = policy.act(observation)
        robot.apply(action)
        observation = robot.observe()

        if judge.is_success(observation):
            return EpisodeResult(
                episode_id=str(uuid.uuid4()),
                success=True,
                duration_s=time.perf_counter() - start,
                metadata={"steps": step + 1, "policy": policy.name},
            )

    success = judge.on_timeout(observation)
    return EpisodeResult(
        episode_id=str(uuid.uuid4()),
        success=success,
        duration_s=time.perf_counter() - start,
        failure_category=None if success else "timeout_or_task_failure",
        metadata={"steps": max_steps, "policy": policy.name},
    )
