import pytest

from laundrybench.evaluation.judge import MockSuccessJudge
from laundrybench.evaluation.runner import run_episode
from laundrybench.policies.mock import MockPolicy
from laundrybench.robot.mock import MockRobot


def test_run_episode_returns_result() -> None:
    result = run_episode(
        MockRobot(seed=0),
        MockPolicy(),
        MockSuccessJudge(seed=0, success_after_steps=1),
        max_steps=5,
    )
    assert result.metadata["policy"] == "mock-policy"
    assert result.duration_s >= 0.0


def test_run_episode_can_fail() -> None:
    result = run_episode(
        MockRobot(seed=0),
        MockPolicy(),
        MockSuccessJudge(seed=0, success_after_steps=100),
        max_steps=2,
    )
    assert result.success is False
    assert result.failure_category == "timeout_or_task_failure"


def test_robot_protocol_has_no_task_success() -> None:
    assert not hasattr(MockRobot(), "task_success")


def test_runner_resets_policy_each_episode() -> None:
    policy = MockPolicy()
    robot = MockRobot()
    judge = MockSuccessJudge(success_after_steps=1)
    run_episode(robot, policy, judge, max_steps=3)
    run_episode(robot, policy, judge, max_steps=3)
    assert policy.reset_calls == 2


def test_runner_stops_robot_when_policy_raises() -> None:
    class ExplodingPolicy:
        name = "boom"

        def reset(self) -> None: ...

        def act(self, observation):
            raise RuntimeError("boom")

    robot = MockRobot()
    with pytest.raises(RuntimeError):
        run_episode(robot, ExplodingPolicy(), MockSuccessJudge(), max_steps=3)
    assert robot.stopped is True


def test_runner_stops_robot_after_normal_episode() -> None:
    robot = MockRobot()
    run_episode(robot, MockPolicy(), MockSuccessJudge(success_after_steps=1), max_steps=3)
    assert robot.stopped is True
