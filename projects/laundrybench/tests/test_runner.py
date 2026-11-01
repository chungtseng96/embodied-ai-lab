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
