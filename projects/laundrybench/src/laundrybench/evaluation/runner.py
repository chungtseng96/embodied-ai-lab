from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from laundrybench.evaluation.judge import SuccessJudge
from laundrybench.policies.base import Policy
from laundrybench.robot.base import Robot
from laundrybench.types import Action, EpisodeResult, FailureCategory, Observation


def run_episode(
    robot: Robot,
    policy: Policy,
    judge: SuccessJudge,
    *,
    control_hz: float,
    timeout_s: float,
    clock: Callable[[], float] = time.perf_counter,
    sleep: Callable[[float], None] = time.sleep,
    episode_id: str | None = None,
    on_step: Callable[[str, int, Observation, Action], None] | None = None,
) -> EpisodeResult:
    """Run one closed-loop episode paced at ``control_hz`` and bounded by ``timeout_s``.

    Each step observes, acts, applies, re-observes, and asks the judge. A success
    verdict returns immediately; otherwise the loop sleeps until the next tick.
    ``episode_id`` names the result; a random UUID is used when it is not given.
    ``on_step``, when given, is called once per step with the episode id, the
    step index, the pre-action observation, and the action, before the robot
    applies the action.
    """

    if control_hz <= 0:
        raise ValueError(f"control_hz must be positive, got {control_hz}")
    if timeout_s <= 0:
        raise ValueError(f"timeout_s must be positive, got {timeout_s}")

    if episode_id is None:
        episode_id = str(uuid.uuid4())
    period_s = 1.0 / control_hz
    robot.reset()
    policy.reset()
    start = clock()
    next_tick = start
    steps = 0
    try:
        observation = robot.observe()

        while clock() - start < timeout_s:
            action = policy.act(observation)
            if on_step is not None:
                on_step(episode_id, steps, observation, action)
            robot.apply(action)
            observation = robot.observe()
            steps += 1

            if judge.is_success(observation):
                return EpisodeResult(
                    episode_id=episode_id,
                    success=True,
                    duration_s=clock() - start,
                    metadata={"steps": steps, "policy": policy.name, "control_hz": control_hz},
                )

            next_tick += period_s
            sleep(max(0.0, next_tick - clock()))

        success = judge.on_timeout(observation)
        return EpisodeResult(
            episode_id=episode_id,
            success=success,
            duration_s=clock() - start,
            failure_category=None if success else FailureCategory.TIMEOUT,
            metadata={"steps": steps, "policy": policy.name, "control_hz": control_hz},
        )
    finally:
        robot.stop()
